# tools/text_tools.py - 文本处理工具

def mcp_tool(description: str = "", parameters: dict = None):
    """MCP工具装饰器"""
    def decorator(func):
        func._mcp_tool = {
            'description': description,
            'parameters': parameters or {}
        }
        return func
    return decorator

import hashlib

@mcp_tool(
    description="计算文本的字符数、单词数和行数",
    parameters={
        "text": {"type": "string", "description": "要分析的文本"}
    }
)
def text_stats(text: str):
    """分析文本统计信息"""
    lines = text.split('\n')
    words = text.split()
    chars = len(text)
    
    return {
        "characters": chars,
        "words": len(words),
        "lines": len(lines),
        "average_word_length": round(sum(len(word) for word in words) / len(words), 2) if words else 0
    }

@mcp_tool(
    description="将文本转换为大写、小写或标题格式",
    parameters={
        "text": {"type": "string", "description": "要转换的文本"},
        "mode": {"type": "string", "description": "转换模式: upper, lower, title"}
    }
)
def text_transform(text: str, mode: str = "upper"):
    """转换文本格式"""
    if mode == "upper":
        return text.upper()
    elif mode == "lower":
        return text.lower()
    elif mode == "title":
        return text.title()
    else:
        return f"错误: 未知模式 '{mode}', 支持的模式: upper, lower, title"

@mcp_tool(
    description="生成文本的MD5哈希值",
    parameters={
        "text": {"type": "string", "description": "要哈希的文本"}
    }
)
def text_hash(text: str):
    """生成文本的MD5哈希"""
    md5_hash = hashlib.md5(text.encode()).hexdigest()
    return f"MD5: {md5_hash}"
