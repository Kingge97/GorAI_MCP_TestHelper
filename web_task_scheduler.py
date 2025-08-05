#!/usr/bin/env python3
# web_task_scheduler.py - 集成Web服务器的任务调度器
import json
import logging
import threading
import time
import uuid
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from task_scheduler import TaskScheduler, TaskConfig, TaskExecutionRecord, TaskStatus
from task_executor import TaskExecutor

logger = logging.getLogger(__name__)

class WebTaskScheduler(TaskScheduler):
    """集成Web服务器的任务调度器"""
    
    def __init__(self, web_server, config_file: str = "tasks.json", chat_save_dir: str = "missionChatSave"):
        super().__init__(config_file, chat_save_dir)
        self.web_server = web_server
        self.task_executor = TaskExecutor(web_server, chat_save_dir)
        
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

    def _execute_task(self, task: TaskConfig):
        """使用Web服务器执行单个任务"""
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
            
            # 使用任务执行器执行任务
            chat_filename = self.task_executor.execute_task(task)
            
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