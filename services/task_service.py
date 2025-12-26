#!/usr/bin/env python3
# task_service.py - 任务服务层，集成任务调度和执行功能
import json
import logging
import threading
import time
import uuid
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from .base_service import BaseService

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskConfig:
    """任务配置"""
    id: str
    name: str
    prompt: str  # 任务执行的提示词
    user_input: str  # 用户输入的命令
    tools: List[str]  # 需要使用的工具列表
    model: str  # 使用的AI模型
    interval_minutes: int  # 执行间隔（分钟）
    max_executions: int  # 最大执行次数（-1为无限循环）
    created_at: str
    updated_at: str
    next_execution_time: str
    last_execution_file: Optional[str] = None
    current_executions: int = 0
    status: str = TaskStatus.PENDING.value
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskConfig':
        return cls(**data)

@dataclass
class TaskExecutionRecord:
    """任务执行记录"""
    id: str
    task_id: str
    task_name: str
    start_time: str
    end_time: Optional[str] = None
    status: str = TaskStatus.RUNNING.value
    chat_file: Optional[str] = None
    error_message: Optional[str] = None
    execution_data: Optional[Dict[str, Any]] = None
    ai_conversation: Optional[List[Dict[str, Any]]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    final_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class TaskService(BaseService):
    """任务服务层，集成任务调度和执行功能"""

    def __init__(self):
        super().__init__()
        self.config_file = "tasks.json"
        self.chat_save_dir = "missionChatSave"
        self.tasks: Dict[str, TaskConfig] = {}
        self.execution_records: Dict[str, TaskExecutionRecord] = {}
        self.running = False
        self.scheduler_thread = None
        self.current_execution = None
        self.execution_lock = threading.Lock()
        self.chat_service = None
        self.tool_service = None

        # 确保目录存在
        os.makedirs(self.chat_save_dir, exist_ok=True)

        # 加载现有任务
        self.load_tasks()

    def initialize(self, chat_service, tool_service):
        """初始化任务服务"""
        self.chat_service = chat_service
        self.tool_service = tool_service
        logger.info("TaskService 初始化完成")

    def load_tasks(self):
        """从文件加载任务"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = {
                        task_id: TaskConfig.from_dict(task_data)
                        for task_id, task_data in data.get('tasks', {}).items()
                    }
                    logger.info(f"已加载 {len(self.tasks)} 个任务")
            else:
                logger.info("任务配置文件不存在，创建新的")
                self.save_tasks()
        except Exception as e:
            logger.error(f"加载任务失败: {e}")

    def save_tasks(self):
        """保存任务到文件"""
        try:
            data = {
                'tasks': {task_id: task.to_dict() for task_id, task in self.tasks.items()},
                'last_updated': datetime.now().isoformat()
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存任务失败: {e}")

    def create_task(self, name: str, prompt: str, user_input: str, tools: List[str],
                   model: str, interval_minutes: int, max_executions: int = -1) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        now = datetime.now()

        task = TaskConfig(
            id=task_id,
            name=name,
            prompt=prompt,
            user_input=user_input,
            tools=tools,
            model=model,
            interval_minutes=interval_minutes,
            max_executions=max_executions,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            next_execution_time=now.isoformat(),
            is_active=True
        )

        self.tasks[task_id] = task
        self.save_tasks()
        logger.info(f"创建任务: {name} (ID: {task_id})")
        return task_id

    def update_task(self, task_id: str, **kwargs) -> bool:
        """更新任务"""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.now().isoformat()
        self.save_tasks()
        logger.info(f"更新任务: {task.name}")
        return True

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id not in self.tasks:
            return False

        task_name = self.tasks[task_id].name
        del self.tasks[task_id]
        self.save_tasks()
        logger.info(f"删除任务: {task_name}")
        return True

    def get_task(self, task_id: str) -> Optional[TaskConfig]:
        """获取任务配置"""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[TaskConfig]:
        """获取所有任务"""
        return list(self.tasks.values())

    def start_scheduler(self):
        """启动调度器"""
        if self.running:
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("任务调度器已启动")

    def stop_scheduler(self):
        """停止调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("任务调度器已停止")

    def _scheduler_loop(self):
        """调度器主循环"""
        while self.running:
            try:
                self._check_and_execute_tasks()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"调度器循环错误: {e}")
                time.sleep(60)

    def _check_and_execute_tasks(self):
        """检查并执行到期任务"""
        now = datetime.now()

        # 获取需要执行的任务（按下次执行时间排序）
        pending_tasks = [
            task for task in self.tasks.values()
            if (task.is_active and
                datetime.fromisoformat(task.next_execution_time) <= now and
                (task.max_executions == -1 or task.current_executions < task.max_executions))
        ]

        pending_tasks.sort(key=lambda t: datetime.fromisoformat(t.next_execution_time))

        for task in pending_tasks:
            if not self.running:
                break

            # 使用锁确保同一时间只有一个任务执行
            with self.execution_lock:
                self._execute_task(task)

    def _execute_task(self, task: TaskConfig):
        """执行单个任务"""
        try:
            logger.info(f"开始执行任务: {task.name}")

            # 创建执行记录
            execution_id = str(uuid.uuid4())
            start_time = datetime.now()

            record = TaskExecutionRecord(
                id=execution_id,
                task_id=task.id,
                task_name=task.name,
                start_time=start_time.isoformat()
            )

            self.execution_records[execution_id] = record
            self.current_execution = record
            record.status = TaskStatus.RUNNING.value

            # 执行任务
            chat_filename = self._execute_task_with_services(task)

            # 加载执行详情
            execution_details = None
            if chat_filename:
                chat_path = os.path.join(self.chat_save_dir, chat_filename)
                if os.path.exists(chat_path):
                    with open(chat_path, 'r', encoding='utf-8') as f:
                        execution_details = json.load(f)

            if chat_filename:
                record.chat_file = chat_filename
                record.status = TaskStatus.COMPLETED.value
                record.end_time = datetime.now().isoformat()

                # 添加增强的执行数据
                if execution_details:
                    record.ai_conversation = execution_details.get('ai_conversation', [])
                    record.tool_calls = execution_details.get('tool_calls', [])
                    record.final_response = execution_details.get('response', '')
                    record.execution_data = {
                        'model': execution_details.get('model'),
                        'tools_used': execution_details.get('tools', []),
                        'prompt': execution_details.get('prompt'),
                        'user_input': execution_details.get('user_input')
                    }

                logger.info(f"任务 {task.name} 执行完成")
            else:
                record.status = TaskStatus.FAILED.value
                record.error_message = "任务执行失败"
                record.end_time = datetime.now().isoformat()
                logger.error(f"任务 {task.name} 执行失败")

            # 更新任务状态
            task.current_executions += 1
            task.last_execution_file = chat_filename

            # 计算下次执行时间
            next_time = start_time + timedelta(minutes=task.interval_minutes)
            task.next_execution_time = next_time.isoformat()

            # 如果达到最大执行次数，停用任务
            if task.max_executions != -1 and task.current_executions >= task.max_executions:
                task.is_active = False
                logger.info(f"任务 {task.name} 已达到最大执行次数，已停用")

            self.save_tasks()

        except Exception as e:
            logger.error(f"任务 {task.name} 执行失败: {e}")
            if self.current_execution:
                self.current_execution.status = TaskStatus.FAILED.value
                self.current_execution.error_message = str(e)
                self.current_execution.end_time = datetime.now().isoformat()
        finally:
            self.current_execution = None

    def _execute_task_with_services(self, task: TaskConfig) -> Optional[str]:
        """使用服务层执行任务"""
        if not self.chat_service or not self.tool_service:
            logger.error("ChatService 或 ToolService 未初始化")
            return None

        try:
            # 准备消息
            messages = [
                {"role": "system", "content": task.prompt},
                {"role": "user", "content": task.user_input}
            ]

            # 构建工具定义
            tools = self._build_tools_definition(task.tools)

            # 生成聊天文件路径
            execution_id = str(uuid.uuid4())
            start_time = datetime.now()
            chat_filename = f"task_{task.name}_{start_time.strftime('%Y%m%d_%H%M%S')}_{execution_id}.json"
            chat_path = os.path.join(self.chat_save_dir, chat_filename)

            # 执行AI任务
            response, full_conversation = self._execute_ai_task(messages, task.model, tools)

            if response is None:
                raise Exception("AI任务执行失败")

            # 保存聊天记录
            chat_data = {
                'task_name': task.name,
                'task_id': task.id,
                'execution_id': execution_id,
                'prompt': task.prompt,
                'user_input': task.user_input,
                'tools': task.tools,
                'model': task.model,
                'messages': full_conversation,
                'response': response,
                'start_time': start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'status': 'completed',
                'ai_conversation': full_conversation,
                'tool_calls': self._extract_tool_calls(full_conversation),
                'final_response': response
            }

            os.makedirs(self.chat_save_dir, exist_ok=True)
            with open(chat_path, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, ensure_ascii=False, indent=2)

            logger.info(f"任务 {task.name} 执行完成，聊天记录已保存到 {chat_filename}")
            return chat_filename

        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return None

    def _build_tools_definition(self, tool_names: list) -> Optional[list]:
        """构建工具定义"""
        if not tool_names or not self.tool_service:
            return None

        tools = []
        available_tools = self.tool_service.get_available_tools()

        for tool_name in tool_names:
            tool = next((t for t in available_tools if t['name'] == tool_name), None)
            if tool:
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool['name'],
                        "description": tool['description'],
                        "parameters": {
                            "type": "object",
                            "properties": tool['parameters'],
                            "required": list(tool['parameters'].keys())
                        }
                    }
                }
                tools.append(tool_def)

        return tools if tools else None

    def _execute_ai_task(self, messages: list, model: str, tools: Optional[list]) -> tuple[Optional[str], list]:
        """执行AI任务，支持工具调用后继续对话
        
        使用 ChatService.execute_ai_task_sync 方法，该方法内部调用 chatToNextLoop，
        自动处理完整的对话循环，包括工具调用和多轮对话。
        """
        try:
            # 复制消息列表，避免修改原始消息
            current_messages = messages.copy()
            
            # 使用 ChatService 的 execute_ai_task_sync 方法
            # 该方法内部使用 chatToNextLoop，自动处理工具调用循环
            final_response, current_messages = self.chat_service.execute_ai_task_sync(
                current_messages,
                model,
                tools,
                self.tool_service  # 传入 tool_service 作为 executor
            )
            
            return final_response, current_messages

        except Exception as e:
            logger.error(f"AI任务执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, messages

    def _extract_tool_calls(self, messages: list) -> list[Dict[str, Any]]:
        """从消息中提取工具调用记录"""
        tool_calls = []

        for message in messages:
            if message.get('role') == 'assistant' and 'tool_calls' in message:
                for tc in message['tool_calls']:
                    tool_calls.append({
                        'id': tc.get('id', ''),
                        'name': tc.get('function', {}).get('name', ''),
                        'arguments': tc.get('function', {}).get('arguments', '{}'),
                        'type': tc.get('type', 'function')
                    })

        return tool_calls

    def reset_task_executions(self, task_id: str) -> bool:
        """重置任务执行次数，保留上次执行记录的绑定"""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.current_executions = 0
        # 保留 last_execution_file 不变，不清除上次执行记录的绑定
        task.updated_at = datetime.now().isoformat()

        # 如果任务因为达到最大次数而停用，重新启用
        if not task.is_active and task.max_executions != -1:
            task.is_active = True
            # 重新计算下次执行时间
            task.next_execution_time = datetime.now().isoformat()

        self.save_tasks()
        logger.info(f"重置任务执行次数: {task.name} (保留上次执行记录: {task.last_execution_file})")
        return True

    def get_execution_history(self, task_id: str = None) -> List[TaskExecutionRecord]:
        """获取执行历史"""
        # 先从内存中获取记录
        records = list(self.execution_records.values())

        # 再从文件系统中加载历史执行记录
        file_records = []
        if os.path.exists(self.chat_save_dir):
            for filename in os.listdir(self.chat_save_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.chat_save_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        # 检查是否是任务执行文件（包含task_id和task_name）
                        if 'task_id' in data and 'task_name' in data:
                            # 创建执行记录
                            execution_id = data.get('execution_id', filename.replace('.json', ''))
                            # 确保start_time格式一致
                            start_time = data.get('start_time', '')
                            if not start_time:
                                # 尝试从文件名提取时间
                                try:
                                    parts = filename.split('_')
                                    if len(parts) >= 3:
                                        date_part = parts[-3] + '_' + parts[-2]
                                        start_time = datetime.strptime(date_part, '%Y%m%d_%H%M%S').isoformat()
                                except:
                                    start_time = datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()

                            record = TaskExecutionRecord(
                                id=execution_id,
                                task_id=data['task_id'],
                                task_name=data['task_name'],
                                start_time=start_time,
                                end_time=data.get('end_time'),
                                status=data.get('status', TaskStatus.COMPLETED.value),
                                chat_file=filename
                            )

                            # 过滤特定任务ID（如果指定）
                            if task_id is None or record.task_id == task_id:
                                file_records.append(record)
                    except Exception as e:
                        logger.warning(f"加载执行记录文件失败: {file_path}, {e}")

        # 合并内存中的记录和文件中的记录，去重
        all_records = {r.id: r for r in records}  # 内存记录优先

        # 使用任务ID+开始时间作为唯一标识，避免重复
        existing_keys = set()
        for r in all_records.values():
            start_time = r.start_time
            if start_time:
                # 确保时间格式一致（去掉微秒和时区信息）
                try:
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    normalized_time = dt.replace(microsecond=0).isoformat()
                except:
                    normalized_time = start_time
            else:
                normalized_time = ''
            existing_keys.add((r.task_id, normalized_time))

        for record in file_records:
            start_time = record.start_time
            if start_time:
                # 确保时间格式一致
                try:
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    normalized_time = dt.replace(microsecond=0).isoformat()
                except:
                    normalized_time = start_time
            else:
                normalized_time = ''

            key = (record.task_id, normalized_time)
            if record.id not in all_records and key not in existing_keys:
                all_records[record.id] = record
                existing_keys.add(key)

        # 按开始时间排序，最新的在前
        result_records = list(all_records.values())
        result_records.sort(key=lambda r: r.start_time, reverse=True)
        return result_records

    def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        # 计算实际执行记录数量（包括文件中的）
        total_executions = len(self.get_execution_history())

        return {
            'running': self.running,
            'total_tasks': len(self.tasks),
            'active_tasks': len([t for t in self.tasks.values() if t.is_active]),
            'current_execution': self.current_execution.to_dict() if self.current_execution else None,
            'total_executions': total_executions
        }

    def get_chat_save_dir(self):
        """获取聊天文件保存目录"""
        return self.chat_save_dir