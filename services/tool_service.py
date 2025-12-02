import logging
import traceback
from typing import List, Dict, Any
from mcp_server import MCPClient
from .base_service import BaseService

logger = logging.getLogger(__name__)

class ToolService(BaseService):
    """工具管理服务"""

    def __init__(self):
        super().__init__()
        self.mcp_client = None
        self.available_tools = []
        self.selected_tools = []

    def initialize(self, mcp_client: MCPClient):
        """初始化工具服务"""
        self.mcp_client = mcp_client
        self.logger.info("工具服务初始化完成")

    def connect_mcp(self, host: str, port: int) -> bool:
        """连接MCP服务器"""
        try:
            if not self.mcp_client:
                self.mcp_client = MCPClient(host, port)

            self.logger.info(f"尝试连接MCP服务器 {host}:{port}")

            if self.mcp_client.connect():
                self.available_tools = self.mcp_client.list_tools()
                self.logger.info(f"成功连接MCP服务器，加载了 {len(self.available_tools)} 个工具")

                # 打印工具详情
                for tool in self.available_tools:
                    self.logger.info(f"  - {tool['name']} (来自: {tool.get('package', 'unknown')}): {tool['description']}")
                return True
            else:
                self.logger.error("无法连接到MCP服务器")
                self.available_tools = []
                return False

        except Exception as e:
            self.logger.error(f"连接MCP服务器失败: {e}")
            self.logger.error(traceback.format_exc())
            self.available_tools = []
            return False

    def get_available_tools(self) -> List[Dict]:
        """获取可用工具列表"""
        # 尝试重新获取工具列表
        try:
            if self.mcp_client:
                current_tools = self.mcp_client.list_tools()
                if current_tools != self.available_tools:
                    self.available_tools = current_tools
                    self.logger.info(f"工具列表已更新，当前有 {len(self.available_tools)} 个工具")
        except Exception as e:
            self.logger.error(f"获取工具列表失败: {e}")
            # 使用缓存的工具列表

        return self.available_tools

    def get_selected_tools(self) -> List[str]:
        """获取已选择的工具列表"""
        return self.selected_tools

    def set_selected_tools(self, tools: List[str]):
        """设置选择的工具"""
        self.selected_tools = tools
        self.logger.info(f"用户选择了 {len(self.selected_tools)} 个工具")

    def build_system_prompt(self) -> str:
        """构建系统提示"""
        base_prompt = ""

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

    def build_tools_definition(self) -> List[Dict]:
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

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """执行MCP工具"""
        if not self.mcp_client:
            raise Exception("MCP服务器未连接")

        return self.mcp_client.execute_tool(tool_name, parameters)

    def is_mcp_connected(self) -> bool:
        """检查MCP是否连接"""
        return self.mcp_client is not None

    def get_tools_status(self) -> Dict[str, Any]:
        """获取工具状态信息"""
        return {
            'connected': self.mcp_client is not None,
            'tools_count': len(self.available_tools),
            'selected_count': len(self.selected_tools),
            'tools': [
                {
                    'name': tool['name'],
                    'package': tool.get('package', 'unknown'),
                    'description': tool['description'][:100] + '...' if len(tool['description']) > 100 else tool['description']
                }
                for tool in self.available_tools
            ]
        }