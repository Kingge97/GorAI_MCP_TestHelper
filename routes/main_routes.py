from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """主页"""
    # 注意：这里需要从 app 实例获取 config，会在注册时传入
    return render_template('index.html', config=main_bp.config)

@main_bp.route('/favicon.ico')
def favicon():
    """返回空的favicon以避免404错误"""
    return '', 204

@main_bp.route('/tasks')
def tasks_page():
    """任务管理页面"""
    return render_template('tasks.html')