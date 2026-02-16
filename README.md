# MCP工具助手 - AI智能体项目文档

## 项目概述

本项目是一个**MCP工具开发与调试的本地服务平台**，用于在半封闭网络环境下快速测试MCP工具，支持在本机托管AI任务。

### 核心特性
- ✅ MCP工具动态加载与注册
- ✅ 聊天记录保存与载入
- ✅ 任务托管系统（定时执行）
- ✅ 多模型切换与参数配置
- ✅ 多图片上传支持（Vision API）
- ✅ 系统提示词自定义
- ✅ 对话中断功能
- ✅ 思考链（Chain of Thought）支持
- ✅ 任务执行记录管理与下载
- 🚧 多AI串联/并联工作流（规划中）

---

## 技术架构

### 技术栈
```
后端框架: Flask 3.0.0
跨域支持: Flask-CORS 4.0.0
Web工具: Werkzeug 3.0.1
LLM调用: 本地封装的 GorAI_LLMClient 包 (v0.3.1)
模板引擎: Jinja2 (Flask内置)
Python版本: >= 3.12.8

数据处理: numpy>=1.24.0, pandas>=2.0.0
数据可视化: matplotlib>=3.7.0, seaborn>=0.12.0
AI SDK: openai>=1.93.0, anthropic>=0.39.0
```

### 架构设计
采用**前后端分离 + 服务层架构**：

```
┌─────────────────────────────────────────┐
│          Web前端 (Flask Templates)       │
│     templates/ + static/js + static/css │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│          Flask路由层 (routes/)           │
│  chat_routes | task_routes | tools_routes│
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         服务层 (services/)               │
│  ChatService | TaskService | ToolService │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│         MCP服务器 (mcp_server.py)        │
│    MCPClient → 动态加载 tools/ 目录       │
└─────────────────────────────────────────┘
```

---

## 目录结构详解

```
项目根目录/
├── GorAI_LLMClient/          # 本地LLM客户端封装 (v0.3.1)
│   ├── __init__.py           # 包入口
│   ├── executor.py           # 工具执行器
│   ├── message/              # 消息格式封装
│   └── models/               # 模型封装
│       ├── _model_base.py        # 模型基类
│       ├── _openai_model.py      # OpenAI兼容模型
│       ├── _anthropic_model.py   # Anthropic Claude模型
│       ├── _deepseek_openai_model.py  # DeepSeek模型
│       └── _minimax_anthropic_model.py # MiniMax模型
│
├── chatSave/                 # 普通聊天记录 (JSON)
├── missionChatSave/          # 任务聊天记录 (JSON)
│
├── routes/                   # Flask路由层
│   ├── chat_routes.py        # 聊天接口
│   ├── task_routes.py        # 任务管理接口
│   ├── tools_routes.py       # 工具管理接口
│   ├── config_routes.py      # 配置接口
│   ├── file_routes.py        # 文件操作接口
│   └── main_routes.py        # 主页路由
│
├── services/                 # 业务逻辑层
│   ├── base_service.py       # 服务基类
│   ├── chat_service.py       # 聊天服务 (LLM调用 + 工具执行)
│   ├── task_service.py       # 任务调度服务
│   ├── tool_service.py       # 工具管理服务
│   ├── config_service.py     # 配置管理服务
│   └── session_service.py    # 会话管理服务
│
├── tools/                    # MCP工具实现目录 ⭐
│   ├── __init__.py           # 工具包初始化
│   ├── calculator.py         # 计算器工具
│   ├── file_tools.py         # 文件操作工具
│   ├── time_tools.py         # 时间工具
│   ├── text_tools.py         # 文本处理工具
│   ├── system_tools.py       # 系统工具
│   └── chart_tools.py        # 图表工具
│
├── static/                   # 前端静态资源
│   ├── css/style.css
│   └── js/app.js, tasks.js
│
├── templates/                # HTML模板
│   ├── index.html            # 聊天页面
│   └── tasks.html            # 任务管理页面
│
├── config.json               # 系统配置文件 ⭐
├── tasks.json                # 任务配置文件 ⭐
├── app.py                    # Web服务器主程序
├── mcp_server.py             # MCP服务器实现
├── adaptive_launcher.py      # 服务启动脚本
└── requirements.txt          # Python依赖
```

---

## 核心配置文件

### 1. config.json - 系统配置
```json
{
  "mcp_server": {
    "host": "localhost",
    "port": 8888
  },
  "web_server": {
    "host": "localhost",
    "port": 5000,
    "debug": false
  },
  "llm": {
    "models": [
      {
        "id": "模型ID",
        "model_name": "模型调用名称",
        "name": "显示名称",
        "description": "描述",
        "api_key": "API密钥",
        "base_url": "API端点",
        "stream": true/false,
        "router": "openai-chat/anthropic",
        "extra_args": {
          "temperature": 0.7,
          "max_tokens": 4096
        }
      }
    ],
    "default_model": "默认模型ID"
  },
  "ui": {
    "title": "MCP工具助手",
    "theme": "light",
    "auto_scroll": true
  }
}
```

**重要规则**：
- 必须是标准JSON格式，**不允许注释**
- 所有字符串必须用双引号
- 模型配置必须包含 `router` 字段（值为 `openai-chat` 或 `anthropic`）

### 2. tasks.json - 任务配置
```json
{
  "tasks": {
    "任务UUID": {
      "id": "任务UUID",
      "name": "任务名称",
      "prompt": "系统提示词",
      "user_input": "用户输入",
      "tools": ["工具1", "工具2"],
      "model": "模型ID",
      "interval_minutes": 1,
      "max_executions": -1,
      "status": "pending",
      "is_active": true
    }
  },
  "last_updated": "2025-11-12T14:34:21.466846"
}
```

**任务字段说明**：
- `interval_minutes`: 执行间隔（分钟）
- `max_executions`: 最大执行次数（-1表示无限制）
- `status`: 任务状态（pending/running/completed/failed）
- `is_active`: 是否激活定时执行

---

## 核心服务说明

### ChatService - 聊天服务
**职责**：处理LLM对话 + 工具调用

**关键方法**：
- `stream_chat_response()`: 流式响应（支持SSE）
- `get_chat_response()`: 非流式响应
- `_handle_tool_calls()`: 处理工具调用请求

**工作流程**：
```
用户消息 → LLM生成响应 → 检测tool_calls
                             ↓
                        调用MCP工具
                             ↓
                    将结果返回LLM → 继续对话
```

### TaskService - 任务调度服务
**职责**：管理定时任务执行

**关键功能**：
- 任务创建、删除、启停
- 定时触发任务执行
- 执行历史记录保存

**任务执行流程**：
```
检查任务调度时间 → 启动任务
                     ↓
              使用ChatService调用LLM
                     ↓
              保存执行记录到missionChatSave/
```

### ToolService - 工具管理服务
**职责**：MCP工具注册与调用

**关键功能**：
- 连接MCP服务器
- 获取可用工具列表
- 构建OpenAI function calling定义
- 执行工具调用

**工具发现机制**：
```
MCP服务器启动 → 扫描tools/目录
                    ↓
              查找@mcp_tool装饰器
                    ↓
              自动注册工具到MCPClient
```

---

## 如何添加新工具

### 方法1：使用@mcp_tool装饰器（推荐）

在 `tools/` 目录下创建 `.py` 文件：

```python
from mcp_server import mcp_tool

@mcp_tool(
    name="你的工具名",
    description="工具描述",
    parameters={
        "param1": {
            "type": "string",
            "description": "参数1描述"
        }
    }
)
def your_tool_function(param1: str) -> dict:
    """
    工具实现
    """
    result = f"处理结果: {param1}"
    return {"result": result}
```

**重启服务后自动生效**！

### 方法2：手动注册

在 `mcp_server.py` 的 `MCPServer` 类中注册：

```python
self.tools["your_tool"] = {
    "name": "your_tool",
    "description": "描述",
    "parameters": {...},
    "handler": your_handler_function
}
```

---

## 启动与运行

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置文件
编辑 `config.json` 配置模型和服务器端口

### 3. 启动服务
```bash
python adaptive_launcher.py
```

或使用Windows批处理脚本：
```bash
start_mcp_tools.bat
```

### 4. 访问界面
```
http://localhost:5000/
```

---

## API接口说明

### 聊天接口
- `POST /api/chat` - 发送聊天消息（支持流式/非流式，支持多图片上传）
- `POST /api/chat/clear` - 清空当前会话历史
- `POST /api/chat/save` - 保存当前会话到文件
- `POST /api/chat/load` - 从文件加载历史会话
- `GET /api/chat/list` - 获取已保存的会话列表
- `POST /api/chat/delete` - 删除已保存的会话文件
- `POST /api/chat/interrupt` - 中断当前正在进行的对话

### 工具接口
- `GET /api/tools` - 获取可用工具列表
- `POST /api/tools/select` - 设置选中的工具

### 任务接口
- `GET /api/tasks` - 获取所有任务
- `POST /api/tasks` - 创建新任务
- `POST /api/tasks/<task_id>/toggle` - 启停任务
- `DELETE /api/tasks/<task_id>` - 删除任务
- `POST /api/tasks/<task_id>/execute` - 手动执行任务
- `GET /api/tasks/<task_id>/records` - 获取任务执行记录
- `GET /api/tasks/<task_id>/records/<record_id>` - 获取执行记录详情
- `GET /api/tasks/<task_id>/records/<record_id>/download` - 下载执行记录

### 配置接口
- `GET /api/config` - 获取配置信息
- `POST /api/config/model` - 切换模型

### 调试接口
- `GET /api/debug/status` - 获取系统调试状态信息

### 文件接口
- `GET /api/files/<path>` - 获取静态文件（如生成的图表等）

---

## 数据流向图

```
┌──────────┐
│  用户    │
└────┬─────┘
     │
     ▼
┌────────────┐  HTTP   ┌────────────┐
│  Web前端   │◄───────►│ Flask路由  │
└────────────┘         └─────┬──────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  ChatService   │
                    └────┬───────┬───┘
                         │       │
              ┌──────────┘       └──────────┐
              ▼                             ▼
      ┌──────────────┐            ┌──────────────┐
      │ ToolService  │            │ GorAI_LLM    │
      └──────┬───────┘            │   Client     │
             │                    └──────────────┘
             ▼
      ┌──────────────┐
      │ MCP服务器    │
      │  (本地)      │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │  tools/目录  │
      │  (@mcp_tool) │
      └──────────────┘
```

---

## 关键设计模式

### 1. 装饰器模式 - 工具注册
```python
@mcp_tool(name="...", description="...", parameters={...})
def tool_function(...):
    pass
```

### 2. 服务层模式 - 业务解耦
```
Routes → Services → MCP/LLM
```

### 3. 工厂模式 - 模型路由
```python
if router == "openai-chat":
    client = OpenAIModel(...)
elif router == "anthropic":
    client = AnthropicModel(...)
# 支持更多模型扩展...
```

**已支持的模型类型**：
- `openai-chat`: OpenAI兼容API（GPT、Qwen、DeepSeek等）
- `anthropic`: Anthropic Claude API（Claude、MiniMax等）

---

## 常见问题 (FAQ)

### Q1: 如何添加新的LLM模型？
在 `config.json` 的 `llm.models` 数组中添加新配置，指定正确的 `router`。

### Q2: 工具调用失败怎么办？
检查：
1. MCP服务器是否正常启动（查看日志）
2. 工具是否正确注册（访问 `/tools` 接口）
3. 工具参数是否符合定义

### Q3: 如何调试任务执行？
查看 `missionChatSave/` 目录下对应任务的JSON记录文件。

### Q4: 支持哪些LLM提供商？
当前支持多种LLM提供商：
- **OpenAI兼容接口**（通过 `openai-chat` router）
  - 阿里云千问 (Qwen) 系列
  - DeepSeek 系列（支持思考链输出）
  - 其他OpenAI API兼容服务
- **Anthropic Claude**（通过 `anthropic` router）
- **MiniMax**（通过 `anthropic` router，使用Anthropic兼容接口）

### Q5: 聊天记录保存在哪里？
- 普通聊天：`chatSave/chat_<时间戳>.json`
- 任务聊天：`missionChatSave/task_<任务名>_<时间戳>_<UUID>.json`

---

## 智能体使用建议

### 🤖 作为AI智能体，你应该：

1. **理解项目结构**：先查看 `routes/` 和 `services/` 了解功能模块
2. **查看现有工具**：浏览 `tools/` 目录学习工具实现范式
3. **配置模型**：检查 `config.json` 确认可用模型
4. **测试工具**：通过Web界面或API测试工具调用
5. **创建任务**：使用任务系统进行自动化测试

### 📝 修改代码时注意：
- 遵循服务层架构，不要跨层调用
- 新增工具使用 `@mcp_tool` 装饰器
- 修改配置文件确保JSON格式合法
- 重启服务使更改生效

### 🔍 调试技巧：
- 查看Flask日志定位路由问题
- 检查 `chatSave/` 和 `missionChatSave/` 了解对话历史
- 使用 `/tools` 接口验证工具注册状态
- 查看浏览器控制台定位前端问题


**文档版本**: v0.1.9.7  
**最后更新**: 2026-02-16  
**维护者**: Kingge97