from flask import Blueprint, request, jsonify, Response, send_file
from flask import current_app
import json
import os
from datetime import datetime
import uuid
import logging

chat_bp = Blueprint('chat', __name__)
logger = logging.getLogger(__name__)

@chat_bp.route('/api/chat', methods=['POST'])
def chat():
    """处理聊天请求"""
    config_service = current_app.config['CONFIG_SERVICE']
    tool_service = current_app.config['TOOL_SERVICE']
    session_service = current_app.config['SESSION_SERVICE']
    chat_service = current_app.config['CHAT_SERVICE']

    data = request.get_json()
    message = data.get('message', '')
    model = data.get('model', config_service.get_default_model())
    session_id = data.get('session_id')
    custom_system_prompt = data.get('system_prompt', '')

    if not message.strip():
        return jsonify({'error': '消息不能为空'}), 400

    try:
        # 获取或创建会话
        session_id, session = session_service.get_or_create_session(session_id)
    except Exception as e:
        # 检查是否是会话清理异常
        if "会话已被清理" in str(e):
            return jsonify({
                'error': str(e),
                'code': 'SESSION_EXPIRED'
            }), 410  # 410 Gone 状态码
        # 其他异常
        logger.error(f"会话创建错误: {e}")
        return jsonify({'error': str(e)}), 500

    # 构建包含历史的消息列表
    system_prompt = tool_service.build_system_prompt()
    if custom_system_prompt:
        system_prompt = custom_system_prompt + "\n\n" + system_prompt

    messages = [{"role": "system", "content": system_prompt}]

    # 添加历史消息
    messages.extend(session['messages'])

    # 添加当前用户消息
    messages.append({"role": "user", "content": message})

    tools = tool_service.build_tools_definition() if tool_service.get_selected_tools() else None

    try:
        # 保存用户消息到历史
        session_service.add_user_message(session_id, message)

        # 获取模型特定的stream配置
        model_config = config_service.get_model_config(model)
        stream_enabled = model_config.get('stream', False)

        if stream_enabled:
            return Response(
                chat_service.stream_chat_response(messages, model, tools, session_id),
                mimetype='text/plain',
                headers={'X-Session-ID': session_id}
            )
        else:
            # get_chat_response现在也是流式返回
            return Response(
                chat_service.get_chat_response(messages, model, tools, session_id),
                mimetype='text/plain',
                headers={'X-Session-ID': session_id}
            )

    except Exception as e:
        logger.error(f"聊天处理错误: {e}")
        return jsonify({'error': f'处理请求时出错: {str(e)}'}), 500

@chat_bp.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    """清空对话历史"""
    session_service = current_app.config['SESSION_SERVICE']
    data = request.get_json()
    session_id = data.get('session_id')

    if session_service.clear_session(session_id):
        return jsonify({'success': True})

    return jsonify({'error': '会话不存在'}), 404

@chat_bp.route('/api/chat/save', methods=['POST'])
def save_chat():
    """保存对话历史到文件"""
    session_service = current_app.config['SESSION_SERVICE']
    tool_service = current_app.config['TOOL_SERVICE']
    data = request.get_json()
    session_id = data.get('session_id')
    filename = data.get('filename')

    try:
        result = session_service.save_session_to_file(
            session_id=session_id,
            filename=filename,
            system_prompt=data.get('system_prompt', ''),
            selected_tools=tool_service.get_selected_tools()
        )

        return jsonify({
            'success': True,
            'filename': result['filename'],
            'path': result['path'],
            'message_count': result['message_count']
        })

    except Exception as e:
        logger.error(f"保存对话失败: {e}")
        return jsonify({'error': f'保存对话失败: {str(e)}'}), 500

@chat_bp.route('/api/chat/load', methods=['POST'])
def load_chat():
    """从文件加载对话历史"""
    session_service = current_app.config['SESSION_SERVICE']
    data = request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({'error': '文件名不能为空'}), 400

    try:
        result = session_service.load_session_from_file(filename)

        return jsonify({
            'success': True,
            'session_id': result['session_id'],
            'messages': result['messages'],
            'model': result['model'],
            'selected_tools': result['selected_tools'],
            'system_prompt': result['system_prompt']
        })

    except Exception as e:
        logger.error(f"加载对话失败: {e}")
        return jsonify({'error': f'加载对话失败: {str(e)}'}), 500

@chat_bp.route('/api/chat/list', methods=['GET'])
def list_saved_chats():
    """获取已保存的对话列表"""
    session_service = current_app.config['SESSION_SERVICE']

    try:
        files = session_service.list_saved_sessions()
        return jsonify({'files': files})

    except Exception as e:
        logger.error(f"获取对话列表失败: {e}")
        return jsonify({'error': f'获取对话列表失败: {str(e)}'}), 500

@chat_bp.route('/api/chat/delete', methods=['POST'])
def delete_chat():
    """删除已保存的对话文件"""
    session_service = current_app.config['SESSION_SERVICE']
    data = request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({'error': '文件名不能为空'}), 400

    try:
        if session_service.delete_saved_session(filename):
            return jsonify({'success': True})
        else:
            return jsonify({'error': '文件不存在'}), 404

    except Exception as e:
        logger.error(f"删除对话失败: {e}")
        return jsonify({'error': f'删除对话失败: {str(e)}'}), 500

@chat_bp.route('/api/chat/interrupt', methods=['POST'])
def interrupt_chat():
    """中断当前对话"""
    chat_service = current_app.config['CHAT_SERVICE']
    session_service = current_app.config['SESSION_SERVICE']
    data = request.get_json()
    session_id = data.get('session_id')

    if session_id:
        # 设置中断标志
        chat_service.interrupt_chat(session_id)

        # 移除最后一条助手消息和最后一条用户消息（如果存在）
        removed_messages = 0
        session = session_service.get_session(session_id)
        if session:
            messages = session['messages']

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