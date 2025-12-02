# tools/time_tools.py - 时间处理工具

from datetime import datetime

def mcp_tool(description: str = "", parameters: dict = None):
    """MCP工具装饰器"""
    def decorator(func):
        func._mcp_tool = {
            'description': description,
            'parameters': parameters or {}
        }
        return func
    return decorator

@mcp_tool(
    description="获取当前时间",
    parameters={}
)
def get_current_time():
    """获取当前时间，格式：YYYY-MM-DD HH:MM:SS"""
    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "current_time": formatted_time,
        "timestamp": int(current_time.timestamp())
    }