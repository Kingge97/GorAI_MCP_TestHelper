#!/usr/bin/env python3
# task_scheduler.py - 定时任务调度系统
import json
import threading
import time
import uuid
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, asdict
from enum import Enum

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

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, config_file: str = "tasks.json", chat_save_dir: str = "missionChatSave"):
        self.config_file = config_file
        self.chat_save_dir = chat_save_dir
        self.tasks: Dict[str, TaskConfig] = {}
        self.execution_records: Dict[str, TaskExecutionRecord] = {}
        self.running = False
        self.scheduler_thread = None
        self.current_execution = None
        self.execution_lock = threading.Lock()
        
        # 确保目录存在
        os.makedirs(chat_save_dir, exist_ok=True)
        
        # 加载现有任务
        self.load_tasks()
    
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
            
            # 这里我们需要访问web_server实例，但task_scheduler是独立的
            # 所以我们需要在app.py中重写这个方法
            # 暂时使用模拟执行
            self._simulate_task_execution(task, execution_id)
            
            # 更新任务状态
            task.current_executions += 1
            task.last_execution_file = self.execution_records[execution_id].chat_file
            
            # 计算下次执行时间
            next_time = start_time + timedelta(minutes=task.interval_minutes)
            task.next_execution_time = next_time.isoformat()
            
            # 如果达到最大执行次数，停用任务
            if task.max_executions != -1 and task.current_executions >= task.max_executions:
                task.is_active = False
                logger.info(f"任务 {task.name} 已达到最大执行次数，已停用")
            
            self.save_tasks()
            
            logger.info(f"任务 {task.name} 执行完成")
            
        except Exception as e:
            logger.error(f"任务 {task.name} 执行失败: {e}")
            if self.current_execution:
                self.current_execution.status = TaskStatus.FAILED.value
                self.current_execution.error_message = str(e)
        finally:
            self.current_execution = None
    
    def _simulate_task_execution(self, task: TaskConfig, execution_id: str):
        """模拟任务执行（实际环境中会替换为真实的AI调用）"""
        try:
            # 这里在实际环境中会调用WebServer的chat方法
            logger.info(f"模拟执行任务: {task.name} - {task.user_input}")
            
            # 模拟执行时间
            time.sleep(2)
            
            # 创建模拟的聊天文件
            chat_data = {
                'task_name': task.name,
                'execution_id': execution_id,
                'prompt': task.prompt,
                'user_input': task.user_input,
                'tools': task.tools,
                'messages': [
                    {'role': 'system', 'content': task.prompt},
                    {'role': 'user', 'content': task.user_input},
                    {'role': 'assistant', 'content': f'任务 "{task.name}" 已按计划执行'}
                ],
                'execution_time': datetime.now().isoformat()
            }
            
            chat_filename = self.execution_records[execution_id].chat_file
            chat_path = os.path.join(self.chat_save_dir, chat_filename)
            
            with open(chat_path, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, ensure_ascii=False, indent=2)
            
            self.execution_records[execution_id].status = TaskStatus.COMPLETED.value
            self.execution_records[execution_id].end_time = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"模拟任务执行失败: {e}")
            raise
    
    def cancel_current_execution(self) -> bool:
        """取消当前执行的任务"""
        if self.current_execution:
            # 这里实际环境中需要实现中断逻辑
            logger.info(f"取消当前执行任务: {self.current_execution.task_name}")
            self.current_execution.status = TaskStatus.CANCELLED.value
            self.current_execution.end_time = datetime.now().isoformat()
            return True
        return False
    
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
        # 标准化时间格式以确保比较的一致性
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

# 全局调度器实例
task_scheduler = TaskScheduler()