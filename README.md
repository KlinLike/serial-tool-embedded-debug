# PyQt 串口助手 (PyQt Serial Tool)

这是一个使用 Python 和 PyQt6 开发的简易桌面串口调试助手。它提供了一个简洁的用户界面，用于与串口设备进行通信，支持自动刷新、自定义波特率、数据筛选和保存等功能。

## ✨ 主要功能

- **串口自动/手动刷新**: 自动检测串口设备的插入和拔出，并提供手动刷新按钮。
- **自定义波特率**: 支持标准及高速波特率（如 1,000,000, 2,000,000）。
- **实时数据显示**: 在文本框中实时显示从串口接收到的数据。
- **关键字筛选**: 只显示包含特定关键字的数据行。
- **数据管理**: 可以一键清空接收区的数据，或将所有数据显示存为 `.txt` 文件。
- **健壮的异步设计**: 后台线程负责串口读取，保证了UI界面的流畅不卡顿。

## 🛠️ 环境配置

本项目推荐使用 [Anaconda](https://www.anaconda.com/products/distribution) 来管理Python环境和依赖。

1.  **克隆或下载项目**
    将本项目所有文件下载到您的本地文件夹。

2.  **创建 Conda 环境**
    打开 Anaconda Prompt (或终端)，进入项目根目录，然后执行以下命令来创建一个独立的环境。

    ```bash
    conda create --name serial_env python=3.9 -y
    ```

3.  **激活环境**
    ```bash
    conda activate serial_env
    ```

4.  **安装依赖库**
    在已激活的环境中，执行以下命令来安装所有必需的第三方库。

    ```bash
    pip install pyqt6 pyserial
    ```

    *(最佳实践: 您也可以在项目根目录执行 `pip freeze > requirements.txt` 来生成一个依赖文件，之后其他人只需 `pip install -r requirements.txt` 即可安装所有依赖。)*

## 🚀 如何运行

确保您已经完成了环境配置并且处在已激活的 `serial_env` 环境下。

1.  进入项目根目录。
2.  执行以下命令来启动程序：

    ```bash
    python main.py
    ```

## 📦 打包为 EXE 可执行文件

如果您希望将此程序分享给没有安装Python环境的Windows用户，可以将其打包成一个独立的 `.exe` 文件。

1.  **安装 PyInstaller**
    首先，确保您的 `serial_env` 环境已激活，然后安装打包工具 PyInstaller。

    ```bash
    pip install pyinstaller
    ```

2.  **执行打包命令**
    在项目根目录下，执行以下命令。建议您提前准备一个 `.ico` 格式的图标文件以获得更好的效果。

    ```bash
    pyinstaller --onefile --windowed --name SerialTool --icon=path/to/your/icon.ico main.py
    ```

    **命令参数解释:**
    - `--onefile`: 将所有依赖打包成一个单独的 `.exe` 文件。
    - `--windowed`: 运行程序时不显示黑色的命令行窗口（GUI程序必备）。
    - `--name SerialTool`: 指定生成的程序名称为 `SerialTool.exe`。
    - `--icon=path/to/your/icon.ico`: 为您的程序指定一个图标文件（可选）。

3.  **获取成果**
    打包成功后，在项目根目录下会生成一个 `dist` 文件夹。您需要的 `SerialTool.exe` 文件就在里面。您可以将这个文件单独发送给他人使用。

## 💻 主要技术

- **Python 3**: 核心开发语言
- **PyQt6**: 图形用户界面 (GUI) 框架
- **PySerial**: 串口通信库
- **PyInstaller**: Python程序打包工具