#!/usr/bin/env python3
# app.py - Web后端服务器
import json
import logging
from flask import Flask, render_template, request, jsonify, Response, stream_template, send_file
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
from web_task_scheduler import WebTaskScheduler

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
        
        # 添加中断状态管理
        self.interrupt_flags = {}  # 会话ID -> 是否中断的标志
        self.active_streams = {}   # 会话ID -> 活跃流控制器
        
        # 初始化任务调度器
        self.task_scheduler = WebTaskScheduler(self)
        
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
    
    def get_model_config(self, model_id):
        """获取特定模型的配置"""
        for model in self.config['llm']['models']:
            if model['id'] == model_id:
                return model
        
        # 如果找不到特定模型配置，返回默认配置
        logger.warning(f"未找到模型 {model_id} 的配置，使用第一个模型的配置")
        return self.config['llm']['models'][0]
    
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
        
        @self.app.route('/api/chat/save', methods=['POST'])
        def save_chat():
            """保存对话历史到文件"""
            data = request.get_json()
            session_id = data.get('session_id')
            filename = data.get('filename')
            
            if not session_id or session_id not in self.chat_sessions:
                return jsonify({'error': '会话不存在'}), 404
            
            try:
                # 确保chatSave目录存在
                chat_save_dir = 'chatSave'
                if not os.path.exists(chat_save_dir):
                    os.makedirs(chat_save_dir)
                
                # 生成文件名
                if not filename:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"chat_{timestamp}.json"
                
                if not filename.endswith('.json'):
                    filename += '.json'
                
                # 准备要保存的数据
                session_data = self.chat_sessions[session_id]
                save_data = {
                    'session_id': session_id,
                    'created_at': session_data['created_at'].isoformat(),
                    'last_activity': session_data['last_activity'].isoformat(),
                    'messages': session_data['messages'],
                    'model': None,
                    'selected_tools': self.selected_tools,
                    'system_prompt': data.get('system_prompt', '')
                }
                
                # 保存文件
                file_path = os.path.join(chat_save_dir, filename)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)
                
                return jsonify({
                    'success': True,
                    'filename': filename,
                    'path': file_path,
                    'message_count': len(session_data['messages'])
                })
                
            except Exception as e:
                logger.error(f"保存对话失败: {e}")
                return jsonify({'error': f'保存对话失败: {str(e)}'}), 500
        
        @self.app.route('/api/chat/load', methods=['POST'])
        def load_chat():
            """从文件加载对话历史"""
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({'error': '文件名不能为空'}), 400
            
            try:
                # 确保文件名安全
                filename = os.path.basename(filename)
                if not filename.endswith('.json'):
                    filename += '.json'
                
                file_path = os.path.join('chatSave', filename)
                
                if not os.path.exists(file_path):
                    return jsonify({'error': '文件不存在'}), 404
                
                # 加载文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)
                
                # 创建新会话
                session_id = str(uuid.uuid4())
                self.chat_sessions[session_id] = {
                    'messages': save_data.get('messages', []),
                    'created_at': datetime.fromisoformat(save_data.get('created_at', datetime.now().isoformat())),
                    'last_activity': datetime.now()
                }
                
                return jsonify({
                    'success': True,
                    'session_id': session_id,
                    'messages': save_data.get('messages', []),
                    'model': save_data.get('model'),
                    'selected_tools': save_data.get('selected_tools', []),
                    'system_prompt': save_data.get('system_prompt', '')
                })
                
            except Exception as e:
                logger.error(f"加载对话失败: {e}")
                return jsonify({'error': f'加载对话失败: {str(e)}'}), 500
        
        @self.app.route('/api/chat/list', methods=['GET'])
        def list_saved_chats():
            """获取已保存的对话列表"""
            try:
                chat_save_dir = 'chatSave'
                if not os.path.exists(chat_save_dir):
                    return jsonify({'files': []})
                
                files = []
                for filename in os.listdir(chat_save_dir):
                    if filename.endswith('.json'):
                        file_path = os.path.join(chat_save_dir, filename)
                        try:
                            stat = os.stat(file_path)
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                files.append({
                                    'filename': filename,
                                    'size': stat.st_size,
                                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                    'message_count': len(data.get('messages', [])),
                                    'created_at': data.get('created_at', ''),
                                    'model': data.get('model', ''),
                                    'selected_tools_count': len(data.get('selected_tools', [])),
                                    'has_system_prompt': bool(data.get('system_prompt', '').strip())
                                })
                        except Exception as e:
                            logger.warning(f"读取文件信息失败: {filename}, {e}")
                            files.append({
                                'filename': filename,
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                'error': str(e)
                            })
                
                # 按修改时间排序，最新的在前
                files.sort(key=lambda x: x['modified'], reverse=True)
                return jsonify({'files': files})
                
            except Exception as e:
                logger.error(f"获取对话列表失败: {e}")
                return jsonify({'error': f'获取对话列表失败: {str(e)}'}), 500
        
        @self.app.route('/api/chat/delete', methods=['POST'])
        def delete_chat():
            """删除已保存的对话文件"""
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({'error': '文件名不能为空'}), 400
            
            try:
                # 确保文件名安全
                filename = os.path.basename(filename)
                if not filename.endswith('.json'):
                    filename += '.json'
                
                file_path = os.path.join('chatSave', filename)
                
                if not os.path.exists(file_path):
                    return jsonify({'error': '文件不存在'}), 404
                
                os.remove(file_path)
                return jsonify({'success': True})
                
            except Exception as e:
                logger.error(f"删除对话失败: {e}")
                return jsonify({'error': f'删除对话失败: {str(e)}'}), 500
        
        @self.app.route('/api/chat/interrupt', methods=['POST'])
        def interrupt_chat():
            """中断当前对话"""
            data = request.get_json()
            session_id = data.get('session_id')
            
            if session_id and session_id in self.interrupt_flags:
                # 设置中断标志
                self.interrupt_flags[session_id] = True
                
                # 如果有活跃流，尝试关闭
                if session_id in self.active_streams:
                    try:
                        self.active_streams[session_id].close()
                        del self.active_streams[session_id]
                    except Exception as e:
                        logger.warning(f"关闭流时出错: {e}")
                
                # 移除最后一条助手消息和最后一条用户消息（如果存在）
                if session_id in self.chat_sessions:
                    messages = self.chat_sessions[session_id]['messages']
                    removed_messages = 0
                    
                    # 先移除最后一条助手消息
                    if messages and messages[-1]['role'] == 'assistant':
                        messages.pop()
                        removed_messages += 1
                    
                    # 再移除最后一条用户消息
                    if messages and messages[-1]['role'] == 'user':
                        messages.pop()
                        removed_messages += 1
                    
                    logger.info(f"对话中断：已移除 {removed_messages} 条消息")
                
                return jsonify({'success': True, 'message': '对话已中断', 'removed_messages': removed_messages})
            
            return jsonify({'error': '会话不存在或无需中断'}), 404
        
        # 任务调度系统路由
        @self.app.route('/tasks')
        def tasks_page():
            """任务管理页面"""
            return render_template('tasks.html')
        
        @self.app.route('/api/tasks')
        def get_tasks():
            """获取所有任务"""
            try:
                tasks = self.task_scheduler.get_all_tasks()
                return jsonify({
                    'success': True,
                    'tasks': [task.to_dict() for task in tasks]
                })
            except Exception as e:
                logger.error(f"获取任务列表失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks', methods=['POST'])
        def create_task():
            """创建新任务"""
            try:
                data = request.get_json()
                
                task_id = self.task_scheduler.create_task(
                    name=data['name'],
                    prompt=data['prompt'],
                    user_input=data['user_input'],
                    tools=data['tools'],
                    model=data['model'],
                    interval_minutes=data['interval_minutes'],
                    max_executions=data['max_executions']
                )
                
                return jsonify({
                    'success': True,
                    'task_id': task_id
                })
                
            except Exception as e:
                logger.error(f"创建任务失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/<task_id>', methods=['DELETE'])
        def delete_task(task_id):
            """删除任务"""
            try:
                success = self.task_scheduler.delete_task(task_id)
                return jsonify({
                    'success': success,
                    'message': '任务已删除' if success else '任务不存在'
                })
            except Exception as e:
                logger.error(f"删除任务失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/<task_id>/status', methods=['PUT'])
        def update_task_status(task_id):
            """更新任务状态"""
            try:
                data = request.get_json()
                success = self.task_scheduler.update_task(task_id, is_active=data['is_active'])
                return jsonify({
                    'success': success,
                    'message': '任务状态已更新' if success else '任务不存在'
                })
            except Exception as e:
                logger.error(f"更新任务状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/<task_id>', methods=['PUT'])
        def update_task(task_id):
            """更新任务"""
            try:
                data = request.get_json()
                
                # 验证必填字段
                required_fields = ['name', 'prompt', 'user_input', 'tools', 'model', 'interval_minutes', 'max_executions']
                for field in required_fields:
                    if field not in data:
                        return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400
                
                # 更新任务
                success = self.task_scheduler.update_task(
                    task_id,
                    name=data['name'],
                    prompt=data['prompt'],
                    user_input=data['user_input'],
                    tools=data['tools'],
                    model=data['model'],
                    interval_minutes=data['interval_minutes'],
                    max_executions=data['max_executions'],
                    updated_at=datetime.now().isoformat()
                )
                
                return jsonify({
                    'success': success,
                    'message': '任务已更新' if success else '任务不存在'
                })
                
            except Exception as e:
                logger.error(f"更新任务失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/scheduler/start', methods=['POST'])
        def start_scheduler():
            """启动任务调度器"""
            try:
                self.task_scheduler.start_scheduler()
                return jsonify({
                    'success': True,
                    'message': '任务调度器已启动'
                })
            except Exception as e:
                logger.error(f"启动调度器失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/scheduler/stop', methods=['POST'])
        def stop_scheduler():
            """停止任务调度器"""
            try:
                self.task_scheduler.stop_scheduler()
                return jsonify({
                    'success': True,
                    'message': '任务调度器已停止'
                })
            except Exception as e:
                logger.error(f"停止调度器失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/scheduler/status')
        def get_scheduler_status():
            """获取调度器状态"""
            try:
                status = self.task_scheduler.get_scheduler_status()
                return jsonify({
                    'success': True,
                    **status
                })
            except Exception as e:
                logger.error(f"获取调度器状态失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/executions')
        def get_executions():
            """获取执行历史"""
            try:
                executions = self.task_scheduler.get_execution_history()
                return jsonify({
                    'success': True,
                    'executions': [exec.to_dict() for exec in executions]
                })
            except Exception as e:
                logger.error(f"获取执行历史失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/<task_id>/reset', methods=['POST'])
        def reset_task_executions(task_id):
            """重置任务执行次数"""
            try:
                success = self.task_scheduler.reset_task_executions(task_id)
                return jsonify({
                    'success': success,
                    'message': '任务已重置' if success else '任务不存在'
                })
            except Exception as e:
                logger.error(f"重置任务失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/<task_id>/execution/latest')
        def get_latest_execution(task_id):
            """获取任务最新的执行记录"""
            try:
                executions = self.task_scheduler.get_execution_history(task_id)
                if not executions:
                    return jsonify({'success': False, 'error': '暂无执行记录'}), 404
                
                latest = executions[0]  # 最新的记录
                
                # 如果存在聊天文件，读取详细内容
                execution_data = latest.to_dict()
                if latest.chat_file:
                    chat_path = os.path.join(self.task_scheduler.chat_save_dir, latest.chat_file)
                    if os.path.exists(chat_path):
                        with open(chat_path, 'r', encoding='utf-8') as f:
                            chat_data = json.load(f)
                        execution_data['chat_data'] = chat_data
                
                return jsonify({
                    'success': True,
                    'execution': execution_data
                })
                
            except Exception as e:
                logger.error(f"获取最新执行记录失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/executions/<filename>/download')
        def download_execution_chat(filename):
            """下载任务执行的聊天记录"""
            try:
                file_path = os.path.join(self.task_scheduler.chat_save_dir, filename)
                if not os.path.exists(file_path):
                    return jsonify({'success': False, 'error': '文件不存在'}), 404
                
                return send_file(file_path, as_attachment=True, download_name=filename)
            except Exception as e:
                logger.error(f"下载聊天记录失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/executions/recent')
        def get_recent_executions():
            """获取最近的执行记录"""
            try:
                limit = request.args.get('limit', 50, type=int)
                
                # 获取所有执行记录
                all_executions = self.task_scheduler.get_execution_history()
                
                # 按时间排序，最新的在前
                all_executions.sort(key=lambda x: x.start_time, reverse=True)
                
                # 限制数量
                recent_executions = all_executions[:limit]
                
                # 加载详细的聊天数据
                executions_with_data = []
                for exec in recent_executions:
                    exec_data = exec.to_dict()
                    
                    # 加载对应的聊天文件
                    if exec.chat_file:
                        chat_path = os.path.join(self.task_scheduler.chat_save_dir, exec.chat_file)
                        if os.path.exists(chat_path):
                            try:
                                with open(chat_path, 'r', encoding='utf-8') as f:
                                    chat_data = json.load(f)
                                exec_data['chat_data'] = chat_data
                            except Exception as e:
                                logger.warning(f"加载聊天文件失败: {exec.chat_file}, {e}")
                    
                    executions_with_data.append(exec_data)
                
                return jsonify({
                    'success': True,
                    'executions': executions_with_data
                })
                
            except Exception as e:
                logger.error(f"获取最近执行记录失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/executions/<execution_id>/detail')
        def get_execution_detail(execution_id):
            """获取执行记录的详细信息"""
            try:
                # 获取所有执行记录
                executions = self.task_scheduler.get_execution_history()
                
                # 查找对应的执行记录
                execution = None
                for exec in executions:
                    if exec.id == execution_id:
                        execution = exec
                        break
                
                if not execution:
                    return jsonify({'success': False, 'error': '执行记录不存在'}), 404
                
                execution_data = execution.to_dict()
                
                # 加载对应的聊天文件
                if execution.chat_file:
                    chat_path = os.path.join(self.task_scheduler.chat_save_dir, execution.chat_file)
                    if os.path.exists(chat_path):
                        try:
                            with open(chat_path, 'r', encoding='utf-8') as f:
                                chat_data = json.load(f)
                            execution_data['chat_data'] = chat_data
                        except Exception as e:
                            logger.warning(f"加载聊天文件失败: {execution.chat_file}, {e}")
                
                return jsonify({
                    'success': True,
                    'execution': execution_data
                })
                
            except Exception as e:
                logger.error(f"获取执行详情失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/executions/file/<filename>')
        def get_execution_file(filename):
            """获取指定执行文件的详细信息"""
            try:
                # 确保文件名安全
                filename = os.path.basename(filename)
                file_path = os.path.join(self.task_scheduler.chat_save_dir, filename)
                
                if not os.path.exists(file_path):
                    return jsonify({'success': False, 'error': '执行文件不存在'}), 404
                
                # 加载执行文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    execution_data = json.load(f)
                
                # 构建执行记录对象
                execution_record = {
                    'id': execution_data.get('execution_id', 'unknown'),
                    'task_name': execution_data.get('task_name', 'unknown'),
                    'start_time': execution_data.get('start_time', ''),
                    'end_time': execution_data.get('end_time', ''),
                    'status': execution_data.get('status', 'completed'),
                    'chat_data': execution_data
                }
                
                return jsonify({
                    'success': True,
                    'execution': execution_record
                })
                
            except Exception as e:
                logger.error(f"获取执行文件失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/tasks/executions/file/<filename>/summary')
        def get_execution_file_summary(filename):
            """获取指定执行文件的摘要信息"""
            try:
                # 确保文件名安全
                filename = os.path.basename(filename)
                file_path = os.path.join(self.task_scheduler.chat_save_dir, filename)
                
                if not os.path.exists(file_path):
                    return jsonify({'success': False, 'error': '执行文件不存在'}), 404
                
                # 加载执行文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    execution_data = json.load(f)
                
                # 构建摘要信息
                summary = {
                    'id': execution_data.get('execution_id', 'unknown'),
                    'task_name': execution_data.get('task_name', 'unknown'),
                    'start_time': execution_data.get('start_time', ''),
                    'end_time': execution_data.get('end_time', ''),
                    'status': execution_data.get('status', 'completed'),
                    'duration': execution_data.get('duration', '')
                }
                
                return jsonify({
                    'success': True,
                    'execution': summary
                })
                
            except Exception as e:
                logger.error(f"获取执行文件摘要失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
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
        
        # 获取模型特定配置
        model_config = self.get_model_config(model)
        openai_client = OpenAI(
            api_key=model_config['api_key'],
            base_url=model_config['base_url']
        )

        response = openai_client.chat.completions.create(**kwargs)
        
        # 处理工具调用
        if response.choices[0].message.tool_calls:
            return self.handle_tool_calls(response, messages, model, tools)
        
        return response.choices[0].message.content
    
    # 修复工具调用显示和消息解码问题
    def stream_chat_response(self, messages, model, tools=None, session_id=None):
        """流式聊天响应"""
        # 设置中断标志为False
        if session_id:
            self.interrupt_flags[session_id] = False
            
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
            # 获取模型特定配置
            model_config = self.get_model_config(model)
            openai_client = OpenAI(
                api_key=model_config['api_key'],
                base_url=model_config['base_url']
            )

            stream = openai_client.chat.completions.create(**kwargs)
            
            # 记录活跃流
            if session_id:
                self.active_streams[session_id] = stream
            
            # 明确指定utf-8编码并处理GBK编码问题
            def encode_json(data):
                try:
                    return json.dumps(data, ensure_ascii=False).encode('utf-8')
                except UnicodeEncodeError as e:
                    # 如果遇到编码错误，使用转义序列或替换字符
                    safe_data = json.dumps(data, ensure_ascii=True).encode('utf-8')
                    return safe_data
            
            # 在流式响应结束前，保存助手的完整回复
            assistant_response = ""
            
            reasoning_content = ""  # 定义完整思考过程
            answer_content = ""  # 定义完整回复
            tool_info = []  # 存储工具调用信息
            is_answering = False  # 判断是否结束思考过程并开始回复
            localMessages = messages  # 局部交流池

            print("=" * 20 + "思考过程" + "=" * 20)
            yield b"data: " + encode_json({'type': 'content', 'content': '=' * 20 + '思考过程' + '=' * 20 + '\n'}) + b"\n\n"
            
            for chunk in stream:
                # 检查中断标志
                if session_id and self.interrupt_flags.get(session_id, False):
                    print(f"\n检测到中断请求，停止会话 {session_id}")
                    yield b"data: " + encode_json({'type': 'interrupted', 'message': '对话已被用户中断'}) + b"\n\n"
                    break
                    
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
                        yield b"data: " + encode_json({'type': 'content', 'content': delta.reasoning_content}) + b"\n\n"

                    # 处理最终回复内容
                    else:
                        if not is_answering:  # 首次进入回复阶段时打印标题
                            is_answering = True
                            print("\n" + "=" * 20 + "回复内容" + "=" * 20)
                            yield b"data: " + encode_json({'type': 'content', 'content': '\n' + '=' * 20 + '回复内容' + '=' * 20 + '\n'}) + b"\n\n"
                        
                        if delta.content is not None:
                            answer_content += delta.content
                            print(delta.content, end="", flush=True)  # 流式输出回复内容
                            yield b"data: " + encode_json({'type': 'content', 'content': delta.content}) + b"\n\n"

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
                # 检查中断标志
                if session_id and self.interrupt_flags.get(session_id, False):
                    print(f"\n检测到中断请求，停止工具执行会话 {session_id}")
                    yield b"data: " + encode_json({'type': 'interrupted', 'message': '对话已被用户中断'}) + b"\n\n"
                    break
                    
                print("\n开始工具调用")
                
                # 构建助手消息
                if answer_content != "":
                #    assistantMessage = {"role": "assistant", "content": reasoning_content}
                   assistantMessage = {"role": "assistant", "content": answer_content}
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
                yield b"data: " + encode_json({'type': 'tool_calls', 'tool_calls': tool_calls_for_frontend}) + b"\n\n"
                
                # 执行工具调用
                print("工具数量："+str(len(tool_info)))
                for i in range(len(tool_info)):
                    # 检查中断标志
                    if session_id and self.interrupt_flags.get(session_id, False):
                        print(f"\n检测到中断请求，停止工具执行会话 {session_id}")
                        yield b"data: " + encode_json({'type': 'interrupted', 'message': '对话已被用户中断'}) + b"\n\n"
                        break
                        
                    tool = tool_info[i]
                    try:
                        tool_args = json.loads(tool["arguments"])
                        tool_name = tool["name"]
                        tool_call_id = tool["id"]
                        
                        print(f"执行工具: {tool_name}, 参数: {tool_args}")
                        
                        # 发送工具执行通知
                        yield b"data: " + encode_json({'type': 'tool_execution', 'tool_name': tool_name, 'tool_call_id': tool_call_id, 'args': tool_args}) + b"\n\n"
                        
                        # 执行工具
                        result = self.mcp_client.execute_tool(tool_name, tool_args)
                        
                        print(f"工具执行结果: {result}")
                        
                        # 发送工具结果
                        yield b"data: " + encode_json({'type': 'tool_result', 'tool_name': tool_name, 'tool_call_id': tool_call_id, 'result': str(result)}) + b"\n\n"
                        
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
                        yield b"data: " + encode_json({'type': 'tool_result', 'tool_name': tool_name, 'tool_call_id': tool_call_id, 'result': error_msg}) + b"\n\n"
                        localMessages.append({"role": "tool", "tool_call_id": tool_call_id, "content": error_msg})
                
                # 检查中断标志
                if session_id and self.interrupt_flags.get(session_id, False):
                    print(f"\n检测到中断请求，跳过工具执行后的对话会话 {session_id}")
                    yield b"data: " + encode_json({'type': 'interrupted', 'message': '对话已被用户中断'}) + b"\n\n"
                    break
                    
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
                

                # 获取模型特定配置
                model_config = self.get_model_config(model)
                openai_client = OpenAI(
                    api_key=model_config['api_key'],
                    base_url=model_config['base_url']
                )
                stream = openai_client.chat.completions.create(**localKwargs)
                
                # 记录活跃流
                if session_id:
                    self.active_streams[session_id] = stream
                
                print("\n" + "=" * 20 + "思考过程" + "=" * 20)
                yield b"data: " + encode_json({'type': 'content', 'content': '\n' + '=' * 20 + '思考过程' + '=' * 20 + '\n'}) + b"\n\n"
                
                for chunk in stream:
                    print(chunk)
                    print(stream)
                    # 检查中断标志
                    if session_id and self.interrupt_flags.get(session_id, False):
                        print(f"\n检测到中断请求，停止会话 {session_id}")
                        yield b"data: " + encode_json({'type': 'interrupted', 'message': '对话已被用户中断'}) + b"\n\n"
                        break
                        
                    if not chunk.choices:
                        print("\n" + "=" * 20 + "Usage" + "=" * 20)
                        print(chunk.usage)
                    else:
                        delta = chunk.choices[0].delta
                        
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                            reasoning_content += delta.reasoning_content
                            print(delta.reasoning_content, end="", flush=True)
                            yield b"data: " + encode_json({'type': 'content', 'content': delta.reasoning_content}) + b"\n\n"
                        else:
                            if not is_answering:
                                is_answering = True
                                print("\n" + "=" * 20 + "回复内容" + "=" * 20)
                                yield b"data: " + encode_json({'type': 'content', 'content': '\n' + '=' * 20 + '回复内容' + '=' * 20 + '\n'}) + b"\n\n"
                            
                            if delta.content is not None:
                                answer_content += delta.content
                                print(delta.content, end="", flush=True)
                                yield b"data: " + encode_json({'type': 'content', 'content': delta.content}) + b"\n\n"

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
            
            # 保存助手回复到会话历史（只有在没有被中断的情况下）
            if session_id and session_id in self.chat_sessions and not self.interrupt_flags.get(session_id, False):
                final_content = answer_content if answer_content else reasoning_content
                if final_content.strip():  # 只有非空内容才保存
                    self.chat_sessions[session_id]['messages'].append({
                        "role": "assistant", 
                        "content": final_content
                    })
            
            yield b"data: " + encode_json({'type': 'end'}) + b"\n\n"
            
        except Exception as e:
            error_msg = f"流式响应错误: {str(e)}"
            print(f"流式响应错误: {e}")
            yield b"data: " + encode_json({'type': 'error', 'message': error_msg}) + b"\n\n"
        finally:
            # 清理会话状态
            if session_id:
                # 清除中断标志
                self.interrupt_flags.pop(session_id, None)
                # 清除活跃流引用
                self.active_streams.pop(session_id, None)

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
        
        # 获取模型特定配置
        model_config = self.get_model_config(model)
        openai_client = OpenAI(
            api_key=model_config['api_key'],
            base_url=model_config['base_url']
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