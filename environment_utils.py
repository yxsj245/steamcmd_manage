#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import urllib.request
import shutil
import time
from typing import Optional, List, Dict, Union, Tuple, Callable

class EnvironmentUtils:
    """环境工具类，提供安装依赖、下载文件和运行安装程序等功能"""
    
    def __init__(self):
        self.current_dir = os.path.abspath(os.getcwd())
        self.tmp_dir = os.path.join(self.current_dir, "tmp")
        
        # 创建临时目录
        os.makedirs(self.tmp_dir, exist_ok=True)
    
    def download_file(self, url: str, filename: Optional[str] = None, show_progress: bool = True) -> Optional[str]:
        """
        从URL下载文件到tmp目录
        
        Args:
            url: 文件下载URL
            filename: 保存的文件名，如果为None则使用URL的最后部分
            show_progress: 是否显示下载进度
            
        Returns:
            下载文件的完整路径，如果下载失败则返回None
        """
        try:
            if filename is None:
                # 从URL中提取文件名
                filename = url.split('/')[-1]
            
            file_path = os.path.join(self.tmp_dir, filename)
            
            print(f"正在下载: {url}")
            print(f"保存到: {file_path}")
            
            # 使用进度条下载
            if show_progress:
                def report_progress(block_num, block_size, total_size):
                    read_data = block_num * block_size
                    if total_size > 0:
                        percent = read_data * 100 / total_size
                        # 显示下载进度条
                        bar_len = 20
                        filled_len = int(bar_len * read_data // total_size)
                        bar = '=' * filled_len + '-' * (bar_len - filled_len)
                        sys.stdout.write(f"\r下载进度: [{bar}] {percent:.1f}% {read_data}/{total_size} 字节")
                        sys.stdout.flush()
                
                # 开始下载
                urllib.request.urlretrieve(url, file_path, report_progress)
                print("\n下载完成!")
            else:
                urllib.request.urlretrieve(url, file_path)
                print("下载完成!")
            
            return file_path
        
        except Exception as e:
            print(f"下载失败: {e}")
            return None
    
    def run_installer(self, installer_path: str, wait_completion: bool = True, 
                     silent_args: Optional[str] = None, 
                     verification_func: Optional[Callable[[], bool]] = None) -> bool:
        """
        运行安装程序
        
        Args:
            installer_path: 安装程序路径
            wait_completion: 是否等待安装完成
            silent_args: 静默安装参数
            verification_func: 安装验证函数，用于检查安装是否成功
            
        Returns:
            安装是否成功
        """
        try:
            if not os.path.exists(installer_path):
                print(f"安装程序不存在: {installer_path}")
                return False
            
            # 构建命令
            cmd = [installer_path]
            if silent_args:
                cmd.extend(silent_args.split())
            
            print(f"正在启动安装程序: {' '.join(cmd)}")
            
            # 运行安装程序
            if wait_completion:
                subprocess.run(cmd, check=True)
                print("安装程序已结束")
            else:
                subprocess.Popen(cmd)
                print("安装程序已启动，请按照提示完成安装")
                return True  # 不等待的情况下直接返回成功
            
            # 如果提供了验证函数，执行验证
            if verification_func is not None:
                print("正在验证安装...")
                if verification_func():
                    print("安装验证成功!")
                    return True
                else:
                    print("安装验证失败!")
                    return False
                    
            return True
            
        except Exception as e:
            print(f"安装失败: {e}")
            return False
    
    def verify_python_package(self, package_name: str) -> bool:
        """
        验证Python包是否已安装
        
        Args:
            package_name: 包名
            
        Returns:
            包是否已安装
        """
        try:
            # 尝试导入包
            __import__(package_name)
            return True
        except ImportError:
            return False
    
    def install_python_package(self, package_name: str, upgrade: bool = False) -> bool:
        """
        安装Python包
        
        Args:
            package_name: 包名
            upgrade: 是否升级
            
        Returns:
            安装是否成功
        """
        try:
            cmd = [sys.executable, "-m", "pip", "install"]
            if upgrade:
                cmd.append("--upgrade")
            cmd.append(package_name)
            
            print(f"正在安装Python包: {package_name}")
            subprocess.run(cmd, check=True)
            
            # 验证安装
            if self.verify_python_package(package_name):
                print(f"Python包 {package_name} 安装成功")
                return True
            else:
                print(f"Python包 {package_name} 安装失败")
                return False
                
        except Exception as e:
            print(f"安装Python包失败: {e}")
            return False
    
    def ensure_python_package(self, package_name: str, upgrade: bool = False) -> bool:
        """
        确保Python包已安装，如果未安装则进行安装
        
        Args:
            package_name: 包名
            upgrade: 是否强制升级
            
        Returns:
            包是否已安装或安装成功
        """
        # 如果不需要升级且已安装，直接返回成功
        if not upgrade and self.verify_python_package(package_name):
            print(f"Python包 {package_name} 已安装")
            return True
        
        # 否则安装或升级
        return self.install_python_package(package_name, upgrade)
    
    def list_tmp_files(self) -> List[str]:
        """
        列出tmp目录中的所有文件
        
        Returns:
            文件列表
        """
        files = []
        try:
            for item in os.listdir(self.tmp_dir):
                item_path = os.path.join(self.tmp_dir, item)
                if os.path.isfile(item_path):
                    files.append(item)
        except Exception as e:
            print(f"列出tmp文件失败: {e}")
        
        return files
    
    def clean_tmp_files(self, confirm: bool = True) -> bool:
        """
        清理tmp目录
        
        Args:
            confirm: 是否需要确认
            
        Returns:
            清理是否成功
        """
        try:
            files = self.list_tmp_files()
            
            if not files:
                print("tmp目录为空，无需清理")
                return True
            
            print("tmp目录中的文件:")
            for i, file in enumerate(files, 1):
                file_path = os.path.join(self.tmp_dir, file)
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"{i}. {file} ({size_mb:.2f} MB)")
            
            if confirm:
                choice = input("是否删除这些文件? (y/n): ").lower()
                if choice != 'y':
                    print("取消删除")
                    return False
            
            for file in files:
                file_path = os.path.join(self.tmp_dir, file)
                os.remove(file_path)
            
            print("tmp文件清理完成")
            return True
            
        except Exception as e:
            print(f"清理tmp文件失败: {e}")
            return False
    
    def install_from_url(self, url: str, filename: Optional[str] = None, 
                        wait_completion: bool = True, silent_args: Optional[str] = None,
                        verification_func: Optional[Callable[[], bool]] = None,
                        clean_after: bool = True) -> bool:
        """
        从URL下载并安装
        
        Args:
            url: 下载URL
            filename: 保存的文件名
            wait_completion: 是否等待安装完成
            silent_args: 静默安装参数
            verification_func: 安装验证函数
            clean_after: 安装后是否清理
            
        Returns:
            安装是否成功
        """
        # 下载文件
        installer_path = self.download_file(url, filename)
        if not installer_path:
            return False
        
        # 运行安装程序
        result = self.run_installer(installer_path, wait_completion, silent_args, verification_func)
        
        # 清理临时文件
        if clean_after and wait_completion:
            print("\n安装完成，是否删除安装文件?")
            self.clean_tmp_files()
        
        return result
    
    def install_from_tmp(self, filename: str, wait_completion: bool = True, 
                        silent_args: Optional[str] = None,
                        verification_func: Optional[Callable[[], bool]] = None) -> bool:
        """
        从tmp目录安装
        
        Args:
            filename: 文件名
            wait_completion: 是否等待安装完成
            silent_args: 静默安装参数
            verification_func: 安装验证函数
            
        Returns:
            安装是否成功
        """
        installer_path = os.path.join(self.tmp_dir, filename)
        
        if not os.path.exists(installer_path):
            print(f"安装文件不存在: {installer_path}")
            
            # 显示tmp目录中的所有文件
            files = self.list_tmp_files()
            if files:
                print("\n可用的安装文件:")
                for i, file in enumerate(files, 1):
                    print(f"{i}. {file}")
                
                choice = input("\n请选择要安装的文件编号 (0表示取消): ")
                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(files):
                        filename = files[choice_num-1]
                        installer_path = os.path.join(self.tmp_dir, filename)
                    else:
                        return False
                except ValueError:
                    return False
            else:
                print("tmp目录为空，没有可用的安装文件")
                return False
        
        # 运行安装程序
        return self.run_installer(installer_path, wait_completion, silent_args, verification_func)
    
    def ensure_essential_packages(self) -> bool:
        """
        确保安装了基本的Python包
        
        Returns:
            是否所有包均已安装成功
        """
        packages = [
            "requests",
            "psutil"
        ]
        
        success_count = 0
        for package in packages:
            if self.ensure_python_package(package):
                success_count += 1
        
        print(f"\n共 {len(packages)} 个基本包，成功安装 {success_count} 个")
        return success_count == len(packages)
    
    def check_and_install_vcredist(self) -> bool:
        """
        检查并安装Visual C++ Redistributable
        
        Returns:
            是否已安装或安装成功
        """
        def verify_vcredist():
            # 这只是一个简单的验证方法，实际可能需要更复杂的检查
            system_dir = os.environ.get("SystemRoot", "C:\\Windows") + "\\System32"
            target_dll = os.path.join(system_dir, "msvcp140.dll")
            return os.path.exists(target_dll)
        
        if verify_vcredist():
            print("Visual C++ Redistributable 已安装")
            return True
        
        print("Visual C++ Redistributable 未安装，正在下载安装...")
        url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
        
        return self.install_from_url(
            url, 
            wait_completion=True,
            silent_args="/install /quiet /norestart",
            verification_func=verify_vcredist
        )

# 单例实例，方便其他模块直接导入使用
env_utils = EnvironmentUtils()

# 方便导入的函数
def ensure_package(package_name, upgrade=False):
    return env_utils.ensure_python_package(package_name, upgrade)

def download_file(url, filename=None):
    return env_utils.download_file(url, filename)

def install_from_url(url, filename=None, wait=True, silent_args=None):
    return env_utils.install_from_url(url, filename, wait, silent_args)

def install_from_tmp(filename, wait=True, silent_args=None):
    return env_utils.install_from_tmp(filename, wait, silent_args)

def clean_tmp():
    return env_utils.clean_tmp_files()

def ensure_vcredist():
    return env_utils.check_and_install_vcredist()

def ensure_basic_environment():
    """确保基本环境已安装"""
    print("正在检查基本环境...")
    packages_ok = env_utils.ensure_essential_packages()
    vcredist_ok = env_utils.check_and_install_vcredist()
    
    if packages_ok and vcredist_ok:
        print("基本环境检查完成，所有依赖已安装")
        return True
    else:
        print("基本环境检查完成，部分依赖安装失败")
        return False

# 测试函数
if __name__ == "__main__":
    print("环境工具测试")
    ensure_basic_environment()
    print("测试完成") 