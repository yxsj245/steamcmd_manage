#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import zipfile
import urllib.request
import json
import datetime
import time
import glob
import socket
import threading
import psutil
import webbrowser
from pathlib import Path
from typing import Dict, List, Tuple, Set

# 导入环境工具模块
try:
    import environment_utils as env_utils
except ImportError:
    print("警告: 环境工具模块导入失败，环境安装功能将不可用")
    
class PortScanner:
    def __init__(self):
        self.initial_ports = set()
        self.stop_scanning = False
        self.scan_thread = None
    
    def get_listening_ports(self) -> Set[Tuple[int, str]]:
        """获取当前系统正在监听的所有端口和协议"""
        listening_ports = set()
        
        try:
            # 使用psutil获取所有网络连接
            connections = psutil.net_connections()
            
            # 筛选出正在监听的连接
            for conn in connections:
                if conn.status == 'LISTEN':
                    # 添加端口和协议 (TCP)
                    if conn.laddr.port > 0:
                        listening_ports.add((conn.laddr.port, 'tcp'))
            
            # 获取UDP端口 (需要单独处理)
            for conn in connections:
                if not conn.raddr and conn.type == socket.SOCK_DGRAM:
                    # 添加端口和协议 (UDP)
                    if conn.laddr.port > 0:
                        listening_ports.add((conn.laddr.port, 'udp'))
        
        except Exception as e:
            print(f"获取端口信息时出错: {e}")
        
        return listening_ports
    
    def start_scan(self, interval=5):
        """开始端口扫描线程"""
        print("\n正在开始端口监测...")
        print("正在获取初始端口列表...")
        
        # 获取初始端口列表
        self.initial_ports = self.get_listening_ports()
        
        # 显示初始端口信息
        print("初始端口列表:")
        if self.initial_ports:
            for port, proto in sorted(self.initial_ports):
                print(f"  端口 {port}/{proto} 已开放")
        else:
            print("  未检测到开放端口")
        
        print("\n正在监测新开放端口...")
        print("=" * 50)
        
        # 重置停止标志
        self.stop_scanning = False
        
        # 创建并启动扫描线程
        self.scan_thread = threading.Thread(target=self._scan_thread, args=(interval,))
        self.scan_thread.daemon = True
        self.scan_thread.start()
    
    def stop_scan(self):
        """停止端口扫描线程"""
        if self.scan_thread and self.scan_thread.is_alive():
            self.stop_scanning = True
            self.scan_thread.join(2)  # 等待线程结束，最多2秒
            print("\n端口监测已停止")
    
    def _scan_thread(self, interval):
        """端口扫描线程的具体实现"""
        try:
            while not self.stop_scanning:
                # 获取当前端口列表
                current_ports = self.get_listening_ports()
                
                # 获取新增端口
                new_ports = current_ports - self.initial_ports
                
                # 如果有新增端口，显示它们
                if new_ports:
                    for port, proto in sorted(new_ports):
                        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 发现新开放端口: {port}/{proto}")
                        # 将新端口添加到初始端口集合，避免重复报告
                        self.initial_ports.add((port, proto))
                
                # 等待指定间隔
                time.sleep(interval)
        
        except Exception as e:
            print(f"端口扫描线程出错: {e}")

class SteamCMDManager:
    def __init__(self):
        self.current_dir = os.path.abspath(os.getcwd())
        # 创建游戏安装目录 - 使用名为games的文件夹
        self.games_dir = os.path.join(self.current_dir, "games")
        os.makedirs(self.games_dir, exist_ok=True)
        
        self.steamcmd_dir = os.path.join(self.current_dir, "steamcmd")
        self.steamcmd_exe = os.path.join(self.steamcmd_dir, "steamcmd.exe")
        
        # 获取资源文件路径
        self.resource_dir = self._get_resource_dir()
        self.env_config_file = os.path.join(self.resource_dir, "envinstall.json")
        self.install_game_config = os.path.join(self.resource_dir, "installgame.json")
        
        # Python文件路径 - 两个位置都检查
        self.quick_deploy_script = os.path.join(self.current_dir, "quick_deploy.py")
        self.quick_deploy_resource = os.path.join(self.resource_dir, "quick_deploy.py")
        
        # config.json不随exe打包，而是在本地目录中
        self.config_file = os.path.join(self.current_dir, "config.json")
        
        # 创建端口扫描器
        self.port_scanner = PortScanner()
    
    def _get_resource_dir(self) -> str:
        """获取资源文件目录路径"""
        try:
            # 如果是打包后的程序
            if getattr(sys, 'frozen', False):
                # 获取程序所在目录
                base_path = sys._MEIPASS
            else:
                # 如果是直接运行的Python脚本
                base_path = self.current_dir
            
            return base_path
        except Exception:
            return self.current_dir
    
    def check_steamcmd_installed(self) -> bool:
        """检查steamcmd是否已安装"""
        if not os.path.exists(self.steamcmd_dir):
            return False
        
        if not os.path.exists(self.steamcmd_exe):
            return False
            
        return True
    
    def install_steamcmd(self) -> bool:
        """安装steamcmd"""
        print("正在安装SteamCMD...")
        
        # 检查当前路径是否包含非ASCII字符
        current_path = os.path.abspath(self.current_dir)
        if not all(ord(c) < 128 for c in current_path):
            print("\n错误: 当前路径包含非英文字符!")
            print(f"当前路径: {current_path}")
            print("\nSteamCMD无法在包含非英文字符的路径中运行。")
            print("请将程序移动到仅包含英文字母、数字和基本符号的路径下，例如:")
            print("C:\\SteamCMD")
            print("D:\\Games\\SteamServer")
            return False
        
        # 创建steamcmd目录
        os.makedirs(self.steamcmd_dir, exist_ok=True)
        
        try:
            # Windows安装步骤
            zip_path = os.path.join(self.current_dir, "steamcmd.zip")
            url = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
            
            print(f"正在下载SteamCMD: {url}")
            urllib.request.urlretrieve(url, zip_path)
            
            print("正在解压SteamCMD...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.steamcmd_dir)
            
            # 删除zip文件
            os.remove(zip_path)
            
            # 运行steamcmd首次更新 - 忽略可能的错误代码
            print("首次运行SteamCMD进行更新...")
            try:
                subprocess.run([self.steamcmd_exe, "+quit"], check=False)
                print("SteamCMD首次运行完成")
            except Exception as e:
                print(f"SteamCMD首次运行时出现异常: {e}，但这可能不影响使用")
            
            # 验证文件是否存在而非依赖返回代码
            if os.path.exists(self.steamcmd_exe):
                print("SteamCMD安装完成!")
                return True
            else:
                print("SteamCMD安装不完整，请检查文件")
                return False
            
        except Exception as e:
            print(f"安装SteamCMD时出错: {e}")
            return False
    
    def run_steamcmd(self) -> None:
        """直接运行steamcmd"""
        try:
            subprocess.run([self.steamcmd_exe])
            print("\nSteamCMD已退出")
            input("按回车键返回主菜单...")
        except Exception as e:
            print(f"运行SteamCMD时出错: {e}")
            input("按回车键返回主菜单...")
    
    def run_quick_deploy(self) -> None:
        """运行快速部署脚本"""
        try:
            script_path = None
            
            # 优先查找当前目录
            if os.path.exists(self.quick_deploy_script):
                script_path = self.quick_deploy_script
                print(f"找到本地脚本: {script_path}")
            # 其次查找资源目录
            elif os.path.exists(self.quick_deploy_resource):
                script_path = self.quick_deploy_resource
                print(f"找到内嵌脚本: {script_path}")
            # 如果都不存在，提示错误
            else:
                print(f"错误: 快速部署脚本不存在!")
                print(f"已检查以下路径:")
                print(f"1. {self.quick_deploy_script}")
                print(f"2. {self.quick_deploy_resource}")
                input("按回车键返回主菜单...")
                return
            
            print(f"正在启动快速部署脚本: {script_path}")
            
            # 如果是打包后的环境，使用内嵌脚本
            if getattr(sys, 'frozen', False):
                print("检测到打包环境，尝试提取脚本和资源文件...")
                # 提取脚本和配置文件到临时目录
                temp_script = self._extract_script("quick_deploy.py")
                temp_config = self._extract_script("installgame.json")
                
                if temp_script:
                    script_path = temp_script
                    print(f"已提取脚本到临时路径: {script_path}")
                else:
                    print("提取脚本失败，尝试直接使用内嵌脚本")
                
                if temp_config:
                    print(f"已提取配置文件到临时路径: {temp_config}")
                else:
                    print("提取配置文件失败")
            
            # 直接导入并运行脚本，而不是使用subprocess
            print(f"开始执行脚本: {script_path}")
            
            try:
                # 保存当前工作目录
                current_dir = os.getcwd()
                
                # 切换到脚本所在目录
                script_dir = os.path.dirname(script_path)
                os.chdir(script_dir)
                
                # 将资源目录路径添加到sys.path中，确保脚本可以导入其他模块
                if self.resource_dir not in sys.path:
                    sys.path.insert(0, self.resource_dir)
                
                # 设置环境变量，便于脚本访问资源
                os.environ['STEAMCMD_RESOURCE_DIR'] = self.resource_dir
                
                # 打包环境下，直接导入并执行模块
                script_name = os.path.basename(script_path).replace('.py', '')
                print(f"导入模块: {script_name}")
                
                import importlib.util
                spec = importlib.util.spec_from_file_location(script_name, script_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 如果模块有main函数，调用它
                if hasattr(module, 'main'):
                    print("调用主函数...")
                    module.main()
                else:
                    print("警告: 脚本中没有找到main()函数!")
                
                # 恢复工作目录
                os.chdir(current_dir)
                
            except Exception as e:
                print(f"执行脚本时出错: {e}")
                import traceback
                traceback.print_exc()
            
            print("\n快速部署脚本已退出")
            input("按回车键返回主菜单...")
        except Exception as e:
            print(f"运行快速部署脚本时出错: {e}")
            import traceback
            traceback.print_exc()
            input("按回车键返回主菜单...")
    
    def _extract_script(self, script_name):
        """将内嵌脚本提取到临时文件中"""
        try:
            import tempfile
            
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            temp_script = os.path.join(temp_dir, script_name)
            
            # 如果是打包环境，从资源目录复制
            if getattr(sys, 'frozen', False) and os.path.exists(os.path.join(self.resource_dir, script_name)):
                source_script = os.path.join(self.resource_dir, script_name)
                with open(source_script, 'rb') as src, open(temp_script, 'wb') as dst:
                    dst.write(src.read())
                return temp_script
            
            return None
        except Exception as e:
            print(f"提取脚本时出错: {e}")
            return None
    
    def install_game(self, app_id: str, username: str = "anonymous", password: str = "") -> bool:
        """使用SteamCMD安装游戏"""
        try:
            # 构建安装命令
            # 将游戏直接安装到games目录下的对应appid文件夹
            install_dir = os.path.join(self.games_dir, app_id)
            os.makedirs(install_dir, exist_ok=True)
            
            # 创建命令参数
            cmd = [
                self.steamcmd_exe,
                "+@NoPromptForPassword 1",
                f"+login {username}" + (f" {password}" if password else ""),
                f"+force_install_dir \"{install_dir}\"",
                f"+app_update {app_id} validate",
                "+quit"
            ]
            
            print(f"正在安装AppID: {app_id} 到 {install_dir}")
            print("安装命令: " + " ".join(cmd))
            subprocess.run(cmd)
            
            # 不再保存游戏信息到JSON文件
            
            print(f"游戏服务器安装完成: AppID {app_id}")
            input("按回车键返回主菜单...")
            return True
            
        except Exception as e:
            print(f"安装游戏时出错: {e}")
            input("按回车键返回主菜单...")
            return False
    
    def get_installed_games(self) -> Dict:
        """获取已安装的游戏列表"""
        # 不再从JSON文件读取，完全依赖目录扫描
        games = {}
        
        # 检查games目录，自动检测已安装的游戏
        if os.path.exists(self.games_dir):
            for item in os.listdir(self.games_dir):
                item_path = os.path.join(self.games_dir, item)
                if os.path.isdir(item_path):
                    # 尝试检测游戏名称
                    game_name = item
                    # 如果目录名是数字，可能是AppID
                    app_id = item
                    
                    # 计算文件夹大小
                    folder_size = self.get_folder_size(item_path)
                    folder_size_str = self.format_size(folder_size)
                        
                    games[app_id] = {
                        "install_dir": item_path,
                        "folder_size": folder_size_str,
                        "game_name": game_name
                    }
        
        return games
    
    def get_folder_size(self, folder_path) -> int:
        """
        计算文件夹大小
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            文件夹大小（字节）
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
        except Exception as e:
            print(f"计算文件夹大小时出错: {e}")
        return total_size
    
    def format_size(self, size_bytes) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 文件大小（字节）
            
        Returns:
            格式化后的文件大小字符串
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def find_executable_scripts(self, directory: str) -> List[Tuple[str, str]]:
        """查找目录下的所有可执行脚本文件（.bat和.exe）"""
        bat_files = glob.glob(os.path.join(directory, "**/*.bat"), recursive=True)
        exe_files = glob.glob(os.path.join(directory, "**/*.exe"), recursive=True)
        
        # 排序，将.bat文件放在前面
        scripts = [(f, "bat") for f in bat_files] + [(f, "exe") for f in exe_files]
        return scripts
    
    def run_game_script(self, app_id: str) -> None:
        """运行游戏的启动脚本"""
        games = self.get_installed_games_without_size()
        
        if app_id not in games:
            print(f"未找到AppID为{app_id}的游戏")
            input("按回车键返回...")
            return
        
        install_dir = games[app_id]["install_dir"]
        
        if not os.path.exists(install_dir):
            print(f"游戏安装目录不存在: {install_dir}")
            input("按回车键返回...")
            return
        
        # 显示正在加载的提示
        print(f"\n正在加载游戏文件信息...")
        
        # 查找可执行脚本
        scripts = self.find_executable_scripts(install_dir)
        
        if not scripts:
            print(f"在游戏目录中未找到可执行脚本: {install_dir}")
            input("按回车键返回...")
            return
        
        # 显示找到的脚本
        print(f"\n在游戏 AppID:{app_id} 中找到以下可执行脚本:")
        print("-" * 50)
        
        # 按类型排序：优先显示.bat文件
        bat_scripts = [s for s in scripts if s[1] == "bat"]
        exe_scripts = [s for s in scripts if s[1] == "exe"]
        
        # 先显示所有.bat脚本
        for i, (script, _) in enumerate(bat_scripts, 1):
            script_name = os.path.basename(script)
            script_rel_path = os.path.relpath(script, install_dir)
            print(f"{i}. [BAT] {script_name} - {script_rel_path}")
        
        # 再显示所有.exe脚本
        for i, (script, _) in enumerate(exe_scripts, len(bat_scripts) + 1):
            script_name = os.path.basename(script)
            script_rel_path = os.path.relpath(script, install_dir)
            print(f"{i}. [EXE] {script_name} - {script_rel_path}")
        
        print("-" * 50)
        
        # 用户选择脚本
        while True:
            choice = input("请选择要运行的脚本编号 (输入0返回): ")
            
            if choice == "0":
                return
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(scripts):
                    selected_script = bat_scripts[choice_num - 1][0] if choice_num <= len(bat_scripts) else exe_scripts[choice_num - len(bat_scripts) - 1][0]
                    
                    print(f"正在运行脚本: {os.path.basename(selected_script)}")
                    
                    # 询问是否开启端口监测
                    port_monitor = input("是否开启端口监测? (y/n): ").lower() == 'y'
                    
                    # 切换到脚本所在目录
                    script_dir = os.path.dirname(selected_script)
                    original_dir = os.getcwd()
                    
                    try:
                        # 如果开启端口监测，先启动监测线程
                        if port_monitor:
                            self.port_scanner.start_scan()
                        
                        # 切换到脚本目录并执行
                        os.chdir(script_dir)
                        
                        # 启动游戏进程
                        game_process = subprocess.Popen([selected_script], shell=True)
                        
                        # 如果开启了端口监测，等待用户输入停止命令
                        if port_monitor:
                            print("\n游戏已在新窗口启动，端口监测正在运行...")
                            print("按下回车键可停止端口监测并返回...")
                            input()
                            self.port_scanner.stop_scan()
                        else:
                            # 等待游戏进程完成
                            game_process.wait()
                    
                    finally:
                        # 切回原目录
                        os.chdir(original_dir)
                        
                        # 确保端口监测停止
                        if port_monitor:
                            self.port_scanner.stop_scan()
                        
                        # 检查进程是否仍在运行
                        if game_process.poll() is None:
                            print("\n检测到游戏进程仍在运行")
                            terminate = input("是否终止游戏进程? (y/n): ").lower() == 'y'
                            if terminate:
                                try:
                                    # 终止进程及其子进程
                                    parent = psutil.Process(game_process.pid)
                                    children = parent.children(recursive=True)
                                    for child in children:
                                        child.terminate()
                                    parent.terminate()
                                    print("游戏进程已终止")
                                except Exception as e:
                                    print(f"终止进程时出错: {e}")
                    
                    print(f"脚本执行结束: {os.path.basename(selected_script)}")
                    input("按回车键返回...")
                    return
                else:
                    print("无效的选择，请重试")
            except ValueError:
                print("请输入有效的数字")
    
    def show_installed_games(self) -> None:
        """显示已安装的游戏列表并允许用户选择运行游戏脚本"""
        # 首先获取游戏列表（不计算大小）
        games = self.get_installed_games_without_size()
        
        if not games:
            print("当前没有已安装的游戏服务器")
            input("按回车键返回主菜单...")
            return
        
        print("\n已安装的游戏服务器:")
        print("-" * 50)
        
        # 创建游戏列表
        game_list = []
        
        for app_id, info in games.items():
            game_list.append(app_id)
            
            # 显示游戏名称和AppID
            if app_id.isdigit():
                game_name = info.get("game_name", "未知游戏名称")
                print(f"{len(game_list)}. AppID: {app_id} - {game_name}")
            else:
                game_name = app_id
                print(f"{len(game_list)}. 游戏名称: {game_name}")
            
            print(f"   安装目录: {info['install_dir']}")
            print("-" * 50)
        
        # 用户选择游戏
        while True:
            choice = input("请选择要操作的游戏编号 (输入0返回，输入'size'查看文件夹大小): ")
            
            if choice == "0":
                return
            
            if choice.lower() == 'size':
                self._show_folder_sizes(game_list, games)
                continue
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(game_list):
                    app_id = game_list[choice_num - 1]
                    clear_screen()
                    self.run_game_script(app_id)
                    return
                else:
                    print("无效的选择，请重试")
            except ValueError:
                print("请输入有效的数字，或输入'size'查看文件夹大小")
    
    def _show_folder_sizes(self, game_list, games):
        """显示所有游戏的文件夹大小"""
        print("\n正在计算文件夹大小，请稍候...")
        
        # 计算所有游戏的文件夹大小
        sizes = {}
        for app_id in game_list:
            folder_path = games[app_id]["install_dir"]
            folder_size = self.get_folder_size(folder_path)
            folder_size_str = self.format_size(folder_size)
            sizes[app_id] = folder_size_str
        
        # 清空终端以更好地展示
        clear_screen()
        
        # 显示结果
        print("\n游戏文件夹大小:")
        print("-" * 50)
        for i, app_id in enumerate(game_list, 1):
            game_name = games[app_id].get("game_name", app_id)
            if app_id.isdigit():
                print(f"{i}. AppID: {app_id} - {game_name}")
            else:
                print(f"{i}. 游戏名称: {game_name}")
            print(f"   文件夹大小: {sizes[app_id]}")
            print("-" * 50)
        
        print("按任意键返回游戏列表...")
        self.wait_key()
        
        # 返回时再次清空终端
        clear_screen()
        
        # 重新显示游戏列表
        self.show_installed_games()
    
    def wait_key(self):
        """等待用户按下任意键"""
        if os.name == 'nt':
            import msvcrt
            msvcrt.getch()
        else:
            import termios
            import tty
            import sys
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    def get_installed_games_without_size(self) -> Dict:
        """获取已安装的游戏列表（不计算文件夹大小）"""
        games = {}
        
        # 检查games目录，自动检测已安装的游戏
        if os.path.exists(self.games_dir):
            for item in os.listdir(self.games_dir):
                item_path = os.path.join(self.games_dir, item)
                if os.path.isdir(item_path):
                    # 尝试检测游戏名称
                    game_name = item
                    # 如果目录名是数字，可能是AppID
                    app_id = item
                    
                    games[app_id] = {
                        "install_dir": item_path,
                        "game_name": game_name
                    }
        
        return games
    
    def install_environment_dependencies(self):
        """
        安装环境依赖，根据envinstall.json配置文件
        """
        # 检查环境工具模块是否可用
        if 'env_utils' not in globals() and 'env_utils' not in locals():
            print("错误: 环境工具模块不可用，无法安装环境依赖")
            input("按回车键返回...")
            return
        
        # 检查配置文件是否存在
        if not os.path.exists(self.env_config_file):
            print(f"错误: 环境配置文件 {self.env_config_file} 不存在!")
            input("按回车键返回...")
            return
        
        try:
            # 加载配置文件
            with open(self.env_config_file, 'r', encoding='utf-8') as f:
                env_configs = json.load(f)
                
            if not env_configs:
                print("错误: 环境配置文件为空!")
                input("按回车键返回...")
                return
            
            # 显示可安装的环境依赖列表
            print("\n可安装的环境依赖:")
            print("-" * 50)
            
            # 筛选出需要安装环境依赖的项目
            env_items = []
            for i, (name, config) in enumerate(env_configs.items(), 1):
                if config.get("env", False):
                    env_items.append((name, config))
                    print(f"{i}. {name}")
            
            if not env_items:
                print("没有找到需要安装的环境依赖!")
                input("按回车键返回...")
                return
                
            print("-" * 50)
            
            # 用户选择要安装的环境依赖
            while True:
                choice = input("请选择要安装的环境依赖编号 (输入0返回): ")
                
                if choice == "0":
                    return
                
                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(env_items):
                        name, config = env_items[choice_num - 1]
                        self.install_single_environment(name, config)
                        break
                    else:
                        print("无效的选择，请重试")
                except ValueError:
                    print("请输入有效的数字")
            
            input("按回车键返回...")
            
        except Exception as e:
            print(f"安装环境依赖时出错: {e}")
            input("按回车键返回...")
    
    def install_single_environment(self, name, config):
        """
        安装单个环境依赖
        
        Args:
            name: 环境依赖名称
            config: 环境依赖配置
        """
        print(f"\n准备安装环境依赖: {name}")
        
        # 特殊处理Python包
        if name == "Python环境库" and "env_packages" in config:
            packages = config.get("env_packages", [])
            if packages:
                print(f"准备安装Python包: {', '.join(packages)}")
                success_count = 0
                
                for package in packages:
                    print(f"\n正在安装 {package}...")
                    if env_utils.ensure_package(package):
                        success_count += 1
                
                print(f"\n共 {len(packages)} 个Python包，成功安装 {success_count} 个")
                return
        
        # 检查是否通过URL下载安装
        if config.get("env_URL", False):
            url = config.get("env_URL_value", "")
            if url and url.lower() != "none":
                print(f"从URL下载安装: {url}")
                
                # 下载文件但先不执行
                installer_path = env_utils.download_file(url)
                
                if installer_path:
                    # 让用户选择安装模式
                    print("\n请选择安装模式:")
                    print("1. 静默安装 (自动安装，无界面)")
                    print("2. GUI安装 (手动安装，有安装界面)")
                    
                    while True:
                        install_choice = input("请选择 [1/2]: ")
                        if install_choice in ['1', '2']:
                            break
                        print("无效的选择，请输入1或2")
                    
                    # 根据用户选择执行安装
                    if install_choice == '1':
                        # 静默安装模式
                        silent_args = config.get("env_silent_args", None)
                        print(f"正在进行静默安装...")
                        env_utils.install_from_tmp(
                            filename=os.path.basename(installer_path),
                            wait=True,
                            silent_args=silent_args
                        )
                    else:
                        # GUI安装模式
                        print(f"正在启动安装向导，请按照界面提示完成安装...")
                        env_utils.install_from_tmp(
                            filename=os.path.basename(installer_path),
                            wait=False,
                            silent_args=None
                        )
                        input("完成安装后，请按回车键继续...")
                    
                    print(f"\n{name} 环境依赖安装完成!")
                    
                    # 询问是否清理安装文件
                    clean_choice = input("\n是否删除安装文件? (y/n): ").lower()
                    if clean_choice == 'y':
                        env_utils.clean_tmp()
                    
                    return
                else:
                    print(f"下载 {name} 安装程序失败!")
        
        # 如果不通过URL下载或者URL为None，则提示用户手动安装
        read_url = config.get("env_URL_read", "")
        if read_url and read_url.lower() != "none":
            print(f"\n请手动前往以下网址下载并安装 {name}:")
            print(read_url)
            
            # 询问是否打开浏览器
            open_browser = input("是否打开浏览器访问下载页面? (y/n): ").lower() == 'y'
            if open_browser:
                try:
                    webbrowser.open(read_url)
                    print("已打开浏览器，请完成下载和安装")
                except Exception as e:
                    print(f"打开浏览器失败: {e}")
            
            input("完成安装后，请按回车键继续...")
        else:
            print(f"错误: 无法找到 {name} 的下载方式或下载地址!")

def clear_screen():
    """清除终端屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')

def show_menu():
    """显示主菜单"""
    clear_screen()
    print("\n" + "=" * 30)
    print("SteamCMD 服务器管理工具")
    print("=" * 30)
    print("1. 进入SteamCMD")
    print("2. 使用AppID安装游戏服务器")
    print("3. 查看/启动已安装的游戏服务器")
    print("4. 使用配置文件快速部署游戏")
    print("5. 安装环境依赖")
    print("0. 退出")
    print("=" * 30)
    
    choice = input("请选择操作 [0-5]: ")
    return choice

def main():
    manager = SteamCMDManager()
    
    # 检查SteamCMD是否已安装
    if not manager.check_steamcmd_installed():
        print("SteamCMD未安装，即将开始安装...")
        if not manager.install_steamcmd():
            print("SteamCMD安装失败，请手动安装后重试")
            input("按回车键退出...")
            return
        
        # 安装后暂停一下，给用户查看信息的时间
        input("SteamCMD安装已完成，按回车键继续...")
    
    # 检查是否存在psutil库，如果不存在提示安装
    try:
        import psutil
    except ImportError:
        print("缺少必要的库: psutil")
        print("请使用以下命令安装: pip install psutil")
        input("安装完成后请重新运行程序，按回车键退出...")
        return
    
    while True:
        choice = show_menu()
        
        if choice == '1':
            clear_screen()
            print("启动SteamCMD...")
            manager.run_steamcmd()
        
        elif choice == '2':
            clear_screen()
            app_id = input("请输入要安装的游戏AppID: ")
            username = input("请输入Steam账户 (留空则使用匿名登录): ")
            if username:
                password = input("请输入密码: ")
            else:
                username = "anonymous"
                password = ""
            
            manager.install_game(app_id, username, password)
        
        elif choice == '3':
            clear_screen()
            manager.show_installed_games()
        
        elif choice == '4':
            clear_screen()
            manager.run_quick_deploy()
            
        elif choice == '5':
            clear_screen()
            manager.install_environment_dependencies()
        
        elif choice == '0':
            clear_screen()
            print("感谢使用，再见!")
            time.sleep(1)
            break
        
        else:
            print("无效的选择，请重试")
            time.sleep(1)

if __name__ == "__main__":
    main() 