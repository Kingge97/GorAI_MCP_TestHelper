# mcp_server.py - MCP服务器实现
import json
import socket
import threading
import os
import importlib.util
import inspect
from typing import Dict, List, Any, Callable
import traceback

class MCPServer:
    def __init__(self, host=None, port=None, tools_dir='tools', config_file='config.json'):
        """
        初始化MCP服务器
        
        Args:
            host: 服务器主机地址，如果为None则从配置文件读取
            port: 服务器端口，如果为None则从配置文件读取
            tools_dir: 工具文件夹路径
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.tools_dir = tools_dir
        self.tools = {}
        self.running = False
        
        # 从配置文件加载配置
        config = self.load_config()
        
        # 设置host和port，优先使用传入的参数，其次使用配置文件，最后使用默认值
        self.host = host or config.get('mcp_server', {}).get('host', 'localhost')
        self.port = port or config.get('mcp_server', {}).get('port', 8888)
        
        print(f"MCP服务器配置 - 主机: {self.host}, 端口: {self.port}")
        
    def load_config(self):
        """从配置文件加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"已从 {self.config_file} 加载配置")
                return config
            else:
                print(f"配置文件 {self.config_file} 不存在，使用默认配置")
                return {}
        except Exception as e:
            print(f"读取配置文件失败: {e}，使用默认配置")
            return {}
    
    def save_default_config(self):
        """保存默认配置文件"""
        default_config = {
            "mcp_server": {
                "host": "localhost",
                "port": 8888
            },
            "web_server": {
                "host": "localhost",
                "port": 5000,
                "debug": True
            },
            "llm": {
                "api_key": "your api key",
                "base_url": "your base url",
                "models": [
                    {
                        "id": "qwen-max",
                        "name": "千问MAX",
                        "description": ""
                    }
                ],
                "default_model": "qwen-max",
                "stream": True
            },
            "ui": {
                "title": "MCP工具助手",
                "theme": "light",
                "auto_scroll": True
            }
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"已创建默认配置文件: {self.config_file}")
        except Exception as e:
            print(f"创建默认配置文件失败: {e}")
    
    def load_tools(self):
        """从tools文件夹加载MCP工具"""
        print(f"正在从 {self.tools_dir} 文件夹加载工具...")
        
        if not os.path.exists(self.tools_dir):
            os.makedirs(self.tools_dir)
            print(f"创建了 {self.tools_dir} 文件夹")
            return
            
        for filename in os.listdir(self.tools_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                tool_path = os.path.join(self.tools_dir, filename)
                tool_name = filename[:-3]  # 去掉.py扩展名
                
                try:
                    # 动态导入模块
                    spec = importlib.util.spec_from_file_location(tool_name, tool_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # 查找工具函数
                    for name, obj in inspect.getmembers(module):
                        if inspect.isfunction(obj) and hasattr(obj, '_mcp_tool'):
                            tool_info = {
                                'name': name,
                                'description': obj._mcp_tool.get('description', ''),
                                'parameters': obj._mcp_tool.get('parameters', {}),
                                'package': tool_name,  # 添加包名信息
                                'file_path': tool_path,  # 添加文件路径
                                'function': obj
                            }
                            self.tools[name] = tool_info
                            print(f"加载工具: {name} (来自: {tool_name})")
                            
                except Exception as e:
                    print(f"加载工具 {filename} 时出错: {e}")
    
    def handle_request(self, request_data: str) -> str:
        """处理客户端请求"""
        try:
            request = json.loads(request_data)
            method = request.get('method')
            params = request.get('params', {})
            request_id = request.get('id')
            
            if method == 'list_tools':
                # 返回工具列表
                tools_list = []
                for tool_name, tool_info in self.tools.items():
                    tools_list.append({
                        'name': tool_info['name'],
                        'description': tool_info['description'],
                        'parameters': tool_info['parameters'],
                        'package': tool_info['package'],
                        'file_path': tool_info['file_path']
                    })
                
                response = {
                    'jsonrpc': '2.0',
                    'result': {'tools': tools_list},
                    'id': request_id
                }
                
            elif method == 'execute_tool':
                # 执行工具
                tool_name = params.get('tool_name')
                tool_params = params.get('parameters', {})
                
                if tool_name not in self.tools:
                    response = {
                        'jsonrpc': '2.0',
                        'error': {'code': -32602, 'message': f'工具 {tool_name} 未找到'},
                        'id': request_id
                    }
                else:
                    try:
                        tool_func = self.tools[tool_name]['function']
                        result = tool_func(**tool_params)
                        response = {
                            'jsonrpc': '2.0',
                            'result': {'output': result},
                            'id': request_id
                        }
                    except Exception as e:
                        response = {
                            'jsonrpc': '2.0',
                            'error': {'code': -32603, 'message': f'工具执行错误: {str(e)}'},
                            'id': request_id
                        }
            else:
                response = {
                    'jsonrpc': '2.0',
                    'error': {'code': -32601, 'message': f'未知方法: {method}'},
                    'id': request_id
                }
                
            return json.dumps(response)
            
        except json.JSONDecodeError:
            return json.dumps({
                'jsonrpc': '2.0',
                'error': {'code': -32700, 'message': 'JSON解析错误'},
                'id': None
            })
        except Exception as e:
            return json.dumps({
                'jsonrpc': '2.0',
                'error': {'code': -32603, 'message': f'内部错误: {str(e)}'},
                'id': None
            })
    
    def handle_client(self, client_socket, address):
        """处理单个客户端连接"""
        print(f"客户端 {address} 已连接")
        
        try:
            while self.running:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                response = self.handle_request(data)
                client_socket.send(response.encode('utf-8'))
                
        except Exception as e:
            print(f"处理客户端 {address} 时出错: {e}")
        finally:
            client_socket.close()
            print(f"客户端 {address} 已断开连接")
    
    def start(self):
        """启动服务器"""
        self.load_tools()
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.running = True
            print(f"MCP服务器启动在 {self.host}:{self.port}")
            
            while self.running:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
                
        except KeyboardInterrupt:
            print("\n服务器正在关闭...")
        except Exception as e:
            print(f"服务器启动失败: {e}")
            print(f"请检查地址 {self.host}:{self.port} 是否已被占用")
        finally:
            self.stop()
    
    def stop(self):
        """停止服务器"""
        self.running = False
        if hasattr(self, 'server_socket'):
            self.server_socket.close()

# mcp_client.py - MCP客户端实现
class MCPClient:
    def __init__(self, host=None, port=None, config_file='config.json'):
        """
        初始化MCP客户端
        
        Args:
            host: 服务器主机地址，如果为None则从配置文件读取
            port: 服务器端口，如果为None则从配置文件读取
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.socket = None
        self.request_id = 0
        
        # 从配置文件加载配置
        config = self.load_config()
        
        # 设置host和port
        self.host = host or config.get('mcp_server', {}).get('host', 'localhost')
        self.port = port or config.get('mcp_server', {}).get('port', 8888)
    
    def load_config(self):
        """从配置文件加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            return {}
    
    def connect(self):
        """连接到MCP服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"已连接到MCP服务器 {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"连接服务器失败: {e}")
            return False
    
    def send_request(self, method: str, params: dict = None) -> dict:
        """发送请求到服务器"""
        if not self.socket:
            raise Exception("未连接到服务器")
        
        self.request_id += 1
        request = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or {},
            'id': self.request_id
        }
        
        request_data = json.dumps(request)
        self.socket.send(request_data.encode('utf-8'))
        
        response_data = self.socket.recv(4096).decode('utf-8')
        return json.loads(response_data)
    
    def list_tools(self) -> List[Dict]:
        """获取工具列表"""
        response = self.send_request('list_tools')
        if 'error' in response:
            raise Exception(f"获取工具列表失败: {response['error']['message']}")
        return response['result']['tools']
    
    def execute_tool(self, tool_name: str, parameters: dict = None) -> Any:
        """执行工具"""
        params = {
            'tool_name': tool_name,
            'parameters': parameters or {}
        }
        response = self.send_request('execute_tool', params)
        if 'error' in response:
            raise Exception(f"执行工具失败: {response['error']['message']}")
        return response['result']['output']
    
    def disconnect(self):
        """断开连接"""
        if self.socket:
            self.socket.close()
            self.socket = None
            print("已断开与服务器的连接")

# 工具装饰器
def mcp_tool(description: str = "", parameters: dict = None):
    """MCP工具装饰器"""
    def decorator(func):
        func._mcp_tool = {
            'description': description,
            'parameters': parameters or {}
        }
        return func
    return decorator

# 示例用法和测试代码
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'server':
        # 启动服务器
        server = MCPServer()
        
        # 如果配置文件不存在，创建默认配置文件
        if not os.path.exists(server.config_file):
            server.save_default_config()
            print("已创建默认配置文件，请根据需要修改config.json中的配置")
        
        try:
            server.start()
        except KeyboardInterrupt:
            print("\n服务器已停止")
    
    elif len(sys.argv) > 1 and sys.argv[1] == 'client':
        # 运行客户端测试
        client = MCPClient()
        
        if client.connect():
            try:
                # 获取工具列表
                print("\n可用工具:")
                tools = client.list_tools()
                for tool in tools:
                    print(f"- {tool['name']}: {tool['description']}")
                
                # 测试执行工具（如果有的话）
                if tools:
                    print(f"\n测试执行第一个工具: {tools[0]['name']}")
                    try:
                        result = client.execute_tool(tools[0]['name'])
                        print(f"执行结果: {result}")
                    except Exception as e:
                        print(f"执行失败: {e}")
                
            except Exception as e:
                print(f"客户端操作失败: {e}")
            finally:
                client.disconnect()
    else:
        print("使用方法:")
        print("启动服务器: python mcp_server.py server")
        print("运行客户端: python mcp_server.py client")
        print("\n配置说明:")
        print("- 修改 config.json 文件中的 mcp_server.host 和 mcp_server.port 来改变服务器地址和端口")
        print("- 如果config.json不存在，首次运行时会自动创建默认配置文件")