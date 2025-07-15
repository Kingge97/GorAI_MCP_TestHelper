// MCP Tool Assistant Frontend JavaScript

class MCPApp {
    constructor() {
        this.config = null;
        this.availableTools = [];
        this.selectedTools = [];
        this.currentModel = null;
        this.isConnected = false;
        this.isStreaming = false;

        // 添加会话ID
        this.sessionId = null;
        this.messageHistory = [];  // 本地消息历史备份
        
        this.init();
    }
    
    async init() {
        this.setupEventListeners();
        await this.loadConfig();
        await this.loadTools();
        this.updateUI();
    }
    
    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            this.config = await response.json();
            this.populateModelSelector();
            this.updateConnectionStatus(true);
        } catch (error) {
            console.error('加载配置失败:', error);
            this.updateConnectionStatus(false);
        }
    }
    
    async loadTools() {
        try {
            this.showLoadingState('正在加载工具...');
            
            const response = await fetch('/api/tools');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            this.availableTools = data.tools || [];
            this.selectedTools = data.selected || [];
            
            console.log('工具加载成功:', {
                total: this.availableTools.length,
                selected: this.selectedTools.length,
                tools: this.availableTools.map(t => ({name: t.name, package: t.package}))
            });
            
            this.renderToolsList();
            this.updateToolsCounter();
            
            if (this.availableTools.length === 0) {
                this.showError('没有找到可用工具，请检查MCP服务器是否正常启动');
            }
            
        } catch (error) {
            console.error('加载工具失败:', error);
            this.showError(`加载工具失败: ${error.message}`);
            this.showDebugInfo(error);
        }
    }
    
    showLoadingState(message) {
        const container = document.getElementById('toolsList');
        container.innerHTML = `<div class="loading">${message}</div>`;
    }
    
    async showDebugInfo(error) {
        try {
            // 获取调试信息
            const response = await fetch('/api/debug/status');
            if (response.ok) {
                const debugInfo = await response.json();
                console.error('调试信息:', debugInfo);
                
                // 显示详细的错误信息
                const container = document.getElementById('toolsList');
                container.innerHTML = `
                    <div class="error-info">
                        <h4>🔍 调试信息</h4>
                        <p><strong>错误:</strong> ${error.message}</p>
                        <p><strong>MCP连接:</strong> ${debugInfo.mcp_client.connected ? '✅ 已连接' : '❌ 未连接'}</p>
                        <p><strong>工具数量:</strong> ${debugInfo.mcp_client.tools_count}</p>
                        <p><strong>配置加载:</strong> ${debugInfo.config.loaded ? '✅ 正常' : '❌ 失败'}</p>
                        
                        <div class="debug-suggestions">
                            <h5>💡 解决建议:</h5>
                            <ul>
                                ${!debugInfo.mcp_client.connected ? '<li>检查MCP服务器是否启动 (python mcp_server.py server)</li>' : ''}
                                ${debugInfo.mcp_client.tools_count === 0 ? '<li>检查tools文件夹中是否有工具文件</li>' : ''}
                                ${!debugInfo.config.loaded ? '<li>检查config.json配置文件</li>' : ''}
                                <li>查看浏览器控制台获取详细错误信息</li>
                                <li>运行 python debug_start.py 进行完整诊断</li>
                            </ul>
                        </div>
                        
                        <button class="btn-primary" onclick="app.loadTools()" style="margin-top: 16px;">
                            🔄 重新加载
                        </button>
                    </div>
                `;
            }
        } catch (debugError) {
            console.error('获取调试信息失败:', debugError);
        }
    }
    
    populateModelSelector() {
        const select = document.getElementById('modelSelect');
        select.innerHTML = '<option value="">选择模型...</option>';
        
        this.config.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = `${model.name} - ${model.description}`;
            if (model.id === this.config.default_model) {
                option.selected = true;
                this.currentModel = model.id;
            }
            select.appendChild(option);
        });
    }
    
    renderToolsList() {
        const container = document.getElementById('toolsList');
        
        if (this.availableTools.length === 0) {
            container.innerHTML = '<div class="loading">暂无可用工具</div>';
            return;
        }
        
        container.innerHTML = '';
        
        this.availableTools.forEach(tool => {
            const toolElement = this.createToolElement(tool);
            container.appendChild(toolElement);
        });
    }
    
    createToolElement(tool) {
        const div = document.createElement('div');
        div.className = 'tool-item';
        div.dataset.toolName = tool.name;
        
        const isSelected = this.selectedTools.includes(tool.name);
        if (isSelected) {
            div.classList.add('selected');
        }
        
        div.innerHTML = `
            <div class="tool-header">
                <div class="tool-checkbox ${isSelected ? 'checked' : ''}"></div>
                <div class="tool-name">${tool.name}</div>
                <div class="tool-package">${tool.package}</div>
            </div>
            <div class="tool-description">${tool.description}</div>
        `;
        
        div.addEventListener('click', () => this.toggleTool(tool.name));
        
        return div;
    }
    
    toggleTool(toolName) {
        const index = this.selectedTools.indexOf(toolName);
        const toolElement = document.querySelector(`[data-tool-name="${toolName}"]`);
        const checkbox = toolElement.querySelector('.tool-checkbox');
        
        if (index > -1) {
            this.selectedTools.splice(index, 1);
            toolElement.classList.remove('selected');
            checkbox.classList.remove('checked');
        } else {
            this.selectedTools.push(toolName);
            toolElement.classList.add('selected');
            checkbox.classList.add('checked');
        }
        
        this.updateToolsCounter();
        this.updateToolsInfo();
    }
    
    async applyToolSelection() {
        const button = document.getElementById('applyTools');
        const originalText = button.textContent;
        
        try {
            button.textContent = '应用中...';
            button.disabled = true;
            
            const response = await fetch('/api/tools/select', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    tools: this.selectedTools
                })
            });
            
            if (response.ok) {
                button.textContent = '已应用 ✓';
                setTimeout(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                }, 2000);
                
                this.updateToolsInfo();
                this.showSuccess(`已应用 ${this.selectedTools.length} 个工具`);
            } else {
                throw new Error('应用工具选择失败');
            }
        } catch (error) {
            console.error('应用工具选择失败:', error);
            this.showError('应用工具选择失败');
            button.textContent = originalText;
            button.disabled = false;
        }
    }
    
    updateToolsCounter() {
        document.getElementById('selectedCount').textContent = this.selectedTools.length;
        document.getElementById('totalCount').textContent = this.availableTools.length;
    }
    
    updateToolsInfo() {
        const info = document.getElementById('toolsInfo');
        if (this.selectedTools.length === 0) {
            info.textContent = '未选择工具';
        } else {
            info.textContent = `已选择 ${this.selectedTools.length} 个工具`;
        }
        
        this.updateSendButtonState();
    }
    
    updateConnectionStatus(connected) {
        this.isConnected = connected;
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        
        if (connected) {
            dot.className = 'status-dot connected';
            text.textContent = '已连接';
        } else {
            dot.className = 'status-dot';
            text.textContent = '未连接';
        }
    }
    
    updateSendButtonState() {
        const button = document.getElementById('sendButton');
        const input = document.getElementById('messageInput');
        const hasMessage = input.value.trim().length > 0;
        const hasModel = this.currentModel !== null;
        
        button.disabled = !hasMessage || !hasModel || this.isStreaming;
    }
    
    setupEventListeners() {
        // 工具搜索
        document.getElementById('toolSearch').addEventListener('input', (e) => {
            this.filterTools(e.target.value);
        });
        
        // 应用工具选择
        document.getElementById('applyTools').addEventListener('click', () => {
            this.applyToolSelection();
        });
        
        // 模型选择
        document.getElementById('modelSelect').addEventListener('change', (e) => {
            this.currentModel = e.target.value || null;
            this.updateSendButtonState();
        });
        
        // 消息输入
        const messageInput = document.getElementById('messageInput');
        messageInput.addEventListener('input', (e) => {
            this.autoResizeTextarea(e.target);
            this.updateCharCount(e.target.value);
            this.updateSendButtonState();
        });
        
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // 发送按钮
        document.getElementById('sendButton').addEventListener('click', () => {
            this.sendMessage();
        });
        
        // 清空对话按钮
        document.getElementById('clearChatButton').addEventListener('click', () => {
            this.clearChat();
        });
        
        // 点击聊天区域关闭弹窗
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeToolModal();
            }
        });
    }

    filterTools(query) {
        const items = document.querySelectorAll('.tool-item');
        const lowerQuery = query.toLowerCase();
        
        items.forEach(item => {
            const name = item.querySelector('.tool-name').textContent.toLowerCase();
            const description = item.querySelector('.tool-description').textContent.toLowerCase();
            const packageName = item.querySelector('.tool-package').textContent.toLowerCase();
            
            const matches = name.includes(lowerQuery) || 
                          description.includes(lowerQuery) || 
                          packageName.includes(lowerQuery);
            
            item.style.display = matches ? 'block' : 'none';
        });
    }
    
    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
    
    updateCharCount(text) {
        document.getElementById('charCount').textContent = `${text.length}/4000`;
    }
    
    async sendMessage() {
        const input = document.getElementById('messageInput');
        const message = input.value.trim();
        
        if (!message || !this.currentModel || this.isStreaming) {
            return;
        }
        
        // 清空输入框
        input.value = '';
        this.autoResizeTextarea(input);
        this.updateCharCount('');
        this.updateSendButtonState();
        
        // 显示用户消息
        this.addMessage('user', message);
        
        // 显示打字指示器
        const typingId = this.showTypingIndicator();
        
        this.isStreaming = true;
        this.updateSendButtonState();
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    model: this.currentModel,
                    session_id: this.sessionId  // 发送会话ID
                })
            });
            
            // 从响应头获取会话ID（首次对话时）
            if (!this.sessionId) {
                this.sessionId = response.headers.get('X-Session-ID');
            }
            
            // 处理流式响应，传入typingId以便移除思考中提示
            await this.handleStreamResponse(response, typingId);
            
            // 保存到本地历史
            this.messageHistory.push({
                role: 'user',
                content: message,
                timestamp: new Date()
            });
            
        } catch (error) {
            console.error('发送消息失败:', error);
            this.removeTypingIndicator(typingId);
            this.addMessage('assistant', `抱歉，发生了错误: ${error.message}`);
        } finally {
            this.isStreaming = false;
            this.updateSendButtonState();
        }
    }
    
    async handleStreamResponse(response, typingId) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let assistantMessageElement = null;
        let currentContent = '';
        let typingIndicatorRemoved = false; // 标记是否已移除思考中提示
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data.trim() === '') continue;
                        
                        try {
                            const parsed = JSON.parse(data);
                            
                            if (parsed.type === 'content') {
                                // 第一次收到内容时，移除思考中提示
                                if (!typingIndicatorRemoved) {
                                    this.removeTypingIndicator(typingId);
                                    typingIndicatorRemoved = true;
                                }
                                
                                if (!assistantMessageElement) {
                                    assistantMessageElement = this.addMessage('assistant', '');
                                }
                                currentContent += parsed.content;
                                this.updateMessageContent(assistantMessageElement, currentContent);
                            } else if (parsed.type === 'tool_calls') {
                                // 如果有工具调用但还没移除思考中提示，移除它
                                if (!typingIndicatorRemoved) {
                                    this.removeTypingIndicator(typingId);
                                    typingIndicatorRemoved = true;
                                }
                                this.showToolExecution(parsed.tool_calls);
                            } else if (parsed.type === 'tool_execution') {
                                this.updateToolExecution(parsed.tool_name, '执行中...', parsed.args);
                            } else if (parsed.type === 'tool_result') {
                                this.updateToolExecution(parsed.tool_name, parsed.result);
                            } else if (parsed.type === 'error') {
                                // 出错时也要移除思考中提示
                                if (!typingIndicatorRemoved) {
                                    this.removeTypingIndicator(typingId);
                                    typingIndicatorRemoved = true;
                                }
                                if (!assistantMessageElement) {
                                    assistantMessageElement = this.addMessage('assistant', '');
                                }
                                currentContent += `\n\n❌ 错误: ${parsed.message}`;
                                this.updateMessageContent(assistantMessageElement, currentContent);
                            } else if (parsed.type === 'end') {
                                break;
                            }
                        } catch (e) {
                            console.error('解析流数据失败:', e, data);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('读取流失败:', error);
            // 确保在出错时移除思考中提示
            if (!typingIndicatorRemoved) {
                this.removeTypingIndicator(typingId);
            }
            if (!assistantMessageElement) {
                this.addMessage('assistant', `流读取错误: ${error.message}`);
            }
        } finally {
            // 最终确保思考中提示被移除
            if (!typingIndicatorRemoved) {
                this.removeTypingIndicator(typingId);
            }
        }
    }
    
    addMessage(role, content) {
        const messagesContainer = document.getElementById('chatMessages');
        
        // 移除欢迎消息
        const welcomeMessage = messagesContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role} fade-in`;
        
        const avatar = role === 'user' ? '👤' : '🤖';
        
        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">${this.formatMessage(content)}</div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        
        return messageDiv;
    }
    
    updateMessageContent(messageElement, content) {
        const contentElement = messageElement.querySelector('.message-content');
        contentElement.innerHTML = this.formatMessage(content);
        this.scrollToBottom();
    }
    
    formatMessage(content) {
        if (!content) return '';
        
        // 简单的 Markdown 格式化
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
    
    showTypingIndicator() {
        const messagesContainer = document.getElementById('chatMessages');
        const typingDiv = document.createElement('div');
        const typingId = Date.now();
        
        typingDiv.className = 'message assistant fade-in';
        typingDiv.id = `typing-${typingId}`;
        typingDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content typing-indicator">
                正在思考
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
        
        return typingId;
    }
    
    removeTypingIndicator(typingId) {
        const typingElement = document.getElementById(`typing-${typingId}`);
        if (typingElement) {
            typingElement.remove();
        }
    }
    
    showToolExecution(toolCalls) {
        const messagesContainer = document.getElementById('chatMessages');
        
        toolCalls.forEach(toolCall => {
            const toolDiv = document.createElement('div');
            toolDiv.className = 'tool-execution fade-in';
            toolDiv.id = `tool-${toolCall.function.name}`;
            
            toolDiv.innerHTML = `
                <div class="tool-execution-header">
                    🔧 执行工具: ${toolCall.function.name}
                </div>
                <div class="tool-execution-result">准备执行...</div>
            `;
            
            messagesContainer.appendChild(toolDiv);
        });
        
        this.scrollToBottom();
    }
    
    updateToolExecution(toolName, result, args = null) {
        const toolElement = document.getElementById(`tool-${toolName}`);
        if (!toolElement) return;
        
        const resultElement = toolElement.querySelector('.tool-execution-result');
        
        if (args) {
            resultElement.innerHTML = `
                <strong>参数:</strong> ${JSON.stringify(args, null, 2)}
                <br><strong>状态:</strong> ${result}
            `;
        } else {
            resultElement.innerHTML = `<strong>结果:</strong><br>${result}`;
        }
        
        this.scrollToBottom();
    }
    
    scrollToBottom() {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // 修改清空对话方法
    async clearChat() {
        // 调用后端API清空服务器端的对话历史
        if (this.sessionId) {
            try {
                await fetch('/api/chat/clear', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        session_id: this.sessionId
                    })
                });
            } catch (error) {
                console.error('清空服务器对话历史失败:', error);
            }
        }
        
        // 清空本地状态
        this.sessionId = null;
        this.messageHistory = [];
        const messagesContainer = document.getElementById('chatMessages');
        
        // 清空所有消息
        messagesContainer.innerHTML = '';
        
        // 显示欢迎消息
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'welcome-message fade-in';
        welcomeDiv.innerHTML = `
            <h3>👋 欢迎使用MCP工具助手</h3>
            <p>请先在左侧选择要使用的工具，然后选择AI模型开始对话。</p>
            <div class="quick-actions">
                <button class="quick-action" onclick="insertMessage('帮我计算 25 * 36 + 78')">
                    计算数学表达式
                </button>
                <button class="quick-action" onclick="insertMessage('分析这段文本的统计信息')">
                    文本分析
                </button>
                <button class="quick-action" onclick="insertMessage('显示当前系统信息')">
                    系统信息
                </button>
            </div>
        `;
        
        messagesContainer.appendChild(welcomeDiv);
        
        // 显示成功提示
        this.showSuccess('对话已清空');
    }

    // 添加获取对话历史的方法
    async loadChatHistory() {
        if (!this.sessionId) return;
        
        try {
            const response = await fetch(`/api/chat/history/${this.sessionId}`);
            if (response.ok) {
                const history = await response.json();
                // 渲染历史消息到UI
                this.renderChatHistory(history);
            }
        } catch (error) {
            console.error('加载对话历史失败:', error);
        }
    }

    // 渲染历史消息
    renderChatHistory(history) {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = '';
        
        history.messages.forEach(msg => {
            this.addMessage(msg.role, msg.content);
        });
    }
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification ${type} fade-in`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--background-primary);
            color: var(--text-primary);
            padding: 16px 20px;
            border-radius: var(--radius-medium);
            box-shadow: var(--shadow-medium);
            border-left: 4px solid ${type === 'success' ? 'var(--success-color)' : type === 'error' ? 'var(--error-color)' : 'var(--primary-color)'};
            z-index: 1001;
            max-width: 300px;
            word-wrap: break-word;
        `;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // 自动移除
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
    
    closeToolModal() {
        const modal = document.getElementById('toolModal');
        modal.classList.remove('show');
    }
    
    updateUI() {
        this.updateToolsInfo();
        this.updateSendButtonState();
    }
}

// 全局函数
function insertMessage(text) {
    const input = document.getElementById('messageInput');
    input.value = text;
    app.autoResizeTextarea(input);
    app.updateCharCount(text);
    app.updateSendButtonState();
    input.focus();
}

function closeToolModal() {
    app.closeToolModal();
}

// 初始化应用
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new MCPApp();
});

// 键盘快捷键
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K 聚焦到工具搜索
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('toolSearch').focus();
    }
    
    // Ctrl/Cmd + Enter 发送消息
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        app.sendMessage();
    }
    
    // Escape 清空输入
    if (e.key === 'Escape') {
        const input = document.getElementById('messageInput');
        if (input.value) {
            input.value = '';
            app.autoResizeTextarea(input);
            app.updateCharCount('');
            app.updateSendButtonState();
        }
    }
});

// 错误处理
window.addEventListener('error', (e) => {
    console.error('全局错误:', e.error);
    if (app) {
        app.showError('发生了未预期的错误，请刷新页面重试');
    }
});

// 网络状态监听
window.addEventListener('online', () => {
    if (app) {
        app.updateConnectionStatus(true);
        app.showSuccess('网络连接已恢复');
    }
});

window.addEventListener('offline', () => {
    if (app) {
        app.updateConnectionStatus(false);
        app.showError('网络连接已断开');
    }
});

// 防止页面意外刷新
window.addEventListener('beforeunload', (e) => {
    if (app && app.isStreaming) {
        e.preventDefault();
        e.returnValue = '正在进行对话，确定要离开吗？';
        return e.returnValue;
    }
});