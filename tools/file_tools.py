# tools/file_tools.py - 文件操作工具

def mcp_tool(description: str = "", parameters: dict = None):
    """MCP工具装饰器"""
    def decorator(func):
        func._mcp_tool = {
            'description': description,
            'parameters': parameters or {}
        }
        return func
    return decorator

import os
import datetime

@mcp_tool(
    description="列出指定目录下的文件和文件夹",
    parameters={
        "path": {"type": "string", "description": "目录路径，默认为当前目录"}
    }
)
def list_directory(path: str = "."):
    """列出目录内容"""
    try:
        if not os.path.exists(path):
            return f"错误: 路径 '{path}' 不存在"
        
        if not os.path.isdir(path):
            return f"错误: '{path}' 不是一个目录"
        
        items = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            item_type = "目录" if os.path.isdir(item_path) else "文件"
            
            try:
                size = os.path.getsize(item_path) if os.path.isfile(item_path) else "-"
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(item_path)).strftime("%Y-%m-%d %H:%M")
                items.append({
                    "name": item,
                    "type": item_type,
                    "size": size,
                    "modified": mtime
                })
            except:
                items.append({
                    "name": item,
                    "type": item_type,
                    "size": "未知",
                    "modified": "未知"
                })
        
        return {"path": path, "items": items}
    
    except Exception as e:
        return f"错误: {str(e)}"

@mcp_tool(
    description="读取文本文件内容",
    parameters={
        "filepath": {"type": "string", "description": "文件路径"},
        "encoding": {"type": "string", "description": "文件编码，默认为utf-8"}
    }
)
def read_file(filepath: str, encoding: str = "utf-8"):
    """读取文件内容"""
    try:
        if not os.path.exists(filepath):
            return f"错误: 文件 '{filepath}' 不存在"
        
        if not os.path.isfile(filepath):
            return f"错误: '{filepath}' 不是一个文件"
        
        with open(filepath, 'r', encoding=encoding) as f:
            content = f.read()
        
        return {
            "filepath": filepath,
            "size": len(content),
            "lines": len(content.split('\n')),
            "content": content[:1000] + "..." if len(content) > 1000 else content
        }
    
    except Exception as e:
        return f"错误: {str(e)}"
