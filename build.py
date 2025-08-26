import os
import subprocess
import sys

def build_exe():
    """
    构建可执行文件，使用当前目录下的icon_1.ico作为图标
    无论脚本在哪个目录执行，都会使用当前工作目录下的资源
    """
    # 获取当前工作目录
    current_dir = os.getcwd()
    
    # 检查icon文件是否存在
    icon_path = os.path.join(current_dir, "icon_1.ico")
    if not os.path.exists(icon_path):
        print(f"错误: 在当前目录下找不到icon_1.ico文件: {icon_path}")
        return False
    
    # 检查main.py是否存在
    main_py_path = os.path.join(current_dir, "main.py")
    if not os.path.exists(main_py_path):
        print(f"错误: 在当前目录下找不到main.py文件: {main_py_path}")
        return False
    
    # 构建PyInstaller命令
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "SerialTool",
        f"--icon={icon_path}",
        main_py_path
    ]
    
    print("开始构建可执行文件...")
    print(f"使用图标: {icon_path}")
    print(f"打包文件: {main_py_path}")
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 执行PyInstaller命令
        subprocess.run(cmd, check=True)
        print("\n构建成功! 可执行文件位于 dist/SerialTool.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n构建失败: {e}")
        return False
    except Exception as e:
        print(f"\n发生错误: {e}")
        return False

if __name__ == "__main__":
    build_exe()
