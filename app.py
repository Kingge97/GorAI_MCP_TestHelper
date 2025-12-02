#!/usr/bin/env python3
# app_rebuild.py - 重构后的Web后端服务器，使用服务层架构
import json
import logging
import time
from flask import Flask, render_template, request, jsonify, Response, stream_template, send_file
from flask_cors import CORS
import openai
from openai import OpenAI
import asyncio
import threading
import traceback
import os

# 导入服务层
from services import ConfigService, ToolService, SessionService, ChatService, TaskService

# 导入所有Blueprint
from routes.main_routes import main_bp
from routes.config_routes import config_bp
from routes.tools_routes import tools_bp
from routes.chat_routes import chat_bp
from routes.task_routes import task_bp
from routes.file_routes import file_bp

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebServer:
    def __init__(self, config_path='config.json'):
        # 初始化服务层
        self.config_service = ConfigService()
        self.config_service.initialize(config_path)
        self.config = self.config_service.get_config()

        self.app = Flask(__name__)
        CORS(self.app)

        # 初始化工具服务
        self.tool_service = ToolService()

        # 初始化会话服务
        self.session_service = SessionService()
        self.session_service.initialize()

        # 初始化聊天服务
        self.chat_service = ChatService()
        self.chat_service.initialize(self.config_service, self.tool_service, self.session_service)

        # 初始化任务服务（不再需要WebTaskScheduler）
        self.task_service = TaskService()
        self.task_service.initialize(self.chat_service, self.tool_service)

        # 注册Blueprints
        self.register_blueprints()

        # 连接MCP服务器
        self.connect_mcp()
        
        # 启动后台清理线程
        self.start_cleanup_thread()

    def register_blueprints(self):
        """注册所有Blueprint"""
        # 将服务实例存储到app配置中，供Blueprint使用
        self.app.config['SERVER'] = self
        self.app.config['CONFIG_SERVICE'] = self.config_service
        self.app.config['TOOL_SERVICE'] = self.tool_service
        self.app.config['SESSION_SERVICE'] = self.session_service
        self.app.config['CHAT_SERVICE'] = self.chat_service
        self.app.config['TASK_SERVICE'] = self.task_service

        # 为main_bp设置config属性
        main_bp.config = self.config

        # 注册所有Blueprint
        self.app.register_blueprint(main_bp)
        self.app.register_blueprint(config_bp)
        self.app.register_blueprint(tools_bp)
        self.app.register_blueprint(chat_bp)
        self.app.register_blueprint(task_bp)
        self.app.register_blueprint(file_bp)

        logger.info("所有Blueprint已注册完成")

    def connect_mcp(self):
        """连接MCP服务器"""
        try:
            mcp_config = self.config['mcp_server']

            logger.info(f"尝试连接MCP服务器 {mcp_config['host']}:{mcp_config['port']}")

            if self.tool_service.connect_mcp(mcp_config['host'], mcp_config['port']):
                logger.info("MCP服务器连接成功")
            else:
                logger.error("无法连接到MCP服务器")

        except Exception as e:
            logger.error(f"连接MCP服务器失败: {e}")
            logger.error(traceback.format_exc())

    def stream_chat_response(self, messages, model, tools=None, session_id=None):
        """流式聊天响应"""
        yield from self.chat_service.stream_chat_response(messages, model, tools, session_id)

    def get_chat_response(self, messages, model, tools=None, session_id=None):
        """非流式聊天响应"""
        yield from self.chat_service.get_chat_response(messages, model, tools, session_id)


    def start_cleanup_thread(self):
        """启动后台会话清理线程"""
        def cleanup_task():
            logger.info("会话清理线程已启动")
            while True:
                try:
                    time.sleep(600)  # 每10分钟执行一次
                    logger.info("开始执行会话缓存清理...")
                    self.session_service.cache_inactive_sessions()
                except Exception as e:
                    logger.error(f"会话清理线程错误: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        logger.info("后台清理线程已启动（每10分钟执行）")

    def run(self):
        """启动Web服务器"""
        web_config = self.config['web_server']
        logger.info(f"启动Web服务器在 http://{web_config['host']}:{web_config['port']}")

        self.app.run(
            host=web_config['host'],
            port=web_config['port'],
            debug=web_config['debug']
        )

if __name__ == '__main__':
    # 确保templates文件夹存在
    if not os.path.exists('templates'):
        os.makedirs('templates')

    # 确保static文件夹存在
    if not os.path.exists('static'):
        os.makedirs('static')
        os.makedirs('static/css')
        os.makedirs('static/js')

    try:
        server = WebServer()
        server.run()
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"启动服务器失败: {e}")