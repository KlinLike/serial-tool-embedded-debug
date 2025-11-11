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

### 方法一：使用 Conda 环境（推荐）

1.  **克隆或下载项目**
    ```bash
    git clone <项目地址>
    cd serial-tool-embedded-debug
    ```

2.  **创建 Conda 环境**
    打开 Anaconda Prompt (或终端)，进入项目根目录，执行以下命令创建独立环境：

    ```bash
    conda create --name serial python=3.12 -y
    ```

3.  **激活环境**
    ```bash
    conda activate serial
    ```

4.  **安装依赖库**
    在已激活的环境中，安装所有必需的第三方库：

    ```bash
    pip install pyqt6 pyserial pyinstaller
    ```

### 方法二：使用 requirements.txt

如果项目包含 `requirements.txt` 文件，可以直接安装：

```bash
conda activate serial
pip install -r requirements.txt
```

### 依赖说明

- **PyQt6** (6.7.1+): GUI 框架
- **pyserial** (3.5+): 串口通信库
- **pyinstaller** (6.12.0+): 打包工具（仅打包时需要）

## 🚀 如何运行

### 开发环境运行

确保您已经完成了环境配置并且处在已激活的 `serial` 环境下。

```bash
# 激活环境
conda activate serial

# 运行程序
python main.py
```

### 直接运行（已打包版本）

如果您已经有打包好的 `SerialTool.exe`，可以直接双击运行，无需安装 Python 环境。

## 📦 打包为 EXE 可执行文件

如果您希望将此程序分享给没有安装Python环境的Windows用户，可以将其打包成一个独立的 `.exe` 文件。

### 使用构建脚本（推荐）

项目提供了 `build.py` 脚本来简化打包流程：

```bash
# 确保在 serial 环境中
conda activate serial

# 运行构建脚本
python build.py
```

构建脚本会自动：
- 检查 `icon_1.ico` 图标文件是否存在
- 使用 PyInstaller 打包程序
- 生成单文件可执行程序

**打包成功后**，可执行文件位于：`dist/SerialTool.exe`

### 手动打包

如果需要自定义打包参数，也可以手动执行：

```bash
pyinstaller --onefile --windowed --name SerialTool --icon=icon_1.ico main.py
```

**命令参数说明:**
- `--onefile`: 打包成单个 `.exe` 文件
- `--windowed`: GUI 模式，不显示控制台窗口
- `--name SerialTool`: 指定程序名称
- `--icon=icon_1.ico`: 指定程序图标

### 注意事项

- 确保项目根目录下有 `icon_1.ico` 图标文件
- 打包过程会创建 `build` 和 `dist` 文件夹
- 最终的可执行文件在 `dist/SerialTool.exe`
- 打包后的 exe 文件可以独立运行，无需 Python 环境

## 💻 主要技术

- **Python 3**: 核心开发语言
- **PyQt6**: 图形用户界面 (GUI) 框架
- **PySerial**: 串口通信库
- **PyInstaller**: Python程序打包工具