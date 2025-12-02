import json
import logging
from typing import Dict, Any
from .base_service import BaseService

logger = logging.getLogger(__name__)

class ConfigService(BaseService):
    """配置管理服务"""

    def __init__(self):
        super().__init__()
        self.config = None

    def initialize(self, config_path: str = 'config.json'):
        """初始化配置服务"""
        self.config = self.load_config(config_path)
        self.logger.info("配置服务初始化完成")

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"配置文件 {config_path} 未找到")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件格式错误: {e}")
            raise

    def get_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self.config

    def get_model_config(self, model_id: str) -> Dict[str, Any]:
        """获取特定模型的配置"""
        for model in self.config['llm']['models']:
            if model['id'] == model_id:
                return model

        # 如果找不到特定模型配置，返回默认配置
        self.logger.warning(f"未找到模型 {model_id} 的配置，使用第一个模型的配置")
        return self.config['llm']['models'][0]

    def get_actual_model_name(self, model_id: str) -> str:
        """获取实际用于API调用的模型名称"""
        model_config = self.get_model_config(model_id)
        return model_config.get('model_name', model_id)

    def get_model_extra_args(self, model_id: str) -> Dict[str, Any]:
        """获取模型的额外参数"""
        model_config = self.get_model_config(model_id)
        return model_config.get('extra_args', {})

    def get_default_model(self) -> str:
        """获取默认模型"""
        return self.config['llm']['default_model']

    def get_web_server_config(self) -> Dict[str, Any]:
        """获取Web服务器配置"""
        return self.config['web_server']

    def get_mcp_server_config(self) -> Dict[str, Any]:
        """获取MCP服务器配置"""
        return self.config['mcp_server']

    def get_ui_config(self) -> Dict[str, Any]:
        """获取UI配置"""
        return self.config['ui']

    def get_all_models(self) -> list:
        """获取所有模型配置"""
        return self.config['llm']['models']

    def get_model_names(self) -> list:
        """获取所有模型名称"""
        return [model['id'] for model in self.config['llm']['models']]

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息"""
        return {
            'models': self.config['llm']['models'],
            'default_model': self.config['llm']['default_model'],
            'ui': self.config['ui']
        }

    def get_debug_status(self) -> Dict[str, Any]:
        """获取调试状态信息"""
        return {
            'config': {
                'loaded': self.config is not None,
                'mcp_server': self.config.get('mcp_server', {}) if self.config else {},
                'models_count': len(self.config.get('llm', {}).get('models', [])) if self.config else 0
            }
        }