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
        # self.openai_client = OpenAI(
        #     api_key=self.config['llm']['api_key'],
        #     base_url=self.config['llm']['base_url']
        # )
        
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
        
        # 在 chat 路由中添加系统提示词支持，修改部分：
        @self.app.route('/api/chat', methods=['POST'])
        def chat():
            """处理聊天请求"""
            data = request.get_json()
            message = data.get('message', '')
            model = data.get('model', self.config['llm']['default_model'])
            session_id = data.get('session_id')  # 从请求中获取会话ID
            custom_system_prompt = data.get('system_prompt', '')  # 获取自定义系统提示词
            
            if not message.strip():
                return jsonify({'error': '消息不能为空'}), 400
            
            # 获取或创建会话
            session_id, session = self.get_or_create_session(session_id)
            
            # 构建包含历史的消息列表
            system_prompt = self.build_system_prompt()
            if custom_system_prompt:
                system_prompt = custom_system_prompt + "\n\n" + system_prompt
            
            messages = [{"role": "system", "content": system_prompt}]
            
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
        
        openai_client = OpenAI(
            api_key=self.config['llm']['api_key'],
            base_url=self.config['llm']['base_url']
        )

        response = openai_client.chat.completions.create(**kwargs)
        
        # 处理工具调用
        if response.choices[0].message.tool_calls:
            return self.handle_tool_calls(response, messages, model, tools)
        
        return response.choices[0].message.content
    
    # 修复工具调用显示和消息解码问题
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
            kwargs['parallel_tool_calls'] = True
        
        try:
            openai_client = OpenAI(
                api_key=self.config['llm']['api_key'],
                base_url=self.config['llm']['base_url']
            )

            stream = openai_client.chat.completions.create(**kwargs)
            
            # 明确指定utf-8编码
            def encode_json(data):
                return json.dumps(data, ensure_ascii=False).encode('utf-8')
            
            # 在流式响应结束前，保存助手的完整回复
            assistant_response = ""
            
            reasoning_content = ""  # 定义完整思考过程
            answer_content = ""  # 定义完整回复
            tool_info = []  # 存储工具调用信息
            is_answering = False  # 判断是否结束思考过程并开始回复
            localMessages = messages  # 局部交流池

            print("=" * 20 + "思考过程" + "=" * 20)
            yield f"data: {json.dumps({'type': 'content', 'content': '=' * 20 + '思考过程' + '=' * 20 + '\n'}, ensure_ascii=False)}\n\n"
            
            for chunk in stream:
                if not chunk.choices:
                    # 处理用量统计信息
                    print("\n" + "=" * 20 + "Usage" + "=" * 20)
                    print(chunk.usage)
                else:
                    delta = chunk.choices[0].delta
                    # 处理AI的思考过程（链式推理）
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                        reasoning_content += delta.reasoning_content
                        print(delta.reasoning_content, end="", flush=True)  # 实时输出思考过程
                        yield f"data: {json.dumps({'type': 'content', 'content': delta.reasoning_content}, ensure_ascii=False)}\n\n"

                    # 处理最终回复内容
                    else:
                        if not is_answering:  # 首次进入回复阶段时打印标题
                            is_answering = True
                            print("\n" + "=" * 20 + "回复内容" + "=" * 20)
                            yield f"data: {json.dumps({'type': 'content', 'content': '\n' + '=' * 20 + '回复内容' + '=' * 20 + '\n'}, ensure_ascii=False)}\n\n"
                        
                        if delta.content is not None:
                            answer_content += delta.content
                            print(delta.content, end="", flush=True)  # 流式输出回复内容
                            yield f"data: {json.dumps({'type': 'content', 'content': delta.content}, ensure_ascii=False)}\n\n"

                        # 处理工具调用信息（支持并行工具调用）
                        if delta.tool_calls is not None:
                            print(delta.tool_calls)
                            for tool_call in delta.tool_calls:
                                index = tool_call.index  # 工具调用索引，用于并行调用

                                # 动态扩展工具信息存储列表
                                while len(tool_info) <= index:
                                    tool_info.append({})

                                # 收集工具调用ID（用于后续函数调用）
                                if tool_call.id:
                                    tool_info[index]['id'] = tool_info[index].get('id', '') + tool_call.id

                                # 收集函数名称（用于后续路由到具体函数）
                                if tool_call.function and tool_call.function.name:
                                    tool_info[index]['name'] = tool_info[index].get('name', '') + tool_call.function.name

                                # 收集函数参数（JSON字符串格式，需要后续解析）
                                if tool_call.function and tool_call.function.arguments:
                                    tool_info[index]['arguments'] = tool_info[index].get('arguments', '') + tool_call.function.arguments
            
            print(tool_info)
            # 工具调用循环
            while len(tool_info) > 0:
                print("\n开始工具调用")
                
                # 构建助手消息
                if answer_content == "":
                    assistantMessage = {"role": "assistant", "content": reasoning_content}
                else:
                    assistantMessage = {"role": "assistant", "content": answer_content}
                assistantMessage["tool_calls"] = []
                localMessages.append(assistantMessage)
                
                # 发送工具调用开始通知 - 修复工具调用显示
                tool_calls_for_frontend = []
                for i in range(len(tool_info)):
                    tool = tool_info[i]
                    tool_calls_for_frontend.append({
                        "id": tool["id"],
                        "function": {
                            "name": tool["name"],
                            "arguments": tool["arguments"]
                        }
                    })
                
                # 发送工具调用通知
                yield f"data: {json.dumps({'type': 'tool_calls', 'tool_calls': tool_calls_for_frontend}, ensure_ascii=False)}\n\n"
                
                # 执行工具调用
                print("工具数量："+str(len(tool_info)))
                for i in range(len(tool_info)):
                    tool = tool_info[i]
                    try:
                        tool_args = json.loads(tool["arguments"])
                        tool_name = tool["name"]
                        tool_call_id = tool["id"]
                        
                        print(f"执行工具: {tool_name}, 参数: {tool_args}")
                        
                        # 发送工具执行通知
                        yield f"data: {json.dumps({'type': 'tool_execution', 'tool_name': tool_name, 'tool_call_id': tool_call_id, 'args': tool_args}, ensure_ascii=False)}\n\n"
                        
                        # 执行工具
                        result = self.mcp_client.execute_tool(tool_name, tool_args)
                        
                        print(f"工具执行结果: {result}")
                        
                        # 发送工具结果
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': tool_name, 'tool_call_id': tool_call_id, 'result': str(result)}, ensure_ascii=False)}\n\n"
                        
                        # 更新消息历史
                        assistantMessage["tool_calls"].append({
                            "id": tool_call_id,
                            "function": {"arguments": tool["arguments"], "name": tool["name"]},
                            "type": 'function'
                        })
                        localMessages.append({"role": "tool", "tool_call_id": tool_call_id, "content": str(result)})
                        
                    except Exception as e:
                        error_msg = f"工具执行错误: {str(e)}"
                        print(f"工具执行错误: {e}")
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': tool_name, 'tool_call_id': tool_call_id, 'result': error_msg}, ensure_ascii=False)}\n\n"
                        localMessages.append({"role": "tool", "tool_call_id": tool_call_id, "content": error_msg})
                
                # 继续进行对话
                reasoning_content = ""
                answer_content = ""
                tool_info = []
                is_answering = False

                localKwargs = {
                    'model': model,
                    'messages': localMessages,
                    'stream': True
                }
                
                if tools:
                    localKwargs['tools'] = tools
                    localKwargs['tool_choice'] = 'auto'
                

                openai_client = OpenAI(
                    api_key=self.config['llm']['api_key'],
                    base_url=self.config['llm']['base_url']
                )
                stream = openai_client.chat.completions.create(**localKwargs)
                
                print("\n" + "=" * 20 + "思考过程" + "=" * 20)
                yield f"data: {json.dumps({'type': 'content', 'content': '\n' + '=' * 20 + '思考过程' + '=' * 20 + '\n'}, ensure_ascii=False)}\n\n"
                
                for chunk in stream:
                    if not chunk.choices:
                        print("\n" + "=" * 20 + "Usage" + "=" * 20)
                        print(chunk.usage)
                    else:
                        delta = chunk.choices[0].delta
                        
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                            reasoning_content += delta.reasoning_content
                            print(delta.reasoning_content, end="", flush=True)
                            yield f"data: {json.dumps({'type': 'content', 'content': delta.reasoning_content}, ensure_ascii=False)}\n\n"
                        else:
                            if not is_answering:
                                is_answering = True
                                print("\n" + "=" * 20 + "回复内容" + "=" * 20)
                                yield f"data: {json.dumps({'type': 'content', 'content': '\n' + '=' * 20 + '回复内容' + '=' * 20 + '\n'}, ensure_ascii=False)}\n\n"
                            
                            if delta.content is not None:
                                answer_content += delta.content
                                print(delta.content, end="", flush=True)
                                yield f"data: {json.dumps({'type': 'content', 'content': delta.content}, ensure_ascii=False)}\n\n"

                            if delta.tool_calls is not None:
                                for tool_call in delta.tool_calls:
                                    index = tool_call.index
                                    while len(tool_info) <= index:
                                        tool_info.append({})
                                    if tool_call.id:
                                        tool_info[index]['id'] = tool_info[index].get('id', '') + tool_call.id
                                    if tool_call.function and tool_call.function.name:
                                        tool_info[index]['name'] = tool_info[index].get('name', '') + tool_call.function.name
                                    if tool_call.function and tool_call.function.arguments:
                                        tool_info[index]['arguments'] = tool_info[index].get('arguments', '') + tool_call.function.arguments
            
            # 保存助手回复到会话历史
            if session_id and session_id in self.chat_sessions:
                final_content = answer_content if answer_content else reasoning_content
                self.chat_sessions[session_id]['messages'].append({
                    "role": "assistant", 
                    "content": final_content
                })
            
            yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            error_msg = f"流式响应错误: {str(e)}"
            print(f"流式响应错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"

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
        openai_client = OpenAI(
            api_key=self.config['llm']['api_key'],
            base_url=self.config['llm']['base_url']
        )
        final_response = openai_client.chat.completions.create(
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