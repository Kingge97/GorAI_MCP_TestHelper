# tools/calculator.py - 计算器工具

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
    description="执行基本数学计算",
    parameters={
        "expression": {"type": "string", "description": "要计算的数学表达式"}
    }
)
def calculate(expression: str):
    """计算数学表达式"""
    try:
        # 安全的数学计算，只允许基本运算符
        allowed_chars = set('0123456789+-*/.()')
        if not all(c in allowed_chars or c.isspace() for c in expression):
            return "错误: 表达式包含不允许的字符"
        
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"

@mcp_tool(
    description="计算两个数的最大公约数",
    parameters={
        "a": {"type": "integer", "description": "第一个整数"},
        "b": {"type": "integer", "description": "第二个整数"}
    }
)
def gcd(a: int, b: int):
    """计算最大公约数"""
    def _gcd(x, y):
        while y:
            x, y = y, x % y
        return x
    
    result = _gcd(abs(a), abs(b))
    return f"gcd({a}, {b}) = {result}"
