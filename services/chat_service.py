import json
import logging
import traceback
from typing import List, Dict, Any, Optional
from GorAI_LLMCLient import create_model, ToolExecutor
from .base_service import BaseService

logger = logging.getLogger(__name__)


class MCPToolExecutor(ToolExecutor):
    """
    MCP工具执行器适配器

    将 ToolService 适配为 ToolExecutor 接口
    """

    def __init__(self, tool_service):
        """
        初始化 MCP 工具执行器

        Args:
            tool_service: ToolService 实例
        """
        self.tool_service = tool_service

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        执行工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            str: 工具执行结果
        """
        result = self.tool_service.execute_tool(tool_name, arguments)
        return str(result)


class ChatService(BaseService):
    """聊天服务"""

    def __init__(self):
        super().__init__()
        self.config_service = None
        self.tool_service = None
        self.session_service = None

        # 添加中断状态管理
        self.interrupt_flags = {}  # 会话ID -> 是否中断的标志
        self.active_streams = {}   # 会话ID -> 活跃流控制器

    def initialize(self, config_service, tool_service, session_service):
        """初始化聊天服务"""
        self.config_service = config_service
        self.tool_service = tool_service
        self.session_service = session_service
        self.logger.info("聊天服务初始化完成")

    def _chat_loop(self, messages, model, tools=None, session_id=None, stream=False):
        """统一的对话循环方法，处理多轮对话和工具调用（使用 GorAI_LLMClient 的 chatToNextLoop）"""
        # 设置中断标志为False
        if session_id:
            self.interrupt_flags[session_id] = False

        # 明确指定utf-8编码并处理GBK编码问题
        def encode_json(data):
            try:
                return json.dumps(data, ensure_ascii=False).encode('utf-8')
            except UnicodeEncodeError:
                # 如果遇到编码错误，使用转义序列或替换字符
                safe_data = json.dumps(data, ensure_ascii=True).encode('utf-8')
                return safe_data

        # 中断检查函数
        def interrupt_check():
            if session_id:
                return self.interrupt_flags.get(session_id, False)
            return False

        # 获取实际用于API调用的模型名称
        actual_model_name = self.config_service.get_actual_model_name(model)

        # 添加额外参数
        extra_args = self.config_service.get_model_extra_args(model)

        # 获取模型特定配置
        model_config = self.config_service.get_model_config(model)

        # 创建GorAI_LLMClient模型实例
        llm_model = create_model(
            base_url=model_config['base_url'],
            api_key=model_config['api_key'],
            model_name=actual_model_name,
            stream=model_config.get('stream', True),
            extra_args=extra_args,
            router=model_config.get('router', 'openai-chat')
        )

        # 初始化工具（如果有）
        if tools:
            # 将MCP工具格式转换为GorAI_LLMClient所需格式
            tool_dict = []
            for tool in tools:
                tool_dict.append({
                    "name": tool['function']['name'],
                    "description": tool['function']['description'],
                    "parameters": tool['function']['parameters'],
                    "function": None  # 工具函数由tool_service执行，这里不需要
                })
            llm_model.model_tool_init(tool_dict)

        # 创建工具执行器
        executor = MCPToolExecutor(self.tool_service)

        # 记录活跃流
        if session_id:
            self.active_streams[session_id] = None

        # 使用新的 chatToNextLoop 方法处理对话循环
        try:
            yield from llm_model.chatToNextLoop(
                messages=messages,
                executor=executor,
                encode_json=encode_json,
                interrupt_check=interrupt_check
            )

            # 保存助手回复到会话历史（只有在没有被中断的情况下）
            # 注意：chatToNextLoop 已经处理了消息历史，这里我们需要从最终的 messages 中提取助手回复
            if session_id and not self.interrupt_flags.get(session_id, False):
                # 从最后的消息中查找助手回复
                for msg in reversed(messages):
                    if msg.get('role') == 'assistant' and msg.get('content'):
                        self.session_service.add_assistant_message(session_id, msg['content'])
                        break

        except Exception as e:
            error_msg = f"响应错误: {str(e)}"
            logger.error(f"响应错误: {e}")
            logger.error(traceback.format_exc())
            yield b"data: " + encode_json({'type': 'error', 'message': error_msg}) + b"\n\n"
        finally:
            # 清理会话状态
            if session_id:
                # 清除中断标志
                self.interrupt_flags.pop(session_id, None)
                # 清除活跃流引用
                self.active_streams.pop(session_id, None)


    def stream_chat_response(self, messages, model, tools=None, session_id=None):
        """流式聊天响应"""
        yield from self._chat_loop(messages, model, tools, session_id, stream=True)

    def get_chat_response(self, messages, model, tools=None, session_id=None):
        """非流式聊天响应"""
        yield from self._chat_loop(messages, model, tools, session_id, stream=False)

    def interrupt_chat(self, session_id):
        """中断指定会话的聊天"""
        if session_id in self.interrupt_flags:
            self.interrupt_flags[session_id] = True
            self.logger.info(f"已设置会话 {session_id} 的中断标志")

            # 如果存在活跃流，尝试中断
            if session_id in self.active_streams and self.active_streams[session_id]:
                try:
                    # 尝试关闭流连接
                    self.active_streams[session_id].close()
                    self.logger.info(f"已尝试关闭会话 {session_id} 的活跃流")
                except Exception as e:
                    self.logger.warning(f"关闭活跃流时出错: {e}")
            return True
        return False

    def get_chat_status(self):
        """获取聊天服务状态"""
        return {
            'active_sessions': len(self.interrupt_flags),
            'active_streams': len(self.active_streams),
            'interrupt_flags': list(self.interrupt_flags.keys())
        }

    def execute_ai_call(self, messages: list, model: str, tools: Optional[list] = None):
        """执行AI调用，返回AI响应对象（用于任务调度器）

        参数:
            messages: 消息列表
            model: 模型名称
            tools: 工具定义列表

        返回:
            dict 包含 content 和 tool_calls 的字典对象
        """
        try:
            # 获取实际用于API调用的模型名称
            actual_model_name = self.config_service.get_actual_model_name(model)

            # 添加额外参数
            extra_args = self.config_service.get_model_extra_args(model)

            # 获取模型特定配置
            model_config = self.config_service.get_model_config(model)
            
            # 创建GorAI_LLMClient模型实例
            llm_model = create_model(
                base_url=model_config['base_url'],
                api_key=model_config['api_key'],
                model_name=actual_model_name,
                stream=False,  # 任务调度器使用非流式
                extra_args=extra_args,
                router=model_config.get('router', 'openai-chat')
            )
            
            # 初始化工具（如果有）
            if tools:
                # 将MCP工具格式转换为GorAI_LLMClient所需格式
                tool_dict = []
                for tool in tools:
                    tool_dict.append({
                        "name": tool['function']['name'],
                        "description": tool['function']['description'],
                        "parameters": tool['function']['parameters'],
                        "function": None
                    })
                llm_model.model_tool_init(tool_dict)

            # 调用模型
            response = llm_model.model_chat(messages)
            
            # 收集响应
            content = ""
            tool_calls = []
            has_error = False
            error_message = ""
            
            for item in response:
                if item.gorType == "error":
                    has_error = True
                    error_message = item.content
                    logger.error(f"模型调用错误: {error_message}")
                    break
                elif item.gorType == "answer":
                    content += item.content
                elif item.gorType == "tool":
                    tool_call = json.loads(item.content)
                    tool_calls.append(tool_call)
            
            # 如果有错误，返回None
            if has_error:
                return None
            
            # 返回类似OpenAI message的对象结构
            class MessageLike:
                def __init__(self, content, tool_calls):
                    self.content = content
                    self.tool_calls = []
                    if tool_calls:
                        for tc in tool_calls:
                            # 创建类似 OpenAI tool_call 的对象
                            class ToolCallLike:
                                def __init__(self, tc_dict):
                                    self.id = tc_dict['id']
                                    self.type = tc_dict.get('type', 'function')
                                    class FunctionLike:
                                        def __init__(self, func_dict):
                                            self.name = func_dict['name']
                                            self.arguments = func_dict['arguments']
                                    self.function = FunctionLike(tc_dict['function'])
                            self.tool_calls.append(ToolCallLike(tc))
            
            return MessageLike(content, tool_calls)

        except Exception as e:
            logger.error(f"AI调用失败: {e}")
            return None