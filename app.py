#!/usr/bin/env python3
# app.py - Web后端服务器
import json
import logging
from flask import Flask, render_template, request, jsonify, Response, stream_template
from flask_cors import CORS
import openai
from openai import OpenAI
import asyncio
import threading
import time
import traceback
from mcp_server import MCPClient
import os
from datetime import datetime, timedelta
import uuid

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebServer:
    def __init__(self, config_path='config.json'):
        self.config = self.load_config(config_path)
        self.app = Flask(__name__)
        CORS(self.app)
        
        # 初始化OpenAI客户端
        self.openai_client = OpenAI(
            api_key=self.config['llm']['api_key'],
            base_url=self.config['llm']['base_url']
        )
        
        # MCP客户端
        self.mcp_client = None
        self.available_tools = []
        self.selected_tools = []
        
        self.setup_routes()
        self.connect_mcp()

        # 添加对话历史存储
        self.chat_sessions = {}  # 存储每个会话的历史
        self.session_timeout = 3600  # 会话超时时间（秒）
    
    # 添加会话管理方法
    def get_or_create_session(self, session_id=None):
        """获取或创建会话"""
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if session_id not in self.chat_sessions:
            self.chat_sessions[session_id] = {
                'messages': [],
                'created_at': datetime.now(),
                'last_activity': datetime.now()
            }
        else:
            # 更新最后活动时间
            self.chat_sessions[session_id]['last_activity'] = datetime.now()
        
        return session_id, self.chat_sessions[session_id]

    def clean_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.chat_sessions.items():
            if now - session['last_activity'] > timedelta(seconds=self.session_timeout):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.chat_sessions[session_id]

    def load_config(self, config_path):
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"配置文件 {config_path} 未找到")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
            raise
    
    def connect_mcp(self):
        """连接MCP服务器"""
        try:
            mcp_config = self.config['mcp_server']
            self.mcp_client = MCPClient(mcp_config['host'], mcp_config['port'])
            
            logger.info(f"尝试连接MCP服务器 {mcp_config['host']}:{mcp_config['port']}")
            
            if self.mcp_client.connect():
                self.available_tools = self.mcp_client.list_tools()
                logger.info(f"成功连接MCP服务器，加载了 {len(self.available_tools)} 个工具")
                
                # 打印工具详情
                for tool in self.available_tools:
                    logger.info(f"  - {tool['name']} (来自: {tool.get('package', 'unknown')}): {tool['description']}")
                
            else:
                logger.error("无法连接到MCP服务器")
                self.available_tools = []
                
        except Exception as e:
            logger.error(f"连接MCP服务器失败: {e}")
            logger.error(traceback.format_exc())
            self.available_tools = []
    
    def setup_routes(self):
        """设置路由"""
        
        @self.app.route('/')
        def index():
            """主页"""
            return render_template('index.html', config=self.config)
        
        @self.app.route('/favicon.ico')  #新增内容
        def favicon():
            """返回空的favicon以避免404错误"""
            return '', 204
        
        @self.app.route('/api/config')
        def get_config():
            """获取配置信息"""
            return jsonify({
                'models': self.config['llm']['models'],
                'default_model': self.config['llm']['default_model'],
                'ui': self.config['ui']
            })
        
        @self.app.route('/api/debug/status')
        def debug_status():
            """调试状态检查"""
            status = {
                'mcp_client': {
                    'connected': self.mcp_client is not None,
                    'tools_count': len(self.available_tools),
                    'selected_count': len(self.selected_tools)
                },
                'config': {
                    'loaded': self.config is not None,
                    'mcp_server': self.config.get('mcp_server', {}) if self.config else {},
                    'models_count': len(self.config.get('llm', {}).get('models', [])) if self.config else 0
                },
                'tools': []
            }
            
            # 添加工具详情
            for tool in self.available_tools:
                status['tools'].append({
                    'name': tool['name'],
                    'package': tool.get('package', 'unknown'),
                    'description': tool['description'][:100] + '...' if len(tool['description']) > 100 else tool['description']
                })
            
            return jsonify(status)
        
        @self.app.route('/api/tools')
        def get_tools():
            """获取可用工具列表"""
            try:
                if not self.mcp_client:
                    return jsonify({
                        'error': 'MCP客户端未初始化',
                        'tools': [],
                        'selected': []
                    }), 500
                
                # 尝试重新获取工具列表
                try:
                    current_tools = self.mcp_client.list_tools()
                    if current_tools != self.available_tools:
                        self.available_tools = current_tools
                        logger.info(f"工具列表已更新，当前有 {len(self.available_tools)} 个工具")
                except Exception as e:
                    logger.error(f"获取工具列表失败: {e}")
                    # 使用缓存的工具列表
                
                return jsonify({
                    'tools': self.available_tools,
                    'selected': self.selected_tools
                })
                
            except Exception as e:
                logger.error(f"获取工具列表API错误: {e}")
                return jsonify({
                    'error': str(e),
                    'tools': [],
                    'selected': []
                }), 500
        
        @self.app.route('/api/tools/select', methods=['POST'])
        def select_tools():
            """选择要使用的工具"""
            data = request.get_json()
            self.selected_tools = data.get('tools', [])
            logger.info(f"用户选择了 {len(self.selected_tools)} 个工具")
            return jsonify({'success': True, 'selected_count': len(self.selected_tools)})
        
        @self.app.route('/api/chat', methods=['POST'])
        def chat():
            """处理聊天请求"""
            data = request.get_json()
            message = data.get('message', '')
            model = data.get('model', self.config['llm']['default_model'])
            session_id = data.get('session_id')  # 从请求中获取会话ID
            
            if not message.strip():
                return jsonify({'error': '消息不能为空'}), 400
            
            # 获取或创建会话
            session_id, session = self.get_or_create_session(session_id)
            
            # 构建包含历史的消息列表
            messages = [{"role": "system", "content": self.build_system_prompt()}]
            
            # 添加历史消息
            messages.extend(session['messages'])
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": message})
            
            tools = self.build_tools_definition() if self.selected_tools else None
            
            try:
                # 保存用户消息到历史
                session['messages'].append({"role": "user", "content": message})
                
                if self.config['llm']['stream']:
                    return Response(
                        self.stream_chat_response(messages, model, tools, session_id),
                        mimetype='text/plain',
                        headers={'X-Session-ID': session_id}  # 返回会话ID
                    )
                else:
                    response = self.get_chat_response(messages, model, tools)
                    # 保存助手回复到历史
                    session['messages'].append({"role": "assistant", "content": response})
                    return jsonify({
                        'response': response,
                        'session_id': session_id
                    })
                    
            except Exception as e:
                logger.error(f"聊天处理错误: {e}")
                return jsonify({'error': f'处理请求时出错: {str(e)}'}), 500
        
        @self.app.route('/api/execute_tool', methods=['POST'])
        def execute_tool():
            """执行MCP工具"""
            data = request.get_json()
            tool_name = data.get('tool_name')
            parameters = data.get('parameters', {})
            
            if not self.mcp_client:
                return jsonify({'error': 'MCP服务器未连接'}), 500
            
            try:
                result = self.mcp_client.execute_tool(tool_name, parameters)
                return jsonify({'result': result})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
            
        @self.app.route('/api/chat/clear', methods=['POST'])
        def clear_chat():
            """清空对话历史"""
            data = request.get_json()
            session_id = data.get('session_id')
            
            if session_id and session_id in self.chat_sessions:
                self.chat_sessions[session_id]['messages'] = []
                return jsonify({'success': True})
            
            return jsonify({'error': '会话不存在'}), 404
    
    def build_system_prompt(self):
        """构建系统提示"""
        base_prompt = """你是一个智能助手，可以使用各种工具来帮助用户完成任务。"""
        
        if self.selected_tools:
            tools_info = []
            for tool_name in self.selected_tools:
                tool = next((t for t in self.available_tools if t['name'] == tool_name), None)
                if tool:
                    tools_info.append(f"- {tool['name']} (来自{tool['package']}): {tool['description']}")
            
            if tools_info:
                base_prompt += f"\n\n当前可用的工具:\n" + "\n".join(tools_info)
                base_prompt += "\n\n当需要使用工具时，请使用function calling功能调用相应的工具。"
        
        return base_prompt
    
    def build_tools_definition(self):
        """构建工具定义供OpenAI function calling使用"""
        tools = []
        
        for tool_name in self.selected_tools:
            tool = next((t for t in self.available_tools if t['name'] == tool_name), None)
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
        
        return tools
    
    def get_chat_response(self, messages, model, tools=None):
        """获取聊天响应（非流式）"""
        kwargs = {
            'model': model,
            'messages': messages,
        }
        
        if tools:
            kwargs['tools'] = tools
            kwargs['tool_choice'] = 'auto'
        
        response = self.openai_client.chat.completions.create(**kwargs)
        
        # 处理工具调用
        if response.choices[0].message.tool_calls:
            return self.handle_tool_calls(response, messages, model, tools)
        
        return response.choices[0].message.content
    
    def stream_chat_response(self, messages, model, tools=None, session_id=None):
        """流式聊天响应"""
        kwargs = {
            'model': model,
            'messages': messages,
            'stream': True
        }
        
        if tools:
            kwargs['tools'] = tools
            kwargs['tool_choice'] = 'auto'
        
        try:
            stream = self.openai_client.chat.completions.create(**kwargs)
            
            tool_calls = []
            current_tool_call = None
            
            # 在流式响应结束前，保存助手的完整回复
            assistant_response = ""
        
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    assistant_response += content
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
            
                # 处理工具调用
                if chunk.choices[0].delta.tool_calls:
                    for tool_call in chunk.choices[0].delta.tool_calls:
                        if tool_call.index is not None:
                            # 新的工具调用
                            if tool_call.index >= len(tool_calls):
                                tool_calls.append({
                                    'id': tool_call.id or '',
                                    'function': {'name': '', 'arguments': ''}
                                })
                            current_tool_call = tool_calls[tool_call.index]
                        
                        if tool_call.function:
                            if tool_call.function.name:
                                current_tool_call['function']['name'] += tool_call.function.name
                            if tool_call.function.arguments:
                                current_tool_call['function']['arguments'] += tool_call.function.arguments
            
            # 如果有工具调用，执行它们
            if tool_calls:
                yield f"data: {json.dumps({'type': 'tool_calls', 'tool_calls': tool_calls})}\n\n"
                
                for tool_call in tool_calls:
                    try:
                        tool_name = tool_call['function']['name']
                        tool_args = json.loads(tool_call['function']['arguments'])
                        
                        yield f"data: {json.dumps({'type': 'tool_execution', 'tool_name': tool_name, 'args': tool_args})}\n\n"
                        
                        result = self.mcp_client.execute_tool(tool_name, tool_args)
                        
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': tool_name, 'result': str(result)})}\n\n"
                        
                        # 将工具结果添加到消息中，继续对话
                        messages.append({
                            "role": "assistant",
                            "tool_calls": [tool_call]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call['id'],
                            "content": str(result)
                        })
                        
                    except Exception as e:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'工具执行错误: {str(e)}'})}\n\n"
                

                # 获取最终响应
                final_stream = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True
                )
                
                for chunk in final_stream:
                    if chunk.choices[0].delta.content:
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk.choices[0].delta.content})}\n\n"
            
            # 保存助手回复到会话历史
            if session_id and session_id in self.chat_sessions:
                self.chat_sessions[session_id]['messages'].append({
                    "role": "assistant", 
                    "content": assistant_response
                })
            
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    def handle_tool_calls(self, response, messages, model, tools):
        """处理工具调用（非流式）"""
        tool_calls = response.choices[0].message.tool_calls
        
        # 添加助手的消息到对话历史
        messages.append({
            "role": "assistant",
            "tool_calls": [tc.dict() for tc in tool_calls]
        })
        
        # 执行工具调用
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                result = self.mcp_client.execute_tool(tool_name, tool_args)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })
                
            except Exception as e:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"工具执行错误: {str(e)}"
                })
        
        # 获取最终响应
        final_response = self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
        )
        
        return final_response.choices[0].message.content
    
    def run(self):
        """启动Web服务器"""
        web_config = self.config['web_server']
        logger.info(f"启动Web服务器在 http://{web_config['host']}:{web_config['port']}")
        
        self.app.run(
            host=web_config['host'],
            port=web_config['port'],
            debug=web_config['debug']
        )

if __name__ == '__main__':
    # 确保templates文件夹存在
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # 确保static文件夹存在
    if not os.path.exists('static'):
        os.makedirs('static')
        os.makedirs('static/css')
        os.makedirs('static/js')
    
    try:
        server = WebServer()
        server.run()
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"启动服务器失败: {e}")