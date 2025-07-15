#!/usr/bin/env python3
# start_all.py - 一键启动所有服务 (支持动态配置)
import os
import sys
import subprocess
import time
import signal
import threading
import requests
import json

class ServiceManager:
    def __init__(self):
        self.processes = []
        self.running = True
        self.config = self.load_config()

    def load_config(self):
        """加载配置文件"""
        config_file = 'config.json'
        
        if not os.path.exists(config_file):
            print(f"❌ 配置文件 {config_file} 不存在")
            sys.exit(1)
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            print(f"✅ 已加载配置文件: {config_file}")
            return config
            
        except json.JSONDecodeError as e:
            print(f"❌ 配置文件格式错误: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 读取配置文件失败: {e}")
            sys.exit(1)

    def get_mcp_config(self):
        """获取MCP服务器配置"""
        mcp_config = self.config.get('mcp_server', {})
        return {
            'host': mcp_config.get('host', 'localhost'),
            'port': mcp_config.get('port', 8888)
        }

    def get_web_config(self):
        """获取Web服务器配置"""
        web_config = self.config.get('web_server', {})
        return {
            'host': web_config.get('host', 'localhost'),
            'port': web_config.get('port', 5000),
            'debug': web_config.get('debug', False)
        }

    def start_service(self, name, command, wait_time=3):
        """启动服务"""
        print(f"🚀 启动 {name}...")
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.processes.append((name, process))
            
            # 等待服务启动
            time.sleep(wait_time)
            
            if process.poll() is None:
                print(f"✅ {name} 启动成功 (PID: {process.pid})")
                return True
            else:
                stdout, stderr = process.communicate()
                print(f"❌ {name} 启动失败")
                if stderr:
                    print(f"错误: {stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 启动 {name} 时出错: {e}")
            return False

    def check_health(self):
        """检查服务健康状态"""
        print("\n🏥 检查服务健康状态...")
        
        mcp_config = self.get_mcp_config()
        web_config = self.get_web_config()
        
        # 检查MCP服务器
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((mcp_config['host'], mcp_config['port']))
            sock.close()
            
            if result == 0:
                print(f"✅ MCP服务器 ({mcp_config['host']}:{mcp_config['port']}) - 运行中")
            else:
                print(f"❌ MCP服务器 ({mcp_config['host']}:{mcp_config['port']}) - 无法连接")
        except Exception as e:
            print(f"❌ MCP服务器检查失败: {e}")

        # 检查Web服务器
        web_url = f"http://{web_config['host']}:{web_config['port']}"
        try:
            response = requests.get(f'{web_url}/api/config', timeout=5)
            if response.status_code == 200:
                data = response.json()
                models_count = len(data.get('models', []))
                print(f"✅ Web服务器 ({web_config['host']}:{web_config['port']}) - 运行中，{models_count} 个模型")
            else:
                print(f"❌ Web服务器响应错误: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Web服务器 ({web_config['host']}:{web_config['port']}) - 无法连接")
        except Exception as e:
            print(f"❌ Web服务器检查失败: {e}")

        # 检查工具API
        try:
            response = requests.get(f'{web_url}/api/tools', timeout=5)
            if response.status_code == 200:
                data = response.json()
                tools_count = len(data.get('tools', []))
                print(f"✅ 工具API - {tools_count} 个工具可用")
            else:
                print(f"❌ 工具API响应错误: {response.status_code}")
        except Exception as e:
            print(f"❌ 工具API检查失败: {e}")

    def monitor_processes(self):
        """监控进程状态"""
        while self.running:
            time.sleep(10)  # 每10秒检查一次
            
            for name, process in self.processes:
                if process.poll() is not None:
                    print(f"\n⚠️  {name} 进程已停止 (退出码: {process.poll()})")
                    # 可以在这里添加自动重启逻辑
            
            if not self.running:
                break

    def cleanup(self):
        """清理所有进程"""
        print("\n🧹 正在停止所有服务...")
        self.running = False
        
        for name, process in self.processes:
            try:
                print(f"  停止 {name}...")
                process.terminate()
                
                # 等待进程正常结束
                try:
                    process.wait(timeout=5)
                    print(f"  ✅ {name} 已停止")
                except subprocess.TimeoutExpired:
                    print(f"  ⚠️  强制结束 {name}...")
                    process.kill()
                    process.wait()
                    print(f"  ✅ {name} 已强制停止")
                    
            except Exception as e:
                print(f"  ❌ 停止 {name} 失败: {e}")

    def print_config_info(self):
        """打印配置信息"""
        mcp_config = self.get_mcp_config()
        web_config = self.get_web_config()
        
        print("📋 当前配置:")
        print(f"  MCP服务器: {mcp_config['host']}:{mcp_config['port']}")
        print(f"  Web服务器: {web_config['host']}:{web_config['port']}")
        print(f"  调试模式: {'开启' if web_config['debug'] else '关闭'}")
        
        # 显示模型信息
        llm_config = self.config.get('llm', {})
        models = llm_config.get('models', [])
        default_model = llm_config.get('default_model', '')
        
        if models:
            print(f"  可用模型: {len(models)} 个")
            if default_model:
                print(f"  默认模型: {default_model}")

    def run(self):
        """运行服务管理器"""
        print("🚀 MCP工具助手 - 一键启动")
        print("=" * 40)
        
        # 打印配置信息
        self.print_config_info()
        print("=" * 40)
        
        # 检查必要文件
        required_files = ['mcp_server.py', 'app.py', 'config.json']
        missing_files = [f for f in required_files if not os.path.exists(f)]
        
        if missing_files:
            print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
            print("请先运行: python diagnose_and_fix.py")
            return False

        mcp_config = self.get_mcp_config()
        web_config = self.get_web_config()

        try:
            # 启动MCP服务器
            mcp_command = [sys.executable, 'mcp_server.py', 'server']
            # 如果需要传递主机和端口参数，可以在这里添加
            # mcp_command.extend(['--host', mcp_config['host'], '--port', str(mcp_config['port'])])
            
            if not self.start_service(
                f"MCP服务器 ({mcp_config['host']}:{mcp_config['port']})", 
                mcp_command,
                wait_time=3
            ):
                print("❌ MCP服务器启动失败，终止启动流程")
                return False

            # 启动Web服务器
            web_command = [sys.executable, 'app.py']
            # 如果需要传递主机和端口参数，可以在这里添加
            # web_command.extend(['--host', web_config['host'], '--port', str(web_config['port'])])
            
            if not self.start_service(
                f"Web服务器 ({web_config['host']}:{web_config['port']})",
                web_command,
                wait_time=5
            ):
                print("❌ Web服务器启动失败")
                self.cleanup()
                return False

            # 检查服务健康状态
            time.sleep(2)
            self.check_health()

            print("\n🎉 所有服务启动成功！")
            
            # 根据配置显示访问地址
            web_url = f"http://{web_config['host']}:{web_config['port']}"
            print(f"🌐 请访问: {web_url}")
            
            if web_config['host'] != 'localhost' and web_config['host'] != '127.0.0.1':
                print(f"🌍 外部访问: {web_url}")
                
            print("📝 实时日志监控已启动...")
            print("\n按 Ctrl+C 停止所有服务")

            # 启动进程监控
            monitor_thread = threading.Thread(target=self.monitor_processes)
            monitor_thread.daemon = True
            monitor_thread.start()

            # 主循环 - 等待用户中断
            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n收到停止信号...")
        except Exception as e:
            print(f"\n❌ 运行出错: {e}")
        finally:
            self.cleanup()

        return True

def main():
    manager = ServiceManager()
    
    # 设置信号处理
    def signal_handler(sig, frame):
        manager.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # 检查是否需要先运行诊断
    if len(sys.argv) > 1 and sys.argv[1] == '--diagnose':
        print("运行诊断...")
        os.system(f"{sys.executable} diagnose_and_fix.py")
        return
    
    # 快速检查
    if not all(os.path.exists(f) for f in ['mcp_server.py', 'app.py']):
        print("❌ 检测到缺少关键文件")
        print("请先运行诊断: python start_all.py --diagnose")
        return
    
    # 启动所有服务
    success = manager.run()
    
    if success:
        print("\n👋 所有服务已停止，再见！")
    else:
        print("\n❌ 启动失败，请检查错误信息")

if __name__ == '__main__':
    main()