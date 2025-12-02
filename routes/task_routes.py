from flask import Blueprint, request, jsonify, send_file
from flask import current_app
import json
import os
from datetime import datetime
import logging

task_bp = Blueprint('task', __name__)
logger = logging.getLogger(__name__)

@task_bp.route('/api/tasks')
def get_tasks():
    """获取所有任务"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        tasks = task_service.get_all_tasks()
        return jsonify({
            'success': True,
            'tasks': [task.to_dict() for task in tasks]
        })
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks', methods=['POST'])
def create_task():
    """创建新任务"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        data = request.get_json()

        task_id = task_service.create_task(
            name=data['name'],
            prompt=data['prompt'],
            user_input=data['user_input'],
            tools=data['tools'],
            model=data['model'],
            interval_minutes=data['interval_minutes'],
            max_executions=data['max_executions']
        )

        return jsonify({
            'success': True,
            'task_id': task_id
        })

    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        success = task_service.delete_task(task_id)
        return jsonify({
            'success': success,
            'message': '任务已删除' if success else '任务不存在'
        })
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/<task_id>/status', methods=['PUT'])
def update_task_status(task_id):
    """更新任务状态"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        data = request.get_json()
        success = task_service.update_task(task_id, is_active=data['is_active'])
        return jsonify({
            'success': success,
            'message': '任务状态已更新' if success else '任务不存在'
        })
    except Exception as e:
        logger.error(f"更新任务状态失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    """更新任务"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        data = request.get_json()

        # 验证必填字段
        required_fields = ['name', 'prompt', 'user_input', 'tools', 'model', 'interval_minutes', 'max_executions']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400

        # 更新任务
        success = task_service.update_task(
            task_id,
            name=data['name'],
            prompt=data['prompt'],
            user_input=data['user_input'],
            tools=data['tools'],
            model=data['model'],
            interval_minutes=data['interval_minutes'],
            max_executions=data['max_executions'],
            updated_at=datetime.now().isoformat()
        )

        return jsonify({
            'success': success,
            'message': '任务已更新' if success else '任务不存在'
        })

    except Exception as e:
        logger.error(f"更新任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/scheduler/start', methods=['POST'])
def start_scheduler():
    """启动任务调度器"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        task_service.start_scheduler()
        return jsonify({
            'success': True,
            'message': '任务调度器已启动'
        })
    except Exception as e:
        logger.error(f"启动调度器失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """停止任务调度器"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        task_service.stop_scheduler()
        return jsonify({
            'success': True,
            'message': '任务调度器已停止'
        })
    except Exception as e:
        logger.error(f"停止调度器失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/scheduler/status')
def get_scheduler_status():
    """获取调度器状态"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        status = task_service.get_scheduler_status()
        return jsonify({
            'success': True,
            **status
        })
    except Exception as e:
        logger.error(f"获取调度器状态失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/executions')
def get_executions():
    """获取执行历史"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        executions = task_service.get_execution_history()
        return jsonify({
            'success': True,
            'executions': [exec.to_dict() for exec in executions]
        })
    except Exception as e:
        logger.error(f"获取执行历史失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/<task_id>/reset', methods=['POST'])
def reset_task_executions(task_id):
    """重置任务执行次数"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        success = task_service.reset_task_executions(task_id)
        return jsonify({
            'success': success,
            'message': '任务已重置' if success else '任务不存在'
        })
    except Exception as e:
        logger.error(f"重置任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/<task_id>/execution/latest')
def get_latest_execution(task_id):
    """获取任务最新的执行记录"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        executions = task_service.get_execution_history(task_id)
        if not executions:
            return jsonify({'success': False, 'error': '暂无执行记录'}), 404

        latest = executions[0]  # 最新的记录

        # 如果存在聊天文件，读取详细内容
        execution_data = latest.to_dict()
        if latest.chat_file:
            chat_path = os.path.join(task_service.get_chat_save_dir(), latest.chat_file)
            if os.path.exists(chat_path):
                with open(chat_path, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                execution_data['chat_data'] = chat_data

        return jsonify({
            'success': True,
            'execution': execution_data
        })

    except Exception as e:
        logger.error(f"获取最新执行记录失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/executions/<filename>/download')
def download_execution_chat(filename):
    """下载任务执行的聊天记录"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        file_path = os.path.join(task_service.get_chat_save_dir(), filename)
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"下载聊天记录失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/executions/recent')
def get_recent_executions():
    """获取最近的执行记录"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        limit = request.args.get('limit', 50, type=int)

        # 获取所有执行记录
        all_executions = task_service.get_execution_history()

        # 按时间排序，最新的在前
        all_executions.sort(key=lambda x: x.start_time, reverse=True)

        # 限制数量
        recent_executions = all_executions[:limit]

        # 加载详细的聊天数据
        executions_with_data = []
        for exec in recent_executions:
            exec_data = exec.to_dict()

            # 加载对应的聊天文件
            if exec.chat_file:
                chat_path = os.path.join(task_service.get_chat_save_dir(), exec.chat_file)
                if os.path.exists(chat_path):
                    try:
                        with open(chat_path, 'r', encoding='utf-8') as f:
                            chat_data = json.load(f)
                        exec_data['chat_data'] = chat_data
                    except Exception as e:
                        logger.warning(f"加载聊天文件失败: {exec.chat_file}, {e}")

            executions_with_data.append(exec_data)

        return jsonify({
            'success': True,
            'executions': executions_with_data
        })

    except Exception as e:
        logger.error(f"获取最近执行记录失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/executions/<execution_id>/detail')
def get_execution_detail(execution_id):
    """获取执行记录的详细信息"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        # 获取所有执行记录
        executions = task_service.get_execution_history()

        # 查找对应的执行记录
        execution = None
        for exec in executions:
            if exec.id == execution_id:
                execution = exec
                break

        if not execution:
            return jsonify({'success': False, 'error': '执行记录不存在'}), 404

        execution_data = execution.to_dict()

        # 加载对应的聊天文件
        if execution.chat_file:
            chat_path = os.path.join(task_service.get_chat_save_dir(), execution.chat_file)
            if os.path.exists(chat_path):
                try:
                    with open(chat_path, 'r', encoding='utf-8') as f:
                        chat_data = json.load(f)
                    execution_data['chat_data'] = chat_data
                except Exception as e:
                    logger.warning(f"加载聊天文件失败: {execution.chat_file}, {e}")

        return jsonify({
            'success': True,
            'execution': execution_data
        })

    except Exception as e:
        logger.error(f"获取执行详情失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/executions/file/<filename>')
def get_execution_file(filename):
    """获取指定执行文件的详细信息"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        # 确保文件名安全
        filename = os.path.basename(filename)
        file_path = os.path.join(task_service.get_chat_save_dir(), filename)

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '执行文件不存在'}), 404

        # 加载执行文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            execution_data = json.load(f)

        # 构建执行记录对象
        execution_record = {
            'id': execution_data.get('execution_id', 'unknown'),
            'task_name': execution_data.get('task_name', 'unknown'),
            'start_time': execution_data.get('start_time', ''),
            'end_time': execution_data.get('end_time', ''),
            'status': execution_data.get('status', 'completed'),
            'chat_data': execution_data
        }

        return jsonify({
            'success': True,
            'execution': execution_record
        })

    except Exception as e:
        logger.error(f"获取执行文件失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@task_bp.route('/api/tasks/executions/file/<filename>/summary')
def get_execution_file_summary(filename):
    """获取指定执行文件的摘要信息"""
    task_service = current_app.config['TASK_SERVICE']
    try:
        # 确保文件名安全
        filename = os.path.basename(filename)
        file_path = os.path.join(task_service.get_chat_save_dir(), filename)

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '执行文件不存在'}), 404

        # 加载执行文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            execution_data = json.load(f)

        # 构建摘要信息
        summary = {
            'id': execution_data.get('execution_id', 'unknown'),
            'task_name': execution_data.get('task_name', 'unknown'),
            'start_time': execution_data.get('start_time', ''),
            'end_time': execution_data.get('end_time', ''),
            'status': execution_data.get('status', 'completed'),
            'duration': execution_data.get('duration', '')
        }

        return jsonify({
            'success': True,
            'execution': summary
        })

    except Exception as e:
        logger.error(f"获取执行文件摘要失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500