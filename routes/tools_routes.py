from flask import Blueprint, request, jsonify
from flask import current_app
import json
import logging

tools_bp = Blueprint('tools', __name__)
logger = logging.getLogger(__name__)

@tools_bp.route('/api/tools')
def get_tools():
    """获取可用工具列表"""
    tool_service = current_app.config['TOOL_SERVICE']
    try:
        if not tool_service.is_mcp_connected():
            return jsonify({
                'error': 'MCP客户端未初始化',
                'tools': [],
                'selected': []
            }), 500

        return jsonify({
            'tools': tool_service.get_available_tools(),
            'selected': tool_service.get_selected_tools()
        })

    except Exception as e:
        logger.error(f"获取工具列表API错误: {e}")
        return jsonify({
            'error': str(e),
            'tools': [],
            'selected': []
        }), 500

@tools_bp.route('/api/tools/select', methods=['POST'])
def select_tools():
    """选择要使用的工具"""
    tool_service = current_app.config['TOOL_SERVICE']
    data = request.get_json()
    tool_service.set_selected_tools(data.get('tools', []))
    return jsonify({'success': True, 'selected_count': len(tool_service.get_selected_tools())})

@tools_bp.route('/api/execute_tool', methods=['POST'])
def execute_tool():
    """执行MCP工具"""
    tool_service = current_app.config['TOOL_SERVICE']
    data = request.get_json()
    tool_name = data.get('tool_name')
    parameters = data.get('parameters', {})

    if not tool_service.is_mcp_connected():
        return jsonify({'error': 'MCP服务器未连接'}), 500

    try:
        result = tool_service.execute_tool(tool_name, parameters)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500