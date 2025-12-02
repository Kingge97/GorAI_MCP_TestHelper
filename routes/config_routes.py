from flask import Blueprint, jsonify
from flask import current_app

config_bp = Blueprint('config', __name__)

@config_bp.route('/api/config')
def get_config():
    """获取配置信息"""
    config_service = current_app.config['CONFIG_SERVICE']
    return jsonify(config_service.get_config_summary())

@config_bp.route('/api/debug/status')
def debug_status():
    """调试状态检查"""
    config_service = current_app.config['CONFIG_SERVICE']
    tool_service = current_app.config['TOOL_SERVICE']

    status = {
        'mcp_client': tool_service.get_tools_status(),
        'config': config_service.get_debug_status()['config']
    }

    return jsonify(status)