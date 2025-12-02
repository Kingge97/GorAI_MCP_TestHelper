from flask import Blueprint, request, jsonify, send_file
from flask import current_app
import os
from datetime import datetime
import logging

file_bp = Blueprint('file', __name__)
logger = logging.getLogger(__name__)

@file_bp.route('/api/files/<filename>')
def serve_file(filename):
    """Serve files from tempfile directory"""
    try:
        # 确保文件名安全
        filename = os.path.basename(filename)
        file_path = os.path.join('tempfile', filename)

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        # 检查是否是下载请求
        download = request.args.get('download', '').lower() == 'true'

        if download:
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return send_file(file_path)

    except Exception as e:
        logger.error(f"文件服务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@file_bp.route('/api/files')
def list_files():
    """List all files in tempfile directory"""
    try:
        temp_dir = 'tempfile'
        if not os.path.exists(temp_dir):
            return jsonify({'success': True, 'files': []})

        files = []
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                file_ext = os.path.splitext(filename)[1].lower()
                is_image = file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']

                files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'extension': file_ext,
                    'is_image': is_image,
                    'url': f'/api/files/{filename}'
                })

        # 按修改时间排序，最新的在前
        files.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify({'success': True, 'files': files})

    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@file_bp.route('/api/files/markdown')
def generate_files_markdown():
    """Generate markdown content for all files"""
    try:
        temp_dir = 'tempfile'
        if not os.path.exists(temp_dir):
            return jsonify({'success': True, 'markdown': '暂无文件'})

        files = []
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                file_ext = os.path.splitext(filename)[1].lower()
                is_image = file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']

                files.append({
                    'filename': filename,
                    'extension': file_ext,
                    'is_image': is_image,
                    'url': f'/api/files/{filename}'
                })

        if not files:
            return jsonify({'success': True, 'markdown': '暂无文件'})

        markdown_content = "## 📁 生成的文件\n\n"

        for file_info in files:
            filename = file_info['filename']
            url = file_info['url']
            is_image = file_info['is_image']

            if is_image:
                markdown_content += f"""
### 🖼️ {filename}

<div style="text-align: center; margin: 16px 0;">
    <img src="{url}" alt="{filename}" style="max-width: 400px; max-height: 400px; width: auto; height: auto; border-radius: 8px; margin: 0 auto; display: block;">
    <div style="margin-top: 12px; display: flex; justify-content: center; gap: 8px;">
        <a href="{url}" target="_blank" style="display: inline-block; padding: 6px 12px; background: #007AFF; color: white; border-radius: 6px; text-decoration: none; font-size: 12px;">查看详情</a>
        <a href="{url}?download=true" download style="display: inline-block; padding: 6px 12px; background: #34C759; color: white; border-radius: 6px; text-decoration: none; font-size: 12px;">下载</a>
    </div>
</div>

---
"""
            else:
                markdown_content += f"""
### 📄 {filename}

- **文件名**: {filename}
- **下载**: [点击下载]({url}?download=true)

---
"""

        return jsonify({'success': True, 'markdown': markdown_content})

    except Exception as e:
        logger.error(f"生成markdown失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500