# tools/chart_tools.py - 图表工具

import matplotlib.pyplot as plt
import matplotlib
import json
import os
import numpy as np
from datetime import datetime
import pandas as pd
import seaborn as sns

# 设置中文字体支持
matplotlib.use('Agg')  # 使用非交互式后端
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def mcp_tool(description: str = "", parameters: dict = None):
    """MCP工具装饰器"""
    def decorator(func):
        func._mcp_tool = {
            'description': description,
            'parameters': parameters or {}
        }
        return func
    return decorator

def get_web_server_config():
    """读取配置文件获取web服务器配置"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('web_server', {})
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        return {'host': 'localhost', 'port': 5000}

def ensure_tempfile_dir():
    """确保tempfile目录存在"""
    if not os.path.exists('tempfile'):
        os.makedirs('tempfile')

def generate_image_url(filename):
    """生成图片访问URL"""
    config = get_web_server_config()
    host = config.get('host', 'localhost')
    port = config.get('port', 5000)
    return f"http://{host}:{port}/api/files/{filename}"

@mcp_tool(
    description="绘制直方图",
    parameters={
        "data": {"type": "array", "description": "数据数组"},
        "title": {"type": "string", "description": "图表标题（可选）"},
        "xlabel": {"type": "string", "description": "X轴标签（可选）"},
        "ylabel": {"type": "string", "description": "Y轴标签（可选）"},
        "bins": {"type": "integer", "description": "分箱数量（可选，默认20）"},
        "color": {"type": "string", "description": "颜色（可选，默认蓝色）"},
        "alpha": {"type": "number", "description": "透明度（可选，默认0.7）"}
    }
)
def draw_histogram(data, title=None, xlabel=None, ylabel="频数", bins=20, color='blue', alpha=0.7):
    """绘制直方图"""
    try:
        ensure_tempfile_dir()
        
        plt.figure(figsize=(10, 6))
        plt.hist(data, bins=bins, color=color, alpha=alpha, edgecolor='black')
        
        if title:
            plt.title(title, fontsize=14, fontweight='bold')
        if xlabel:
            plt.xlabel(xlabel, fontsize=12)
        if ylabel:
            plt.ylabel(ylabel, fontsize=12)
        
        plt.grid(True, alpha=0.3)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"histogram_{timestamp}.png"
        filepath = os.path.join('tempfile', filename)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 生成访问URL
        image_url = generate_image_url(filename)
        
        return {
            "success": True,
            "message": "直方图绘制成功",
            "filename": filename,
            "filepath": os.path.abspath(filepath),
            "image_url": image_url,
            "display_format": f"![直方图]({image_url})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"绘制直方图失败: {str(e)}"
        }

@mcp_tool(
    description="绘制饼图",
    parameters={
        "data": {"type": "array", "description": "数据数组"},
        "labels": {"type": "array", "description": "标签数组"},
        "title": {"type": "string", "description": "图表标题（可选）"},
        "colors": {"type": "array", "description": "颜色数组（可选）"},
        "autopct": {"type": "string", "description": "百分比显示格式（可选，默认'%.1f%%'）"},
        "explode": {"type": "array", "description": "突出显示数组（可选）"},
        "shadow": {"type": "boolean", "description": "是否添加阴影（可选，默认False）"}
    }
)
def draw_pie_chart(data, labels, title=None, colors=None, autopct='%.1f%%', explode=None, shadow=False):
    """绘制饼图"""
    try:
        ensure_tempfile_dir()
        
        plt.figure(figsize=(10, 8))
        
        # 处理explode参数
        if explode is None:
            explode = [0] * len(data)
        
        # 处理colors参数
        if colors is None:
            colors = plt.cm.Set3(np.linspace(0, 1, len(data)))
        
        plt.pie(data, labels=labels, colors=colors, autopct=autopct, 
                explode=explode, shadow=shadow, startangle=90)
        
        if title:
            plt.title(title, fontsize=14, fontweight='bold')
        
        plt.axis('equal')
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"pie_chart_{timestamp}.png"
        filepath = os.path.join('tempfile', filename)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 生成访问URL
        image_url = generate_image_url(filename)
        
        return {
            "success": True,
            "message": "饼图绘制成功",
            "filename": filename,
            "filepath": os.path.abspath(filepath),
            "image_url": image_url,
            "display_format": f"![饼图]({image_url})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"绘制饼图失败: {str(e)}"
        }

@mcp_tool(
    description="绘制折线图",
    parameters={
        "x_data": {"type": "array", "description": "X轴数据"},
        "y_data": {"type": "array", "description": "Y轴数据"},
        "title": {"type": "string", "description": "图表标题（可选）"},
        "xlabel": {"type": "string", "description": "X轴标签（可选）"},
        "ylabel": {"type": "string", "description": "Y轴标签（可选）"},
        "color": {"type": "string", "description": "线条颜色（可选，默认蓝色）"},
        "linewidth": {"type": "number", "description": "线条宽度（可选，默认2）"},
        "marker": {"type": "string", "description": "标记样式（可选）"},
        "grid": {"type": "boolean", "description": "是否显示网格（可选，默认True）"}
    }
)
def draw_line_chart(x_data, y_data, title=None, xlabel=None, ylabel=None, 
                   color='blue', linewidth=2, marker=None, grid=True):
    """绘制折线图"""
    try:
        ensure_tempfile_dir()
        
        plt.figure(figsize=(12, 6))
        
        if marker:
            plt.plot(x_data, y_data, color=color, linewidth=linewidth, 
                    marker=marker, markersize=6)
        else:
            plt.plot(x_data, y_data, color=color, linewidth=linewidth)
        
        if title:
            plt.title(title, fontsize=14, fontweight='bold')
        if xlabel:
            plt.xlabel(xlabel, fontsize=12)
        if ylabel:
            plt.ylabel(ylabel, fontsize=12)
        
        if grid:
            plt.grid(True, alpha=0.3)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"line_chart_{timestamp}.png"
        filepath = os.path.join('tempfile', filename)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 生成访问URL
        image_url = generate_image_url(filename)
        
        return {
            "success": True,
            "message": "折线图绘制成功",
            "filename": filename,
            "filepath": os.path.abspath(filepath),
            "image_url": image_url,
            "display_format": f"![折线图]({image_url})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"绘制折线图失败: {str(e)}"
        }

@mcp_tool(
    description="绘制散点图",
    parameters={
        "x_data": {"type": "array", "description": "X轴数据"},
        "y_data": {"type": "array", "description": "Y轴数据"},
        "title": {"type": "string", "description": "图表标题（可选）"},
        "xlabel": {"type": "string", "description": "X轴标签（可选）"},
        "ylabel": {"type": "string", "description": "Y轴标签（可选）"},
        "color": {"type": "string", "description": "点颜色（可选，默认蓝色）"},
        "alpha": {"type": "number", "description": "透明度（可选，默认0.6）"},
        "s": {"type": "integer", "description": "点大小（可选，默认50）"},
        "grid": {"type": "boolean", "description": "是否显示网格（可选，默认True）"}
    }
)
def draw_scatter_plot(x_data, y_data, title=None, xlabel=None, ylabel=None,
                     color='blue', alpha=0.6, s=50, grid=True):
    """绘制散点图"""
    try:
        ensure_tempfile_dir()
        
        plt.figure(figsize=(10, 8))
        plt.scatter(x_data, y_data, color=color, alpha=alpha, s=s)
        
        if title:
            plt.title(title, fontsize=14, fontweight='bold')
        if xlabel:
            plt.xlabel(xlabel, fontsize=12)
        if ylabel:
            plt.ylabel(ylabel, fontsize=12)
        
        if grid:
            plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"scatter_plot_{timestamp}.png"
        filepath = os.path.join('tempfile', filename)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 生成访问URL
        image_url = generate_image_url(filename)
        
        return {
            "success": True,
            "message": "散点图绘制成功",
            "filename": filename,
            "filepath": os.path.abspath(filepath),
            "image_url": image_url,
            "display_format": f"![散点图]({image_url})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"绘制散点图失败: {str(e)}"
        }

@mcp_tool(
    description="绘制柱状图",
    parameters={
        "data": {"type": "array", "description": "数据数组"},
        "labels": {"type": "array", "description": "标签数组"},
        "title": {"type": "string", "description": "图表标题（可选）"},
        "xlabel": {"type": "string", "description": "X轴标签（可选）"},
        "ylabel": {"type": "string", "description": "Y轴标签（可选）"},
        "color": {"type": "string", "description": "柱状图颜色（可选，默认蓝色）"},
        "alpha": {"type": "number", "description": "透明度（可选，默认0.7）"},
        "grid": {"type": "boolean", "description": "是否显示网格（可选，默认True）"}
    }
)
def draw_bar_chart(data, labels, title=None, xlabel=None, ylabel=None,
                  color='blue', alpha=0.7, grid=True):
    """绘制柱状图"""
    try:
        ensure_tempfile_dir()
        
        plt.figure(figsize=(12, 6))
        bars = plt.bar(labels, data, color=color, alpha=alpha)
        
        if title:
            plt.title(title, fontsize=14, fontweight='bold')
        if xlabel:
            plt.xlabel(xlabel, fontsize=12)
        if ylabel:
            plt.ylabel(ylabel, fontsize=12)
        
        if grid:
            plt.grid(True, alpha=0.3, axis='y')
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # 在柱状图顶部显示数值
        for bar, value in zip(bars, data):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(data)*0.01,
                    f'{value}', ha='center', va='bottom', fontsize=10)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"bar_chart_{timestamp}.png"
        filepath = os.path.join('tempfile', filename)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 生成访问URL
        image_url = generate_image_url(filename)
        
        return {
            "success": True,
            "message": "柱状图绘制成功",
            "filename": filename,
            "filepath": os.path.abspath(filepath),
            "image_url": image_url,
            "display_format": f"![柱状图]({image_url})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"绘制柱状图失败: {str(e)}"
        }

@mcp_tool(
    description="绘制热力图",
    parameters={
        "data": {"type": "array", "description": "2D数据数组"},
        "title": {"type": "string", "description": "图表标题（可选）"},
        "xlabel": {"type": "string", "description": "X轴标签（可选）"},
        "ylabel": {"type": "string", "description": "Y轴标签（可选）"},
        "cmap": {"type": "string", "description": "颜色映射（可选，默认'viridis'）"},
        "annot": {"type": "boolean", "description": "是否显示数值（可选，默认True）"},
        "fmt": {"type": "string", "description": "数值格式（可选，默认'.2f'）"}
    }
)
def draw_heatmap(data, title=None, xlabel=None, ylabel=None, 
                cmap='viridis', annot=True, fmt='.2f'):
    """绘制热力图"""
    try:
        ensure_tempfile_dir()
        
        plt.figure(figsize=(10, 8))
        
        # 转换数据为numpy数组
        data_array = np.array(data)
        
        # 创建热力图
        sns.heatmap(data_array, annot=annot, fmt=fmt, cmap=cmap, 
                   cbar_kws={'label': '数值'})
        
        if title:
            plt.title(title, fontsize=14, fontweight='bold')
        if xlabel:
            plt.xlabel(xlabel, fontsize=12)
        if ylabel:
            plt.ylabel(ylabel, fontsize=12)
        
        plt.tight_layout()
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"heatmap_{timestamp}.png"
        filepath = os.path.join('tempfile', filename)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 生成访问URL
        image_url = generate_image_url(filename)
        
        return {
            "success": True,
            "message": "热力图绘制成功",
            "filename": filename,
            "filepath": os.path.abspath(filepath),
            "image_url": image_url,
            "display_format": f"![热力图]({image_url})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"绘制热力图失败: {str(e)}"
        }

@mcp_tool(
    description="绘制箱线图",
    parameters={
        "data": {"type": "array", "description": "数据数组（可以是多个数组）"},
        "title": {"type": "string", "description": "图表标题（可选）"},
        "xlabel": {"type": "string", "description": "X轴标签（可选）"},
        "ylabel": {"type": "string", "description": "Y轴标签（可选）"},
        "labels": {"type": "array", "description": "各组标签（可选）"},
        "grid": {"type": "boolean", "description": "是否显示网格（可选，默认True）"}
    }
)
def draw_box_plot(data, title=None, xlabel=None, ylabel=None, labels=None, grid=True):
    """绘制箱线图"""
    try:
        ensure_tempfile_dir()
        
        plt.figure(figsize=(10, 6))
        
        # 如果是嵌套数组，绘制多个箱线图
        if isinstance(data[0], (list, np.ndarray)):
            plt.boxplot(data, labels=labels)
        else:
            plt.boxplot(data)
        
        if title:
            plt.title(title, fontsize=14, fontweight='bold')
        if xlabel:
            plt.xlabel(xlabel, fontsize=12)
        if ylabel:
            plt.ylabel(ylabel, fontsize=12)
        
        if grid:
            plt.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"box_plot_{timestamp}.png"
        filepath = os.path.join('tempfile', filename)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 生成访问URL
        image_url = generate_image_url(filename)
        
        return {
            "success": True,
            "message": "箱线图绘制成功",
            "filename": filename,
            "filepath": os.path.abspath(filepath),
            "image_url": image_url,
            "display_format": f"![箱线图]({image_url})"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"绘制箱线图失败: {str(e)}"
        }