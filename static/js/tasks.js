// 任务调度系统前端逻辑
let currentTasks = [];
let currentExecutions = [];
let availableTools = [];
let schedulerRunning = false;
let deleteTaskId = null;

// 初始化
window.addEventListener('DOMContentLoaded', function() {
    loadSchedulerStatus();
    loadTasks();
    loadTools();
    loadExecutionHistory();
    
    // 绑定标签切换事件
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', handleTabSwitch);
    });
    
    // 绑定表单提交事件
    document.getElementById('createTaskForm').addEventListener('submit', handleCreateTask);
    
    // 绑定刷新按钮
    document.getElementById('refreshBtn').addEventListener('click', refreshAll);
    
    // 绑定调度器开关
    document.getElementById('toggleSchedulerBtn').addEventListener('click', toggleScheduler);
    
    // 绑定工具搜索功能
    const toolSearch = document.getElementById('toolSearch');
    if (toolSearch) {
        toolSearch.addEventListener('input', handleToolSearch);
    }
    
    // 定时刷新状态
    setInterval(loadSchedulerStatus, 30000);
});

// 标签切换
function handleTabSwitch(event) {
    const tabName = event.target.dataset.tab;
    
    // 移除所有活动状态
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    // 添加活动状态
    event.target.classList.add('active');
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

// 加载调度器状态
async function loadSchedulerStatus() {
    try {
        const response = await fetch('/api/tasks/scheduler/status');
        const data = await response.json();
        
        schedulerRunning = data.running;
        
        const statusIndicator = document.getElementById('schedulerStatus');
        const statusText = document.getElementById('schedulerText');
        const toggleBtn = document.getElementById('toggleSchedulerBtn');
        
        if (data.running) {
            statusIndicator.className = 'status-indicator active';
            statusText.textContent = '调度器状态: 运行中';
            toggleBtn.textContent = '停止调度器';
            toggleBtn.className = 'btn btn-warning';
        } else {
            statusIndicator.className = 'status-indicator inactive';
            statusText.textContent = '调度器状态: 已停止';
            toggleBtn.textContent = '启动调度器';
            toggleBtn.className = 'btn btn-success';
        }
        
        document.getElementById('totalTasks').textContent = data.total_tasks || 0;
        document.getElementById('activeTasks').textContent = data.active_tasks || 0;
        document.getElementById('executionCount').textContent = data.total_executions || 0;
        
    } catch (error) {
        console.error('Failed to load scheduler status:', error);
    }
}

// 加载任务列表
async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();
        
        currentTasks = data.tasks || [];
        
        // 为每个任务加载上次执行的基本信息
        for (let task of currentTasks) {
            if (task.last_execution_file) {
                try {
                    const filename = encodeURIComponent(task.last_execution_file);
                    const execResponse = await fetch(`/api/tasks/executions/file/${filename}/summary`);
                    if (execResponse.ok) {
                        const execData = await execResponse.json();
                        if (execData.success && execData.execution) {
                            task.last_execution_summary = execData.execution;
                        }
                    } else {
                        console.warn(`执行文件 ${task.last_execution_file} 不存在，跳过摘要加载`);
                    }
                } catch (error) {
                    console.error(`Failed to load execution summary for ${task.id}:`, error);
                }
            }
        }
        
        renderTasks(currentTasks);
        
    } catch (error) {
        console.error('Failed to load tasks:', error);
    }
}

// 渲染任务列表
function renderTasks(tasks) {
    const taskGrid = document.getElementById('taskGrid');
    
    if (tasks.length === 0) {
        taskGrid.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <h3>暂无任务</h3>
                <p>点击"创建任务"标签开始创建您的第一个定时任务</p>
            </div>
        `;
        return;
    }
    
    taskGrid.innerHTML = tasks.map(task => `
        <div class="task-card">
            <div class="task-header">
                <div>
                    <div class="task-title">${task.name}</div>
                    <div class="task-id">${task.id.slice(0, 8)}...</div>
                </div>
                <div class="task-status status-${task.status}">${task.status}</div>
            </div>
            
            <div class="task-info">
                <div class="info-row">
                    <span class="info-label">执行间隔:</span>
                    <span class="info-value">${task.interval_minutes} 分钟</span>
                </div>
                <div class="info-row">
                    <span class="info-label">已执行:</span>
                    <span class="info-value">${task.current_executions} / ${task.max_executions === -1 ? '∞' : task.max_executions}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">状态:</span>
                    <span class="info-value">${task.is_active ? '活跃' : '已停用'}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">下次执行:</span>
                    <span class="info-value">${formatDateTime(task.next_execution_time)}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">创建时间:</span>
                    <span class="info-value">${formatDateTime(task.created_at)}</span>
                </div>
                ${task.last_execution_summary ? `
                <div class="info-row">
                    <span class="info-label">上次执行:</span>
                    <span class="info-value" style="color: var(--${task.last_execution_summary.status === 'completed' ? 'success' : task.last_execution_summary.status === 'failed' ? 'error' : 'warning'}-color);">
                        ${task.last_execution_summary.status} (${formatDateTime(task.last_execution_summary.start_time)})
                    </span>
                </div>
                ` : task.last_execution_file ? `
                <div class="info-row">
                    <span class="info-label">上次执行:</span>
                    <span class="info-value" style="color: var(--text-secondary);">已执行</span>
                </div>
                ` : ''}
            </div>
            
            <div class="task-actions">
                <button class="btn" onclick="viewTaskDetails('${task.id}')">详情</button>
                <button class="btn" onclick="editTask('${task.id}')">编辑</button>
                <button class="btn ${task.is_active ? 'btn-warning' : 'btn-success'}" 
                        onclick="toggleTaskStatus('${task.id}', ${!task.is_active})">
                    ${task.is_active ? '停用' : '启用'}
                </button>
                <button class="btn btn-danger" onclick="showDeleteConfirm('${task.id}')">删除</button>
                <button class="btn" onclick="resetTaskExecutions('${task.id}')">重置</button>
                ${task.last_execution_file ? `<button class="btn btn-primary" onclick="viewLastExecution('${task.id}')">上次执行</button>` : ''}
            </div>
        </div>
    `).join('');
}

// 加载工具列表
async function loadTools() {
    try {
        const [toolsResponse, configResponse] = await Promise.all([
            fetch('/api/tools'),
            fetch('/api/config')
        ]);
        
        const toolsData = await toolsResponse.json();
        const configData = await configResponse.json();
        
        availableTools = toolsData.tools || [];
        renderToolsList(availableTools);
        
        // 加载模型列表
        const modelSelect = document.getElementById('taskModel');
        if (modelSelect && configData.models) {
            modelSelect.innerHTML = '';
            
            // 添加默认选项
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = '选择模型...';
            modelSelect.appendChild(defaultOption);
            
            // 添加可用模型
            configData.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name || model.id;
                modelSelect.appendChild(option);
            });
        }
        
    } catch (error) {
        console.error('Failed to load tools:', error);
    }
}

// 渲染工具列表
function renderToolsList(tools) {
    const toolsList = document.getElementById('toolsList');
    
    if (tools.length === 0) {
        toolsList.innerHTML = '<div class="empty-state">暂无可用工具</div>';
        return;
    }
    
    toolsList.innerHTML = tools.map(tool => `
        <div class="checkbox-item">
            <input type="checkbox" id="tool-${tool.name}" name="tools" value="${tool.name}">
            <label for="tool-${tool.name}">
                <strong>${tool.name}</strong> - ${tool.description}
            </label>
        </div>
    `).join('');
}

// 处理工具搜索
function handleToolSearch(event) {
    const searchTerm = event.target.value.toLowerCase();
    const toolsList = document.getElementById('toolsList');
    
    if (!availableTools || availableTools.length === 0) return;
    
    const filteredTools = availableTools.filter(tool => 
        tool.name.toLowerCase().includes(searchTerm) ||
        tool.description.toLowerCase().includes(searchTerm) ||
        (tool.package && tool.package.toLowerCase().includes(searchTerm))
    );
    
    if (filteredTools.length === 0) {
        toolsList.innerHTML = '<div class="empty-state">未找到匹配的工具</div>';
        return;
    }
    
    renderToolsList(filteredTools);
}

// 加载执行历史
async function loadExecutionHistory() {
    try {
        const response = await fetch('/api/tasks/executions');
        const data = await response.json();
        
        currentExecutions = data.executions || [];
        renderExecutionHistory(currentExecutions);
        
    } catch (error) {
        console.error('Failed to load execution history:', error);
    }
}

// 搜索执行历史
function filterExecutions() {
    const searchTerm = document.getElementById('historySearch').value.toLowerCase();
    const filteredExecutions = currentExecutions.filter(exec => 
        exec.task_name.toLowerCase().includes(searchTerm) ||
        exec.status.toLowerCase().includes(searchTerm) ||
        (exec.task_id && exec.task_id.toLowerCase().includes(searchTerm))
    );
    renderExecutionHistory(filteredExecutions);
}

// 载入最近50条执行记录
async function loadRecentExecutions(limit = 50) {
    try {
        const response = await fetch(`/api/tasks/executions/recent?limit=${limit}`);
        const data = await response.json();
        
        currentExecutions = data.executions || [];
        renderExecutionHistory(currentExecutions);
        
        // 清空搜索框
        document.getElementById('historySearch').value = '';
        
    } catch (error) {
        console.error('Failed to load recent executions:', error);
        alert('加载执行记录失败');
    }
}

// 选择历史文件
async function selectHistoryFile() {
    // 创建文件输入元素
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.json';
    
    fileInput.onchange = async function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        try {
            const content = await file.text();
            const executionData = JSON.parse(content);
            
            // 显示单个文件的执行详情
            if (executionData.task_name) {
                renderExecutionDetail({
                    id: executionData.execution_id || '未知',
                    task_name: executionData.task_name,
                    start_time: executionData.start_time,
                    end_time: executionData.end_time,
                    status: executionData.status,
                    chat_data: executionData
                });
            } else {
                alert('无效的执行记录文件');
            }
            
        } catch (error) {
            console.error('Failed to load history file:', error);
            alert('加载文件失败，请确保是有效的JSON格式');
        }
    };
    
    fileInput.click();
}

// 渲染执行历史
function renderExecutionHistory(executions) {
    const executionList = document.getElementById('executionList');
    
    if (executions.length === 0) {
        executionList.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <h3>暂无执行记录</h3>
                <p>任务执行后，执行记录将显示在这里</p>
                <p style="margin-top: 12px; font-size: 14px;">
                    <button class="btn" onclick="loadRecentExecutions(50)">载入最近50条记录</button>
                    <button class="btn" onclick="selectHistoryFile()">或选择历史文件</button>
                </p>
            </div>
        `;
        return;
    }
    
    executionList.innerHTML = executions.map(exec => `
        <div class="execution-item">
            <div class="execution-info">
                <div class="execution-title">${exec.task_name}</div>
                <div class="execution-meta">
                    开始时间: ${formatDateTime(exec.start_time)} | 
                    状态: ${exec.status} |
                    ${exec.end_time ? '耗时: ' + formatDuration(exec.start_time, exec.end_time) : '运行中'}
                    ${exec.task_id ? `| 任务ID: ${exec.task_id.slice(0, 8)}...` : ''}
                </div>
            </div>
            <div class="execution-actions">
                ${exec.chat_file || exec.chat_data ? `
                    <button class="btn" onclick="viewExecutionDetail('${exec.id}')">查看详情</button>
                ` : ''}
                ${exec.chat_file ? `
                    <button class="btn" onclick="downloadChat('${exec.chat_file}')">下载记录</button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

// 创建任务
async function handleCreateTask(event) {
    event.preventDefault();
    
    const formData = {
        name: document.getElementById('taskName').value,
        prompt: document.getElementById('taskPrompt').value,
        user_input: document.getElementById('taskUserInput').value,
        model: document.getElementById('taskModel').value,
        tools: Array.from(document.querySelectorAll('input[name="tools"]:checked')).map(cb => cb.value),
        interval_minutes: parseInt(document.getElementById('taskInterval').value),
        max_executions: parseInt(document.getElementById('taskMaxExecutions').value)
    };
    
    // 验证必填字段
    if (!formData.name || !formData.user_input || !formData.model) {
        alert('请填写所有必填字段：任务名称、用户输入、选择模型');
        return;
    }
    
    try {
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('任务创建成功！');
            clearForm();
            loadTasks();
            // 切换到任务列表标签
            document.querySelector('[data-tab="tasks"]').click();
        } else {
            alert('创建失败: ' + result.error);
        }
        
    } catch (error) {
        console.error('Failed to create task:', error);
        alert('创建任务失败');
    }
}

// 切换任务状态
async function toggleTaskStatus(taskId, newStatus) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ is_active: newStatus })
        });
        
        const result = await response.json();
        
        if (result.success) {
            loadTasks();
        } else {
            alert('操作失败: ' + result.error);
        }
        
    } catch (error) {
        console.error('Failed to toggle task status:', error);
        alert('操作失败');
    }
}

// 显示删除确认
function showDeleteConfirm(taskId) {
    deleteTaskId = taskId;
    document.getElementById('confirmDeleteModal').classList.add('show');
}

// 确认删除任务
async function confirmDeleteTask() {
    if (!deleteTaskId) return;
    
    try {
        const response = await fetch(`/api/tasks/${deleteTaskId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            loadTasks();
            closeModal('confirmDeleteModal');
        } else {
            alert('删除失败: ' + result.error);
        }
        
    } catch (error) {
        console.error('Failed to delete task:', error);
        alert('删除失败');
    }
}

// 查看任务详情
async function viewTaskDetails(taskId) {
    const task = currentTasks.find(t => t.id === taskId);
    if (!task) return;
    
    const content = `
        <div class="form-group">
            <label class="form-label">任务ID</label>
            <input type="text" class="form-input" value="${task.id}" readonly>
        </div>
        <div class="form-group">
            <label class="form-label">任务名称</label>
            <input type="text" class="form-input" value="${task.name}" readonly>
        </div>
        <div class="form-group">
            <label class="form-label">系统提示词</label>
            <textarea class="form-textarea" readonly>${task.prompt}</textarea>
        </div>
        <div class="form-group">
            <label class="form-label">用户输入</label>
            <textarea class="form-textarea" readonly>${task.user_input}</textarea>
        </div>
        <div class="form-group">
            <label class="form-label">使用模型</label>
            <input type="text" class="form-input" value="${task.model}" readonly>
        </div>
        <div class="form-group">
            <label class="form-label">工具列表</label>
            <div>${task.tools.join(', ') || '无'}</div>
        </div>
        <div class="form-group">
            <label class="form-label">执行间隔</label>
            <input type="text" class="form-input" value="${task.interval_minutes} 分钟" readonly>
        </div>
        <div class="form-group">
            <label class="form-label">执行次数</label>
            <input type="text" class="form-input" value="${task.current_executions} / ${task.max_executions === -1 ? '∞' : task.max_executions}" readonly>
        </div>
        <div class="form-group">
            <label class="form-label">下次执行时间</label>
            <input type="text" class="form-input" value="${formatDateTime(task.next_execution_time)}" readonly>
        </div>
        <div class="form-group">
            <label class="form-label">创建时间</label>
            <input type="text" class="form-input" value="${formatDateTime(task.created_at)}" readonly>
        </div>
    `;
    
    document.getElementById('taskDetailContent').innerHTML = content;
    document.getElementById('taskDetailModal').classList.add('show');
}

// 重置任务执行次数
async function resetTaskExecutions(taskId) {
    if (!confirm('确定要重置该任务的执行次数吗？这将把已执行次数重置为0。')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/tasks/${taskId}/reset`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('任务重置成功！执行次数已重置为0。');
            loadTasks();
        } else {
            alert('重置失败: ' + result.error);
        }
        
    } catch (error) {
        console.error('Failed to reset task:', error);
        alert('重置失败');
    }
}

// 切换调度器状态
async function toggleScheduler() {
    const toggleBtn = document.getElementById('toggleSchedulerBtn');
    
    // 禁用按钮并显示加载状态
    toggleBtn.disabled = true;
    toggleBtn.textContent = schedulerRunning ? '停止中...' : '启动中...';
    toggleBtn.className = 'btn';
    
    try {
        const action = schedulerRunning ? 'stop' : 'start';
        const response = await fetch(`/api/tasks/scheduler/${action}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            await loadSchedulerStatus();
        } else {
            alert('操作失败: ' + result.error);
            // 重新加载状态以确保按钮显示正确
            await loadSchedulerStatus();
        }
        
    } catch (error) {
        console.error('Failed to toggle scheduler:', error);
        alert('操作失败');
        // 重新加载状态以确保按钮显示正确
        await loadSchedulerStatus();
    } finally {
        // 恢复按钮状态
        toggleBtn.disabled = false;
    }
}

// 下载聊天记录
function downloadChat(filename) {
    window.open(`/api/tasks/executions/${filename}/download`, '_blank');
}

// 清空表单
function clearForm() {
    document.getElementById('createTaskForm').reset();
    document.getElementById('createTaskForm').dataset.editMode = 'false';
    document.getElementById('createTaskForm').dataset.taskId = '';
    document.querySelector('#createTaskForm button[type="submit"]').textContent = '创建任务';
}

// 编辑任务
async function editTask(taskId) {
    try {
        const response = await fetch(`/api/tasks`);
        const data = await response.json();
        const task = data.tasks.find(t => t.id === taskId);
        
        if (!task) {
            alert('任务不存在');
            return;
        }
        
        // 填充表单
        document.getElementById('taskName').value = task.name;
        document.getElementById('taskPrompt').value = task.prompt || '';
        document.getElementById('taskUserInput').value = task.user_input;
        document.getElementById('taskModel').value = task.model;
        document.getElementById('taskInterval').value = task.interval_minutes;
        document.getElementById('taskMaxExecutions').value = task.max_executions;
        
        // 选中工具
        const toolCheckboxes = document.querySelectorAll('input[name="tools"]');
        toolCheckboxes.forEach(checkbox => {
            checkbox.checked = task.tools.includes(checkbox.value);
        });
        
        // 设置编辑模式
        const form = document.getElementById('createTaskForm');
        form.dataset.editMode = 'true';
        form.dataset.taskId = taskId;
        document.querySelector('#createTaskForm button[type="submit"]').textContent = '更新任务';
        
        // 切换到创建任务标签
        document.querySelector('[data-tab="create"]').click();
        
    } catch (error) {
        console.error('Failed to load task for editing:', error);
        alert('加载任务失败');
    }
}

// 查看上次执行记录
async function viewLastExecution(taskId) {
    try {
        const task = currentTasks.find(t => t.id === taskId);
        if (!task || !task.last_execution_file) {
            alert('没有上次执行记录');
            return;
        }
        
        // 直接加载指定的执行文件
        const filename = encodeURIComponent(task.last_execution_file);
        const response = await fetch(`/api/tasks/executions/file/${filename}`);
        
        if (!response.ok) {
            alert(`获取执行记录失败: ${response.status}`);
            return;
        }
        
        const data = await response.json();
        
        if (!data.success) {
            alert(data.error || '获取执行记录失败');
            return;
        }
        
        const execution = data.execution;
        renderExecutionDetail(execution);
        
    } catch (error) {
        console.error('Failed to load latest execution:', error);
        alert('加载执行记录失败');
    }
}

// 查看执行详情
async function viewExecutionDetail(executionId) {
    try {
        const execution = currentExecutions.find(e => e.id === executionId);
        if (!execution) {
            alert('未找到执行记录');
            return;
        }
        
        // 如果执行记录有chat_file，获取详细数据
        if (execution.chat_file) {
            const response = await fetch(`/api/tasks/executions/${execution.id}/detail`);
            const data = await response.json();
            
            if (data.success) {
                renderExecutionDetail(data.execution);
            } else {
                // 使用现有数据渲染
                renderExecutionDetail(execution);
            }
        } else {
            // 直接使用现有数据渲染
            renderExecutionDetail(execution);
        }
        
    } catch (error) {
        console.error('Failed to load execution detail:', error);
        alert('加载执行详情失败');
    }
}

// 渲染执行详情
function renderExecutionDetail(execution) {
    let conversationFlow = '';
    
    if (execution.chat_data && execution.chat_data.messages) {
        const messages = execution.chat_data.messages;
        conversationFlow = `
            <div class="execution-conversation">
                <h4>完整对话流程</h4>
                <div class="conversation-messages">
                    ${messages.map((msg, index) => `
                        <div class="message ${msg.role}">
                            <div class="message-role">${getRoleDisplayName(msg.role)}</div>
                            <div class="message-content">
                                ${msg.content ? msg.content.replace(/\n/g, '<br>') : ''}
                                ${msg.tool_calls ? `
                                    <div class="tool-calls">
                                        <strong>🛠️ 工具调用:</strong>
                                        ${msg.tool_calls.map(tc => `
                                            <div class="tool-call">
                                                <div><strong>工具名称:</strong> ${tc.function.name}</div>
                                                <div><strong>调用参数:</strong> <pre>${JSON.stringify(JSON.parse(tc.function.arguments), null, 2)}</pre></div>
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                                ${msg.tool_call_id ? `
                                    <div class="tool-result">
                                        <strong>📋 工具返回:</strong>
                                        <pre>${msg.content}</pre>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } else if (execution.ai_conversation && execution.ai_conversation.length > 0) {
        conversationFlow = `
            <div class="execution-conversation">
                <h4>完整对话流程</h4>
                <div class="conversation-messages">
                    ${execution.ai_conversation.map((msg, index) => `
                        <div class="message ${msg.role}">
                            <div class="message-role">${getRoleDisplayName(msg.role)}</div>
                            <div class="message-content">
                                ${msg.content ? msg.content.replace(/\n/g, '<br>') : ''}
                                ${msg.tool_calls ? `
                                    <div class="tool-calls">
                                        <strong>🛠️ 工具调用:</strong>
                                        ${msg.tool_calls.map(tc => `
                                            <div class="tool-call">
                                                <div><strong>工具名称:</strong> ${tc.function.name}</div>
                                                <div><strong>调用参数:</strong> <pre>${JSON.stringify(JSON.parse(tc.function.arguments), null, 2)}</pre></div>
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    const content = `
        <div class="execution-detail-header">
            <h3>${execution.task_name} - 执行详情</h3>
            <div class="execution-meta">
                <div><strong>执行ID:</strong> ${execution.id}</div>
                <div><strong>开始时间:</strong> ${formatDateTime(execution.start_time)}</div>
                <div><strong>结束时间:</strong> ${execution.end_time ? formatDateTime(execution.end_time) : '未完成'}</div>
                <div><strong>状态:</strong> <span class="status-${execution.status}">${execution.status}</span></div>
            </div>
        </div>
        
        ${execution.execution_data ? `
        <div class="execution-config">
            <h4>任务配置</h4>
            <div class="config-grid">
                <div><strong>模型:</strong> ${execution.execution_data.model || '未知'}</div>
                <div><strong>工具:</strong> ${execution.execution_data.tools_used.join(', ') || '无'}</div>
                <div><strong>用户输入:</strong> ${execution.execution_data.user_input || '无'}</div>
            </div>
        </div>
        ` : ''}
        
        ${conversationFlow || '<div class="empty-state">暂无对话记录</div>'}
    `;
    
    document.getElementById('executionDetailContent').innerHTML = content;
    document.getElementById('executionDetailModal').classList.add('show');
}

// 修改表单提交处理
async function handleCreateTask(event) {
    event.preventDefault();
    
    const form = document.getElementById('createTaskForm');
    const isEdit = form.dataset.editMode === 'true';
    const taskId = form.dataset.taskId;
    
    const formData = {
        name: document.getElementById('taskName').value,
        prompt: document.getElementById('taskPrompt').value,
        user_input: document.getElementById('taskUserInput').value,
        model: document.getElementById('taskModel').value,
        tools: Array.from(document.querySelectorAll('input[name="tools"]:checked')).map(cb => cb.value),
        interval_minutes: parseInt(document.getElementById('taskInterval').value),
        max_executions: parseInt(document.getElementById('taskMaxExecutions').value)
    };
    
    // 验证必填字段
    if (!formData.name || !formData.user_input || !formData.model) {
        alert('请填写所有必填字段：任务名称、用户输入、选择模型');
        return;
    }
    
    try {
        const url = isEdit ? `/api/tasks/${taskId}` : '/api/tasks';
        const method = isEdit ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(isEdit ? '任务更新成功！' : '任务创建成功！');
            clearForm();
            loadTasks();
            // 切换到任务列表标签
            document.querySelector('[data-tab="tasks"]').click();
        } else {
            alert(isEdit ? '更新失败: ' : '创建失败: ' + result.error);
        }
        
    } catch (error) {
        console.error('Failed to save task:', error);
        alert(isEdit ? '更新任务失败' : '创建任务失败');
    }
}

// 关闭弹窗
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
    if (modalId === 'confirmDeleteModal') {
        deleteTaskId = null;
    }
}

// 刷新所有数据
function refreshAll() {
    loadSchedulerStatus();
    loadTasks();
    loadExecutionHistory();
}

// 工具函数
function formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return 'N/A';
    const date = new Date(dateTimeStr);
    return date.toLocaleString('zh-CN');
}

function getRoleDisplayName(role) {
    const roleMap = {
        'user': '👤 用户',
        'assistant': '🤖 AI助手',
        'system': '⚙️ 系统',
        'tool': '🔧 工具'
    };
    return roleMap[role] || role;
}

function formatDuration(startStr, endStr) {
    const start = new Date(startStr);
    const end = new Date(endStr);
    const diff = end - start;
    
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    
    if (minutes > 0) {
        return `${minutes}分${seconds}秒`;
    }
    return `${seconds}秒`;
}

// 点击模态框外部关闭
window.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('show');
    }
});