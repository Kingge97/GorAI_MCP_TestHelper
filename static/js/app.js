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
        
        // 添加系统提示词
        this.systemPrompt = '';
        
        // 添加工具调用计数器，避免ID重复
        this.toolCallCounter = 0;
        
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
        const sendButton = document.getElementById('sendButton');
        const stopButton = document.getElementById('stopButton');
        const input = document.getElementById('messageInput');
        const hasMessage = input.value.trim().length > 0;
        const hasModel = this.currentModel !== null;
        
        if (this.isStreaming) {
            sendButton.style.display = 'none';
            stopButton.style.display = 'flex';
        } else {
            sendButton.style.display = 'flex';
            stopButton.style.display = 'none';
            sendButton.disabled = !hasMessage || !hasModel;
        }
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
            if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                this.sendMessage();
            }
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                const input = e.target;
                const start = input.selectionStart;
                const end = input.selectionEnd;
                const value = input.value;
                
                // 插入换行符
                input.value = value.substring(0, start) + '\n' + value.substring(end);
                
                // 移动光标到新行的开始位置
                input.selectionStart = input.selectionEnd = start + 1;
                
                // 重新调整文本框大小
                this.autoResizeTextarea(input);
                this.updateCharCount(input.value);
            }
        });
        
        // 发送按钮
        document.getElementById('sendButton').addEventListener('click', () => {
            this.sendMessage();
        });
        
        // 停止按钮
        document.getElementById('stopButton').addEventListener('click', () => {
            this.interruptChat();
        });
        
        // 保存对话按钮
        document.getElementById('saveChatButton').addEventListener('click', () => {
            this.saveChatHistory();
        });
        
        // 加载对话按钮
        document.getElementById('loadChatButton').addEventListener('click', () => {
            this.loadChatHistory();
        });
        
        // 清空对话按钮
        document.getElementById('clearChatButton').addEventListener('click', () => {
            this.clearChat();
        });
        
        // 系统提示词按钮
        document.getElementById('systemPromptButton').addEventListener('click', () => {
            this.showSystemPromptModal();
        });
        
        // 点击聊天区域关闭弹窗
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeModal(e.target);
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
                    session_id: this.sessionId,  // 发送会话ID
                    system_prompt: this.systemPrompt  // 发送系统提示词
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
        // 明确指定UTF-8解码器
        const decoder = new TextDecoder('utf-8');
        
        let assistantMessageElement = null;
        let currentContent = '';
        let typingIndicatorRemoved = false; // 标记是否已移除思考中提示
        let isAfterToolCall = false; // 标记是否在工具调用之后
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data.trim() === '') continue;
                        
                        try {
                            const parsed = JSON.parse(data);
                            console.log('收到流数据:', parsed);
                            
                            if (parsed.type === 'content') {
                                // 第一次收到内容时，移除思考中提示
                                if (!typingIndicatorRemoved) {
                                    this.removeTypingIndicator(typingId);
                                    typingIndicatorRemoved = true;
                                }
                                
                                // 如果是工具调用后的内容，创建新的消息元素
                                if (isAfterToolCall && (!assistantMessageElement || currentContent.includes('思考过程'))) {
                                    assistantMessageElement = this.addMessage('assistant', '');
                                    currentContent = '';
                                    isAfterToolCall = false;
                                }
                                
                                if (!assistantMessageElement) {
                                    assistantMessageElement = this.addMessage('assistant', '');
                                }
                                currentContent += parsed.content;
                                this.updateMessageContent(assistantMessageElement, currentContent);
                            } 
                            else if (parsed.type === 'tool_calls') {
                                console.log('处理工具调用:', parsed.tool_calls);
                                // 如果有工具调用但还没移除思考中提示，移除它
                                if (!typingIndicatorRemoved) {
                                    this.removeTypingIndicator(typingId);
                                    typingIndicatorRemoved = true;
                                }
                                this.showToolExecution(parsed.tool_calls);
                                isAfterToolCall = true; // 标记后续内容需要新的消息元素
                            } 
                            else if (parsed.type === 'tool_execution') {
                                console.log('工具执行中:', parsed);
                                this.updateToolExecution(parsed.tool_call_id || parsed.tool_name, '执行中...', parsed.args);
                            } 
                            else if (parsed.type === 'tool_result') {
                                console.log('工具执行结果:', parsed);
                                this.updateToolExecution(parsed.tool_call_id || parsed.tool_name, parsed.result);
                            } 
                            else if (parsed.type === 'error') {
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
                            } 
                            else if (parsed.type === 'interrupted') {
                                console.log('对话被中断');
                                if (!typingIndicatorRemoved) {
                                    this.removeTypingIndicator(typingId);
                                    typingIndicatorRemoved = true;
                                }
                                this.addMessage('assistant', '⚠️ 对话已被用户中断');
                                this.isStreaming = false;
                                this.updateSendButtonState();
                                break;
                            }
                            else if (parsed.type === 'end') {
                                console.log('流结束');
                                this.isStreaming = false;
                                this.updateSendButtonState();
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
            this.isStreaming = false;
            this.updateSendButtonState();
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
        
        console.log('显示工具执行:', toolCalls);
        
        toolCalls.forEach(toolCall => {
            // 使用唯一ID，包含时间戳和计数器
            const uniqueId = `tool-${Date.now()}-${this.toolCallCounter++}`;
            
            const toolDiv = document.createElement('div');
            toolDiv.className = 'tool-execution fade-in';
            toolDiv.id = uniqueId;
            
            // 存储tool call ID供后续更新使用
            toolDiv.dataset.toolCallId = toolCall.id;
            toolDiv.dataset.toolName = toolCall.function.name;
            
            // 格式化参数显示
            let argsDisplay = '';
            try {
                const args = JSON.parse(toolCall.function.arguments);
                argsDisplay = `<pre>${JSON.stringify(args, null, 2)}</pre>`;
            } catch (e) {
                argsDisplay = toolCall.function.arguments;
            }
            
            toolDiv.innerHTML = `
                <div class="tool-execution-header">
                    🔧 执行工具: <strong>${toolCall.function.name}</strong>
                </div>
                <div class="tool-execution-args">
                    <strong>参数:</strong> ${argsDisplay}
                </div>
                <div class="tool-execution-result">准备执行...</div>
            `;
            
            messagesContainer.appendChild(toolDiv);
            console.log('工具执行元素已创建:', uniqueId, toolCall.id);
        });
        
        this.scrollToBottom();
    }
    
    updateToolExecution(toolCallId, result, args = null) {
        console.log('更新工具执行:', toolCallId, result);
        
        // 查找对应的工具执行元素
        const toolElement = document.querySelector(`[data-tool-call-id="${toolCallId}"]`) || 
                           document.querySelector(`[data-tool-name="${toolCallId}"]`) ||
                           document.getElementById(`tool-${toolCallId}`);
        
        if (!toolElement) {
            console.warn('未找到工具执行元素:', toolCallId);
            console.log('当前所有工具元素:', document.querySelectorAll('.tool-execution'));
            return;
        }
        
        const resultElement = toolElement.querySelector('.tool-execution-result');
        
        if (args) {
            // 如果提供了参数，说明是执行状态更新
            resultElement.innerHTML = `<strong>状态:</strong> ${result}`;
        } else {
            // 否则是最终结果
            resultElement.innerHTML = `<strong>结果:</strong><br><pre>${result}</pre>`;
        }
        
        console.log('工具执行已更新:', toolCallId);
        this.scrollToBottom();
    }
    
    scrollToBottom() {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // 移除最后两条消息（用户消息和助手消息）
    removeLastMessages() {
        const messagesContainer = document.getElementById('chatMessages');
        const messages = messagesContainer.querySelectorAll('.message');
        
        if (messages.length >= 2) {
            // 移除最后两条消息（用户消息和助手消息）
            messages[messages.length - 1].remove(); // 助手消息
            messages[messages.length - 2].remove(); // 用户消息
        } else if (messages.length === 1) {
            // 如果只有一条消息，移除它
            messages[0].remove();
        }
        
        // 如果没有消息了，显示欢迎消息
        if (messagesContainer.children.length === 0) {
            this.showWelcomeMessage();
        }
    }
    
    // 显示欢迎消息
    showWelcomeMessage() {
        const messagesContainer = document.getElementById('chatMessages');
        
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
    }
    
    // 修改清空对话方法
    async interruptChat() {
        if (!this.isStreaming || !this.sessionId) {
            return;
        }
        
        try {
            const response = await fetch('/api/chat/interrupt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showSuccess('对话已中断');
                
                // 从界面上移除最后两条消息（用户消息和助手消息）
                this.removeLastMessages();
                
            } else {
                console.error('中断对话失败:', response.status);
            }
        } catch (error) {
            console.error('中断对话失败:', error);
            this.showError('中断对话失败');
        }
    }

    async clearChat() {
        // 如果正在流式输出，先中断
        if (this.isStreaming) {
            await this.interruptChat();
        }
        
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
        this.showWelcomeMessage();
        
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
    
    // 显示系统提示词设置弹窗
    showSystemPromptModal() {
        const modal = document.getElementById('systemPromptModal');
        const textarea = document.getElementById('systemPromptInput');
        textarea.value = this.systemPrompt;
        modal.classList.add('show');
        textarea.focus();
    }
    
    // 保存系统提示词
    saveSystemPrompt() {
        const textarea = document.getElementById('systemPromptInput');
        this.systemPrompt = textarea.value.trim();
        this.closeModal(document.getElementById('systemPromptModal'));
        this.showSuccess('系统提示词已保存');
    }
    
    // 保存对话历史
    async saveChatHistory() {
        if (!this.sessionId) {
            this.showError('没有可保存的对话');
            return;
        }
        
        const filename = prompt('请输入保存文件名（不含扩展名）:', `chat_${new Date().toISOString().slice(0, 19).replace(/[:]/g, '-')}`);
        if (!filename) return;
        
        try {
            const response = await fetch('/api/chat/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    filename: filename,
                    system_prompt: this.systemPrompt
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess(`对话已保存: ${data.filename}`);
            } else {
                this.showError(data.error || '保存失败');
            }
        } catch (error) {
            console.error('保存对话失败:', error);
            this.showError('保存对话失败');
        }
    }
    
    // 加载对话历史
    async loadChatHistory() {
        try {
            const savedChats = await this.getSavedChats();
            if (savedChats.length === 0) {
                this.showError('没有已保存的对话');
                return;
            }
            
            this.showLoadChatModal(savedChats);
        } catch (error) {
            console.error('获取对话列表失败:', error);
            this.showError('获取对话列表失败');
        }
    }
    
    // 获取已保存的对话列表
    async getSavedChats() {
        const response = await fetch('/api/chat/list');
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        return data.files || [];
    }
    
    // 显示加载对话弹窗
    showLoadChatModal(files) {
        const modal = document.getElementById('loadChatModal');
        const listContainer = document.getElementById('savedChatsList');
        
        listContainer.innerHTML = '';
        
        if (files.length === 0) {
            listContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-secondary);">没有已保存的对话</div>';
        } else {
            files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'saved-chat-item';
                fileItem.style.cssText = `
                    padding: 15px;
                    border: 1px solid var(--border-color);
                    border-radius: 8px;
                    margin-bottom: 10px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                `;
                
                fileItem.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>${file.filename}</strong>
                            <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">
                                ${file.message_count || 0} 条消息 • 
                                ${new Date(file.modified).toLocaleString('zh-CN')}
                                ${file.has_system_prompt ? ' • 📋 含提示词' : ''}
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn-load-chat" data-filename="${file.filename}" 
                                    style="padding: 6px 12px; background: var(--primary-color); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                                加载
                            </button>
                            <button class="btn-delete-chat" data-filename="${file.filename}" 
                                    style="padding: 6px 12px; background: var(--error-color); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                                删除
                            </button>
                        </div>
                    </div>
                `;
                
                fileItem.addEventListener('click', (e) => {
                    if (e.target.classList.contains('btn-load-chat')) {
                        this.loadSpecificChat(e.target.dataset.filename);
                    } else if (e.target.classList.contains('btn-delete-chat')) {
                        this.deleteSavedChat(e.target.dataset.filename);
                    }
                });
                
                listContainer.appendChild(fileItem);
            });
        }
        
        modal.classList.add('show');
    }
    
    // 加载特定对话
    async loadSpecificChat(filename) {
        try {
            const response = await fetch('/api/chat/load', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: filename
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // 更新会话ID
                this.sessionId = data.session_id;
                
                // 清空当前对话
                const messagesContainer = document.getElementById('chatMessages');
                messagesContainer.innerHTML = '';
                
                // 加载历史消息
                data.messages.forEach(msg => {
                    this.addMessage(msg.role, msg.content);
                });
                
                // 加载模型和工具选择
                if (data.model) {
                    document.getElementById('modelSelect').value = data.model;
                    this.currentModel = data.model;
                }
                
                // 加载系统提示词
                if (data.system_prompt) {
                    this.systemPrompt = data.system_prompt;
                    // 更新系统提示词输入框
                    const systemPromptInput = document.getElementById('systemPromptInput');
                    if (systemPromptInput) {
                        systemPromptInput.value = data.system_prompt;
                    }
                } else {
                    this.systemPrompt = '';
                    const systemPromptInput = document.getElementById('systemPromptInput');
                    if (systemPromptInput) {
                        systemPromptInput.value = '';
                    }
                }
                
                if (data.selected_tools && data.selected_tools.length > 0) {
                    this.selectedTools = data.selected_tools;
                    // 通知后端更新工具选择
                    await fetch('/api/tools/select', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            tools: this.selectedTools
                        })
                    });
                    
                    // 重新加载工具列表
                    await this.loadTools();
                }
                
                this.closeModal(document.getElementById('loadChatModal'));
                this.showSuccess(`对话已加载: ${filename}`);
            } else {
                this.showError(data.error || '加载失败');
            }
        } catch (error) {
            console.error('加载对话失败:', error);
            this.showError('加载对话失败');
        }
    }
    
    // 删除已保存的对话
    async deleteSavedChat(filename) {
        if (!confirm(`确定要删除对话 "${filename}" 吗？此操作不可恢复。`)) {
            return;
        }
        
        try {
            const response = await fetch('/api/chat/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: filename
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess('对话已删除');
                // 刷新列表
                const savedChats = await this.getSavedChats();
                this.showLoadChatModal(savedChats);
            } else {
                this.showError(data.error || '删除失败');
            }
        } catch (error) {
            console.error('删除对话失败:', error);
            this.showError('删除对话失败');
        }
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
    
    closeModal(modal) {
        if (modal) {
            modal.classList.remove('show');
        }
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

function closeSystemPromptModal() {
    app.closeModal(document.getElementById('systemPromptModal'));
}

function saveSystemPrompt() {
    app.saveSystemPrompt();
}

function closeLoadChatModal() {
    app.closeModal(document.getElementById('loadChatModal'));
}

// 初始化应用
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new MCPApp();
});

// 键盘快捷键 - 已移除聊天历史导航快捷键，仅保留基本输入快捷键
document.addEventListener('keydown', (e) => {
    // 仅保留工具搜索聚焦快捷键
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('toolSearch').focus();
    }
    
    // 注意：Ctrl+Enter 换行功能已在消息输入框的事件监听器中处理
    // 这里不再重复处理
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