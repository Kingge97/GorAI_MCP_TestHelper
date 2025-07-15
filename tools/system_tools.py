# tools/system_tools.py - 系统信息工具

def mcp_tool(description: str = "", parameters: dict = None):
    """MCP工具装饰器"""
    def decorator(func):
        func._mcp_tool = {
            'description': description,
            'parameters': parameters or {}
        }
        return func
    return decorator

import platform
import os
import datetime

@mcp_tool(
    description="获取系统信息",
    parameters={}
)
def system_info():
    """获取系统基本信息"""
    return {
        "操作系统": platform.system(),
        "系统版本": platform.release(),
        "架构": platform.machine(),
        "处理器": platform.processor(),
        "Python版本": platform.python_version(),
        "当前用户": os.getenv('USER') or os.getenv('USERNAME') or "未知",
        "当前时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@mcp_tool(
    description="获取当前工作目录",
    parameters={}
)
def current_directory():
    """获取当前工作目录"""
    return {
        "current_directory": os.getcwd(),
        "absolute_path": os.path.abspath("."),
        "directory_exists": os.path.exists(".")
    }
