#!/usr/bin/env python3
"""
自适应Python启动器 - 智能检测并使用用户的Python环境
支持动态导入新包，无需重新打包exe
"""

import os
import sys
import subprocess
import json
import time
import threading
import signal
import platform
import socket
from pathlib import Path

class AdaptiveLauncher:
    def __init__(self):
        self.processes = []
        self.running = True
        self.python_executable = None
        self.project_root = None
        
    def find_python(self):
        """智能查找用户的Python环境"""
        print("正在检测Python环境...")
        
        # 1. 优先使用当前运行的Python（如果是用户环境）
        current_python = sys.executable
        if self._check_python_suitable(current_python):
            print(f"使用当前Python: {current_python}")
            return current_python
            
        # 2. 查找系统PATH中的python
        python_names = ['python', 'python3', 'py']
        if platform.system() == 'Windows':
            python_names.extend(['python.exe', 'python3.exe'])
            
        for name in python_names:
            try:
                result = subprocess.run(
                    [name, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    full_path = self._get_full_path(name)
                    if full_path and self._check_python_suitable(full_path):
                        print(f"找到系统Python: {full_path}")
                        return full_path
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
                
        # 3. 查找常见安装路径
        common_paths = []
        if platform.system() == 'Windows':
            common_paths.extend([
                r'C:\Python3*\python.exe',
                r'C:\Users\*\AppData\Local\Programs\Python\Python3*\python.exe',
                r'C:\Program Files\Python3*\python.exe'
            ])
        else:
            common_paths.extend([
                '/usr/bin/python3',
                '/usr/local/bin/python3',
                '/opt/homebrew/bin/python3'
            ])
            
        for pattern in common_paths:
            matches = self._glob_python_paths(pattern)
            for path in matches:
                if self._check_python_suitable(path):
                    print(f"找到Python: {path}")
                    return path
                    
        return None
        
    def _check_python_suitable(self, python_path):
        """检查Python是否适合使用"""
        try:
            # 检查Python版本
            result = subprocess.run(
                [python_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return False
                
            # 检查是否能运行pip
            pip_result = subprocess.run(
                [python_path, '-m', 'pip', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return pip_result.returncode == 0
            
        except Exception:
            return False
            
    def _get_full_path(self, command):
        """获取命令的完整路径"""
        try:
            result = subprocess.run(
                ['where' if platform.system() == 'Windows' else 'which', command],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0].strip()
        except Exception:
            pass
        return None
        
    def _glob_python_paths(self, pattern):
        """通配符查找Python路径"""
        import glob
        try:
            return glob.glob(pattern)
        except Exception:
            return []
            
    def setup_project_root(self):
        """设置项目根目录"""
        if getattr(sys, 'frozen', False):
            # 如果是exe运行，使用exe所在目录
            self.project_root = os.path.dirname(sys.executable)
        else:
            # 如果是脚本运行，使用脚本所在目录
            self.project_root = os.path.dirname(os.path.abspath(__file__))
            
        print(f"项目根目录: {self.project_root}")
        
    def check_dependencies(self):
        """检查并安装依赖"""
        print("检查依赖包...")
        
        requirements_file = os.path.join(self.project_root, 'requirements.txt')
        if not os.path.exists(requirements_file):
            print("⚠️  未找到requirements.txt，跳过依赖检查")
            return True
            
        try:
            # 读取requirements
            with open(requirements_file, 'r', encoding='utf-8') as f:
                requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                
            if not requirements:
                print("✅ 无依赖需要安装")
                return True
                
            # 检查每个包
            missing_packages = []
            for req in requirements:
                package_name = req.split('==')[0].split('>=')[0].split('<=')[0]
                try:
                    subprocess.run(
                        [self.python_executable, '-c', f'import {package_name}'],
                        capture_output=True,
                        timeout=5
                    )
                except subprocess.CalledProcessError:
                    missing_packages.append(req)
                    
            if missing_packages:
                print(f"📦 需要安装 {len(missing_packages)} 个包...")
                for package in missing_packages:
                    print(f"  安装 {package}...")
                    subprocess.run([
                        self.python_executable, '-m', 'pip', 'install', package
                    ], check=True)
                print("✅ 依赖安装完成")
            else:
                print("✅ 所有依赖已安装")
                
            return True
            
        except Exception as e:
            print(f"❌ 依赖检查失败: {e}")
            return False
            
    def run_script(self, script_name, args=None):
        """运行指定的Python脚本"""
        if args is None:
            args = []
            
        script_path = os.path.join(self.project_root, script_name)
        if not os.path.exists(script_path):
            print(f"❌ 找不到脚本: {script_path}")
            return None
            
        command = [self.python_executable, script_path] + args
        print(f"🚀 启动 {script_name}...")
        
        try:
            if platform.system() == 'Windows':
                # Windows: 使用cmd.exe启动独立的命令窗口
                cmd_command = ['cmd.exe', '/c', 'start', f'运行 {script_name}', 'cmd.exe', '/k'] + command
                process = subprocess.Popen(
                    cmd_command,
                    cwd=self.project_root
                )
            else:
                # Linux/macOS: 使用终端模拟器启动独立窗口
                terminal_cmd = self._get_terminal_command()
                cmd_command = terminal_cmd + ['-t', f'运行 {script_name}', '-e'] + command
                process = subprocess.Popen(
                    cmd_command,
                    cwd=self.project_root,
                    preexec_fn=os.setsid
                )
            
            self.processes.append((script_name, process))
            print(f"✅ {script_name} 已在独立窗口中启动 (PID: {process.pid})")
            return process
            
        except Exception as e:
            print(f"❌ 启动 {script_name} 失败: {e}")
            return None
            
    def _get_terminal_command(self):
        """获取适合当前系统的终端命令"""
        system = platform.system()
        if system == 'Linux':
            # 尝试各种Linux终端
            for terminal in ['gnome-terminal', 'konsole', 'xterm', 'xfce4-terminal']:
                try:
                    subprocess.run(['which', terminal], check=True, capture_output=True)
                    return [terminal]
                except subprocess.CalledProcessError:
                    continue
            return ['xterm']  # 最通用的选择
        elif system == 'Darwin':  # macOS
            return ['open', '-a', 'Terminal']
        else:
            return ['xterm']

    def get_mcp_port(self):
        """从配置文件获取MCP服务器端口"""
        try:
            config_path = os.path.join(self.project_root, 'config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('mcp_server', {}).get('port', 8888)
        except Exception:
            return 8888  # 默认端口

    def wait_for_mcp_server(self, timeout=60):
        """等待MCP服务器启动完成"""
        port = self.get_mcp_port()
        print(f"⏳ 等待MCP服务器在端口 {port} 启动...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 尝试连接到MCP服务器端口
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()

                if result == 0:
                    print(f"✅ MCP服务器已启动 (端口 {port})")
                    return True

            except Exception:
                pass

            # 显示等待进度
            elapsed = int(time.time() - start_time)
            if elapsed % 5 == 0 and elapsed > 0:
                print(f"  等待中... ({elapsed}s)")

            time.sleep(1)

        print(f"❌ 等待MCP服务器启动超时 ({timeout}s)")
        return False
            
                    
    def cleanup(self):
        """清理所有进程 - 现在为空，因为启动器立即退出"""
        pass
                
    def start_all_services(self):
        """启动所有服务"""
        print("🚀 开始启动所有服务...")

        # 启动MCP服务器
        mcp_process = self.run_script('mcp_server.py', ['server'])
        if not mcp_process:
            return False

        # 等待MCP服务器启动完成
        if not self.wait_for_mcp_server():
            print("❌ MCP服务器启动失败或超时")
            return False

        # 启动Web应用
        web_process = self.run_script('app.py')
        if not web_process:
            return False

        return True
        
    def run(self):
        """主运行函数"""
        print("🎯 MCP工具助手 - 自适应启动器")
        print("=" * 50)
        
        # 设置项目根目录
        self.setup_project_root()
        
        # 查找Python
        self.python_executable = self.find_python()
        if not self.python_executable:
            print("❌ 无法找到合适的Python环境")
            print("请确保已安装Python 3.6+ 并添加到系统PATH")
            return False
            
        print(f"🐍 Python版本: {subprocess.run([self.python_executable, '--version'], capture_output=True, text=True).stdout.strip()}")
        
        # 检查依赖
        if not self.check_dependencies():
            return False
            
        # 检查必要文件
        required_files = ['mcp_server.py', 'app.py', 'config.json']
        missing_files = [f for f in required_files if not os.path.exists(os.path.join(self.project_root, f))]
        if missing_files:
            print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
            return False
            
        # 启动服务
        if not self.start_all_services():
            return False
            
        print("\n🎉 所有服务已启动到独立窗口！")
        print("📋 服务状态:")
        for name, process in self.processes:
            print(f"  ✅ {name} - PID: {process.pid}")
            
        print("\n✅ 启动器任务完成，正在退出...")
        return True

def main():
    """主函数"""
    launcher = AdaptiveLauncher()
    
    # 运行启动器
    try:
        success = launcher.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 启动器运行失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()