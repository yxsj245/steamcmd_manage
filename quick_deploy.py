#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import subprocess
import shutil
import datetime
import time
import requests

# 调试模式开关
DEBUG_MODE = False  # 设置为True开启调试模式

class GameDeployer:
    def __init__(self):
        self.current_dir = os.path.abspath(os.getcwd())
        self.games_dir = os.path.join(self.current_dir, "games")
        self.steamcmd_dir = os.path.join(self.current_dir, "steamcmd")
        self.steamcmd_exe = os.path.join(self.steamcmd_dir, "steamcmd.exe")
        self.config_file = os.path.join(self.current_dir, "installgame.json")
        self.mcsm_config_file = os.path.join(self.current_dir, "config.json")
        self.installed_games_file = os.path.join(self.current_dir, "installed_games.json")
        
        # MCSManager默认配置
        self.mcsm_panel_url = "http://192.168.10.43:23333"
        self.mcsm_api_key = "58230ba934ea45af8eab636199f0faac"
        self.mcsm_daemon_uuid = "f334ce6aa88241c29b6edb2bfbf4df74"
        self.mcsm_host_path = "/dockerwork/game_data"
        
        # 加载MCSManager配置
        self.load_mcsm_config()
        
        # 确保games目录存在
        os.makedirs(self.games_dir, exist_ok=True)
    
    def load_mcsm_config(self):
        """加载MCSManager配置"""
        try:
            if os.path.exists(self.mcsm_config_file):
                with open(self.mcsm_config_file, 'r', encoding='utf-8') as f:
                    mcsm_config = json.load(f)
                
                if "MCSM" in mcsm_config:
                    mcsm = mcsm_config["MCSM"]
                    self.mcsm_panel_url = mcsm.get("PANEL_URL", self.mcsm_panel_url)
                    self.mcsm_api_key = mcsm.get("API_KEY", self.mcsm_api_key)
                    self.mcsm_daemon_uuid = mcsm.get("DAEMON_UUID", self.mcsm_daemon_uuid)
                    self.mcsm_host_path = mcsm.get("HOST_PATH", self.mcsm_host_path)
                    
                    print(f"已加载MCSManager配置:")
                    print(f"面板地址: {self.mcsm_panel_url}")
                    print(f"API密钥: {self.mcsm_api_key}")
                    print(f"守护进程UUID: {self.mcsm_daemon_uuid}")
        except Exception as e:
            print(f"加载MCSManager配置出错: {e}")
    
    def load_config(self):
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_file):
                print(f"错误: 配置文件 {self.config_file} 不存在!")
                return None
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                all_configs = json.load(f)
            
            if not isinstance(all_configs, dict) or len(all_configs) == 0:
                print(f"错误: 配置文件格式不正确或为空!")
                return None
            
            # 返回所有游戏配置
            return all_configs
            
        except json.JSONDecodeError as e:
            print(f"错误: 配置文件格式不正确: {e}")
            return None
        except Exception as e:
            print(f"加载配置文件时出错: {e}")
            return None
    
    def validate_game_config(self, game_key, config):
        """验证单个游戏配置是否有效"""
        # 检查必要字段
        if "appid" not in config or not config["appid"]:
            print(f"错误: 游戏 '{game_key}' 配置中缺少有效的appid字段!")
            return False
        
        # 检查游戏名称字段
        if "game_nameCN" not in config and "game_nameEN" not in config:
            print(f"错误: 游戏 '{game_key}' 配置中必须至少包含一个游戏名称字段 (game_nameCN 或 game_nameEN)!")
            return False
        
        return True
    
    def check_steamcmd_installed(self):
        """检查SteamCMD是否已安装"""
        if not os.path.exists(self.steamcmd_dir) or not os.path.exists(self.steamcmd_exe):
            print("SteamCMD未安装，请先运行steamcmd_manager.py安装SteamCMD")
            return False
        return True
    
    def install_game(self, game_key, config):
        """根据配置安装游戏"""
        app_id = config["appid"]
        game_name_cn = config.get("game_nameCN", "")
        game_name_en = config.get("game_nameEN", game_key)
        anonymous = config.get("anonymous", True)
        create_mcsm = config.get("create_mcsm", False)  # 是否创建MCSM实例
        
        # 显示游戏名称
        display_name = game_name_cn if game_name_cn else game_name_en
        print(f"\n开始安装游戏: {display_name} (AppID: {app_id})")
        
        # 构建安装目录 - 使用英文名或键名作为文件夹名
        folder_name = game_key.replace(" ", "_")
        install_dir = os.path.join(self.games_dir, folder_name)
        os.makedirs(install_dir, exist_ok=True)
        
        # 构建SteamCMD命令
        cmd = [
            self.steamcmd_exe,
            "+@NoPromptForPassword 1"
        ]
        
        # 登录信息
        if anonymous:
            cmd.append("+login anonymous")
            print("使用匿名账户登录Steam")
        else:
            username = input("请输入Steam账户: ")
            password = input("请输入密码: ")
            cmd.append(f"+login {username} {password}")
        
        # 添加安装命令
        cmd.extend([
            f'+force_install_dir "{install_dir}"',
            f"+app_update {app_id} validate",
            "+quit"
        ])
        
        # 执行安装命令
        print(f"执行安装命令: {' '.join(cmd)}")
        subprocess.run(cmd)
        
        # 保存安装信息
        self.save_game_info(app_id, game_key, game_name_cn, game_name_en, install_dir)
        
        # 如果需要创建启动脚本
        script_created = False
        if config.get("script", False):
            # 直接使用script_name的内容，无论是什么值
            if "script_name" in config:
                script_content = config["script_name"]
                self.create_launch_script(app_id, display_name, install_dir, script_content)
                script_created = True
            else:
                # 如果script为true但没有提供script_name，创建一个默认的启动脚本
                self.create_default_launch_script(app_id, display_name, install_dir)
                script_created = True
        
        # 显示提示信息
        if "tip" in config and config["tip"]:
            print("\n" + "=" * 50)
            print("游戏安装完成! 以下是游戏信息:")
            print(config["tip"])
            print("=" * 50)
        
        print(f"\n游戏 {display_name} (AppID: {app_id}) 安装完成!")
        
        if script_created:
            print("启动脚本已创建，您可以使用它来启动游戏服务器。")
        
        # 如果配置了需要创建MCSM实例，就创建
        if create_mcsm:
            create_confirm = input("\n是否创建MCSManager实例? (y/n): ").lower()
            if create_confirm == 'y':
                # 获取启动命令
                mcsm_start_cmd = config.get("mcsm_start_cmd", "")
                
                print(f"\n正在为游戏创建MCSM实例...")
                instance_uuid = self.create_mcsm_instance(
                    game_key, 
                    folder_name, 
                    display_name,
                    mcsm_start_cmd
                )
                
                if instance_uuid:
                    print(f"MCSM实例创建成功，实例UUID: {instance_uuid}")
                else:
                    print(f"MCSM实例创建失败")
        
        return True
    
    def save_game_info(self, app_id, game_key, game_name_cn, game_name_en, install_dir):
        """保存游戏安装信息"""
        try:
            games = {}
            if os.path.exists(self.installed_games_file):
                with open(self.installed_games_file, 'r', encoding='utf-8') as f:
                    games = json.load(f)
            
            # 添加或更新游戏信息
            games[app_id] = {
                "key": game_key,
                "name": game_name_cn if game_name_cn else game_name_en,
                "name_cn": game_name_cn,
                "name_en": game_name_en,
                "install_dir": install_dir,
                "installed_date": str(datetime.datetime.now())
            }
            
            # 保存到文件
            with open(self.installed_games_file, 'w', encoding='utf-8') as f:
                json.dump(games, f, ensure_ascii=False, indent=2)
                
            print(f"游戏信息已保存到 {self.installed_games_file}")
        except Exception as e:
            print(f"保存游戏信息时出错: {e}")
    
    def create_launch_script(self, app_id, game_name, install_dir, script_content):
        """创建游戏启动脚本"""
        try:
            # 为游戏创建启动脚本
            script_file = os.path.join(install_dir, f"start_{app_id}.bat")
            
            # 使用UTF-8编码保存批处理文件，并添加代码页设置命令
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write("@echo off\n")
                f.write("chcp 65001 >nul\n")  # 设置命令行为UTF-8编码
                f.write("cd /d \"%~dp0\"\n")  # 切换到脚本所在目录
                f.write(f"echo 正在启动 {game_name} 服务器...\n")
                f.write(f"{script_content}\n")
                f.write("pause\n")
            
            print(f"已创建启动脚本: {script_file}")
            return script_file
        except Exception as e:
            print(f"创建启动脚本时出错: {e}")
            return None
    
    def create_default_launch_script(self, app_id, game_name, install_dir):
        """创建默认的启动脚本"""
        try:
            # 寻找可能的服务器可执行文件
            server_exes = []
            for root, dirs, files in os.walk(install_dir):
                for file in files:
                    lower_file = file.lower()
                    if lower_file.endswith('.exe') and any(keyword in lower_file for keyword in ['server', 'dedicated', 'service']):
                        server_exes.append(os.path.join(root, file))
            
            # 创建启动脚本
            script_file = os.path.join(install_dir, f"start_{app_id}.bat")
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write("@echo off\n")
                f.write("chcp 65001 >nul\n")  # 设置命令行为UTF-8编码
                f.write("cd /d \"%~dp0\"\n")  # 切换到脚本所在目录
                f.write(f"echo 正在启动 {game_name} 服务器...\n\n")
                
                if server_exes:
                    # 如果找到服务器可执行文件，添加到脚本中
                    for i, exe in enumerate(server_exes):
                        rel_path = os.path.relpath(exe, install_dir)
                        f.write(f"echo {i+1}. 可用启动方式: {rel_path}\n")
                    
                    f.write("\necho 请手动启动适合的服务器程序\n")
                else:
                    # 如果没有找到服务器可执行文件
                    f.write("echo 未找到可能的服务器可执行文件\n")
                    f.write("echo 请在此目录中找到合适的服务器程序启动\n")
                
                f.write("pause\n")
            
            print(f"已创建默认启动脚本: {script_file}")
            return script_file
        
        except Exception as e:
            print(f"创建默认启动脚本时出错: {e}")
            return None
    
    def create_mcsm_instance(self, game_key, folder_name, display_name, start_command=""):
        """创建MCSM实例（非Docker版）"""
        try:
            # 游戏路径
            game_path = os.path.join(self.games_dir, folder_name)
            
            # 构建请求数据 - 使用直接进程模式
            request_data = {
                "nickname": display_name,
                "startCommand": start_command,
                "stopCommand": "^C",
                "cwd": game_path,  # 使用本地游戏路径
                "ie": "utf8",
                "oe": "utf8",
                "type": "steam/universal",
                "tag": [],
                "endTime": 0,
                "fileCode": "utf8",
                "processType": "general",  # 直接进程模式
                "updateCommand": "",
                "actionCommandList": [],
                "crlf": 2
            }
            
            # 构建API URL - 注意这里的参数名可能是大小写敏感的
            api_url = f"{self.mcsm_panel_url}/api/instance"
            
            # MCSM API参数，尝试不同的大小写组合
            params = {
                "apikey": self.mcsm_api_key,
                "daemonId": self.mcsm_daemon_uuid
            }
            
            # 打印请求信息以便调试
            print("\n====== 请求信息 ======")
            print(f"API URL: {api_url}")
            print(f"请求参数: {params}")
            print(f"请求数据: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
            print("=====================\n")
            
            # 发送请求
            response = requests.post(
                api_url, 
                params=params,
                headers={
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json; charset=utf-8',
                    'Accept': '*/*'
                },
                json=request_data
            )
            
            # 如果第一次请求失败，尝试第二种参数形式
            if response.status_code != 200:
                print("首次请求失败，尝试使用不同的参数名...")
                params = {
                    "apiKey": self.mcsm_api_key,  # 使用大写K
                    "daemonId": self.mcsm_daemon_uuid
                }
                
                print(f"新的请求参数: {params}")
                
                response = requests.post(
                    api_url, 
                    params=params,
                    headers={
                        'X-Requested-With': 'XMLHttpRequest',
                        'Content-Type': 'application/json; charset=utf-8',
                        'Accept': '*/*'
                    },
                    json=request_data
                )
            
            # 解析响应
            data = response.json()
            
            # 打印响应信息
            print("\n====== 响应信息 ======")
            print(f"状态码: {response.status_code}")
            print(f"响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
            print("=====================\n")
            
            if data.get("status") == 200:
                instance_uuid = data.get("data", {}).get("instanceUuid")
                return instance_uuid
            else:
                print(f"创建MCSM实例失败: {data.get('data')}")
                return None
                
        except Exception as e:
            print(f"创建MCSM实例出错: {e}")
            return None

def clear_screen():
    """清除终端屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    clear_screen()
    print("=" * 50)
    print("SteamCMD 游戏快速部署工具")
    print("=" * 50)
    print("该工具将根据installgame.json配置文件安装游戏服务器")
    if DEBUG_MODE:
        print("⚠️ 调试模式已开启，将跳过游戏安装过程")
    print("=" * 50)
    
    deployer = GameDeployer()
    
    # 检查SteamCMD
    if not deployer.check_steamcmd_installed() and not DEBUG_MODE:
        input("按回车键退出...")
        return
    
    # 加载配置
    all_configs = deployer.load_config()
    if not all_configs:
        input("配置加载失败，按回车键退出...")
        return
    
    # 显示游戏列表
    print("\n可安装的游戏列表:")
    print("-" * 50)
    
    valid_games = []
    for i, (game_key, config) in enumerate(all_configs.items(), 1):
        if deployer.validate_game_config(game_key, config):
            valid_games.append((game_key, config))
            game_name_cn = config.get("game_nameCN", "")
            game_name_en = config.get("game_nameEN", game_key)
            display_name = f"{game_name_cn} / {game_name_en}" if game_name_cn and game_name_en else (game_name_cn or game_name_en)
            create_mcsm = "是" if config.get("create_mcsm", False) else "否"
            print(f"{i}. {display_name} (AppID: {config.get('appid', 'N/A')}, 创建MCSM实例: {create_mcsm})")
    
    print("-" * 50)
    
    if not valid_games:
        print("没有有效的游戏配置!")
        input("按回车键退出...")
        return
    
    # 用户选择游戏
    while True:
        choice = input("请选择要安装的游戏编号 (输入0退出): ")
        
        if choice == "0":
            print("安装已取消")
            return
        
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(valid_games):
                selected_game = valid_games[choice_num - 1]
                break
            else:
                print("无效的选择，请重试")
        except ValueError:
            print("请输入有效的数字")
    
    # 获取选择的游戏配置
    game_key, config = selected_game
    game_name_cn = config.get("game_nameCN", "")
    game_name_en = config.get("game_nameEN", game_key)
    display_name = f"{game_name_cn} / {game_name_en}" if game_name_cn and game_name_en else (game_name_cn or game_name_en)
    
    # 显示配置信息
    print("\n即将安装以下游戏:")
    print(f"游戏名称: {display_name}")
    print(f"AppID: {config['appid']}")
    
    if not DEBUG_MODE:
        print(f"登录方式: {'匿名账户' if config.get('anonymous', True) else '需要Steam账户'}")
        
        if config.get("script", False):
            if "script_name" in config:
                print(f"将创建启动脚本，内容: {config['script_name']}")
            else:
                print("将创建默认启动脚本")
    
    if config.get("create_mcsm", False):
        print("安装完成后可选择创建MCSM实例")
        if "mcsm_start_cmd" in config:
            print(f"  启动命令: {config['mcsm_start_cmd']}")
    
    # 确认继续
    if DEBUG_MODE:
        confirm = input("\n是否继续? (y/n): ")
    else:
        confirm = input("\n是否开始安装? (y/n): ")
        
    if confirm.lower() != 'y':
        print("操作已取消")
        return
    
    # 调试模式下：跳过游戏安装，直接创建MCSM实例
    if DEBUG_MODE:
        folder_name = game_key.replace(" ", "_")
        install_dir = os.path.join(deployer.games_dir, folder_name)
        
        # 确保目录存在
        os.makedirs(install_dir, exist_ok=True)
        
        # 创建启动脚本
        script_created = False
        if config.get("script", False):
            # 直接使用script_name的内容，无论是什么值
            if "script_name" in config:
                script_content = config["script_name"]
                deployer.create_launch_script(config['appid'], display_name, install_dir, script_content)
                script_created = True
                print(f"已创建启动脚本")
            else:
                # 如果script为true但没有提供script_name，创建一个默认的启动脚本
                deployer.create_default_launch_script(config['appid'], display_name, install_dir)
                script_created = True
                print(f"已创建默认启动脚本")
        
        # 直接询问是否创建MCSM实例
        create_confirm = input("\n是否创建MCSManager实例? (y/n): ").lower()
        if create_confirm == 'y':
            # 获取启动命令
            mcsm_start_cmd = config.get("mcsm_start_cmd", "")
            
            print(f"\n正在为游戏创建MCSM实例...")
            instance_uuid = deployer.create_mcsm_instance(
                game_key, 
                folder_name, 
                display_name,
                mcsm_start_cmd
            )
            
            if instance_uuid:
                print(f"MCSM实例创建成功，实例UUID: {instance_uuid}")
            else:
                print(f"MCSM实例创建失败")
    else:
        # 正常模式：安装游戏
        if deployer.install_game(game_key, config):
            print("\n安装完成!")
        else:
            print("\n安装失败!")
    
    input("按回车键退出...")

if __name__ == "__main__":
    main() 