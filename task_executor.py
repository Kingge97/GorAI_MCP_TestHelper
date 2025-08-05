#!/usr/bin/env python3
# task_executor.py - 任务执行引擎，集成AI聊天系统
import json
import logging
import uuid
import os
from datetime import datetime
from typing import Dict, Any, Optional
from task_scheduler import TaskConfig, TaskExecutionRecord, TaskStatus
from openai import OpenAI

logger = logging.getLogger(__name__)

class TaskExecutor:
    """任务执行引擎，集成WebServer的AI聊天功能"""
    
    def __init__(self, web_server, chat_save_dir: str = "missionChatSave"):
        self.web_server = web_server
        self.chat_save_dir = chat_save_dir
        
    def execute_task(self, task: TaskConfig) -> Optional[str]:
        """执行单个任务"""
        try:
            logger.info(f"开始执行任务: {task.name}")
            
            # 创建执行记录
            execution_id = str(uuid.uuid4())
            start_time = datetime.now()
            
            # 生成聊天文件路径
            chat_filename = f"task_{task.name}_{start_time.strftime('%Y%m%d_%H%M%S')}_{execution_id}.json"
            chat_path = os.path.join(self.chat_save_dir, chat_filename)
            
            # 准备消息
            messages = [
                {"role": "system", "content": task.prompt},
                {"role": "user", "content": task.user_input}
            ]
            
            # 构建工具定义
            tools = self._build_tools_definition(task.tools)
            
            # 使用任务指定的模型
            model = task.model
            
            # 执行AI任务，获取完整的对话历史
            response, full_conversation = self._execute_ai_task(messages, model, tools)
            
            if response is None:
                raise Exception("AI任务执行失败")
            
            # 保存聊天记录（包含完整的对话历史）
            chat_data = {
                'task_name': task.name,
                'task_id': task.id,
                'execution_id': execution_id,
                'prompt': task.prompt,
                'user_input': task.user_input,
                'tools': task.tools,
                'model': model,
                'messages': full_conversation,  # 使用完整的对话历史，包括所有工具调用
                'response': response,
                'start_time': start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'status': 'completed',
                'ai_conversation': full_conversation,  # 完整的AI对话记录
                'tool_calls': self._extract_tool_calls(full_conversation),  # 从完整对话中提取工具调用记录
                'final_response': response
            }
            
            os.makedirs(self.chat_save_dir, exist_ok=True)
            with open(chat_path, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"任务 {task.name} 执行完成，聊天记录已保存到 {chat_filename}")
            return chat_filename
            
        except Exception as e:
            logger.error(f"任务 {task.name} 执行失败: {e}")
            return None
    
    def _build_tools_definition(self, tool_names: list) -> Optional[list]:
        """构建工具定义"""
        if not tool_names or not self.web_server.mcp_client:
            return None
            
        tools = []
        
        for tool_name in tool_names:
            tool = next((t for t in self.web_server.available_tools if t['name'] == tool_name), None)
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
        
        返回:
            tuple: (最终响应内容, 完整的对话历史)
        """
        try:
            # 获取模型配置
            model_config = self.web_server.get_model_config(model)
            openai_client = OpenAI(
                api_key=model_config['api_key'],
                base_url=model_config['base_url']
            )
            
            final_response = None
            current_messages = messages.copy()
            
            while True:
                kwargs = {
                    'model': model,
                    'messages': current_messages,
                }
                
                if tools:
                    kwargs['tools'] = tools
                    kwargs['tool_choice'] = 'auto'
                
                # 调用AI
                response = openai_client.chat.completions.create(**kwargs)
                
                # 获取AI回复
                assistant_message = response.choices[0].message
                
                # 如果没有工具调用，直接返回内容
                if not assistant_message.tool_calls:
                    final_response = assistant_message.content
                    current_messages.append({
                        "role": "assistant",
                        "content": final_response
                    })
                    break
                
                # 有工具调用，先添加助手消息
                current_messages.append({
                    "role": "assistant",
                    "tool_calls": [tc.dict() for tc in assistant_message.tool_calls]
                })
                
                # 执行所有工具调用
                for tool_call in assistant_message.tool_calls:
                    try:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        
                        logger.info(f"执行任务工具调用: {tool_name}")
                        result = self.web_server.mcp_client.execute_tool(tool_name, tool_args)
                        
                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result)
                        })
                        
                    except Exception as e:
                        error_msg = f"工具执行错误: {str(e)}"
                        logger.error(f"工具调用失败: {e}")
                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_msg
                        })
                
                # 继续循环，让AI处理工具调用结果
            
            return final_response, current_messages
            
        except Exception as e:
            logger.error(f"AI任务执行失败: {e}")
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
    
