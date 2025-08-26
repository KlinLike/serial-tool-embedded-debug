import sys
import json
import logging
import logging.handlers
import serial
import serial.tools.list_ports
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QComboBox, QTextBrowser, 
    QLabel, QLineEdit, QMessageBox, QFileDialog
)
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QDateTime, QTimer, QUrl
from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem, QColor, QDesktopServices

# setup_logging 函数接收 settings 字典
def setup_logging(settings):
    """配置日志系统，使用带时间戳的日志名，并根据配置清理旧日志"""
    try:
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).parent
            
        log_dir = base_path / "serialLog"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 从配置中获取保留天数，如果获取失败则默认为3天
        retention_days = settings.get("log_retention_days", 3)
        cutoff = datetime.now() - timedelta(days=retention_days)

        for log_file in log_dir.glob('serial_tool_*.log'):
            try:
                timestamp_str = log_file.stem.replace('serial_tool_', '')
                log_time = datetime.strptime(timestamp_str, '%Y-%m-%d_%H-%M')
                if log_time < cutoff:
                    log_file.unlink()
                    print(f"已删除超过 {retention_days} 天的旧日志: {log_file.name}")
            except (ValueError, IndexError):
                print(f"无法解析日志文件名: {log_file.name}")
                continue
        
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        log_filename = f"serial_tool_{timestamp}.log"
        log_file_path = log_dir / log_filename
        print(f"日志文件将被保存在: {log_file_path}")
        
        log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        if root_logger.hasHandlers():
            root_logger.handlers.clear()
            
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
        
        return logging.getLogger("SerialApp"), log_file_path
    except Exception as e:
        print(f"日志系统初始化失败: {e}")
        return logging.getLogger("SerialApp"), None

class SettingsManager:
    def __init__(self, filename='config.json'):
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).parent
            
        self.filename = base_path / filename
        
        # 【修改点1】新增 log_retention_days 默认配置
        self.defaults = { 
            "font_size": 12, 
            "default_baud_rate": "1000000", 
            "available_baud_rates": [
                "9600", "19200", "38400", "57600", 
                "115200", "1000000", "2000000"
            ], 
            "default_serial_port": "",
            "log_retention_days": 3 
        }
        
        self.settings = self._load_or_create_settings()
    def _load_or_create_settings(self):
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                
            is_updated = False
            for key, value in self.defaults.items():
                if key not in settings:
                    settings[key] = value
                    is_updated = True
                    
            if is_updated:
                self._save_settings(settings)
                
            return settings
            
        except (FileNotFoundError, json.JSONDecodeError):
            # logger尚未初始化，这里只能用print
            print(f"配置文件 '{self.filename}' 未找到或格式错误，将创建并使用默认设置。")
            self._save_settings(self.defaults)
            return self.defaults
    def _save_settings(self, settings):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
            
    def save_setting(self, key, value):
        self.settings[key] = value
        self._save_settings(self.settings)

# SerialWorker 和 PortScannerWorker 类
class SerialWorker(QObject):
    data_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, serial_instance, logger):
        super().__init__()
        self.ser = serial_instance
        self.logger = logger
        self._is_running = True
        
    def run(self):
        while self._is_running and self.ser.is_open:
            try:
                self.ser.timeout = 0.5 
                line = self.ser.readline()
                if line:
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    self.logger.debug(f"RECV: {line_str}")
                    self.data_received.emit(line_str)
            except serial.SerialException as e:
                self.logger.error(f"串口读取错误: {e}")
                self.error_occurred.emit(f"串口读取错误: {e}")
                self._is_running = False
            except Exception as e:
                self.logger.error(f"未知线程错误: {e}")
                self.error_occurred.emit(f"发生未知错误: {e}")
                self._is_running = False
                
    def stop(self):
        self._is_running = False
class PortScannerWorker(QObject):
    ports_updated = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self._is_running = True
        
    def run(self):
        while self._is_running:
            ports = [port.device for port in serial.tools.list_ports.comports()]
            self.ports_updated.emit(ports)
            QThread.msleep(1000)
            
    def stop(self):
        self._is_running = False

class SerialApp(QMainWindow):
    def __init__(self, settings_manager, logger, log_path):
        super().__init__()
        
        # 设置基本属性
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.settings
        self.logger = logger
        self.log_path = log_path
        self.logger.info("应用程序启动中...")
        
        # 设置窗口属性
        self.setWindowTitle("串口助手 v2.5 (稳定版)")
        self.setGeometry(100, 100, 700, 650)
        
        # 初始化变量
        self.log_buffer = []
        self.serial = serial.Serial()
        self.worker_thread = None
        self.serial_worker = None
        self.target_port = None
        self.is_port_intentionally_opened = False
        self.current_ports = []
        self.is_reconnecting = False
        
        # 初始化UI和端口
        self.initUI()
        self.apply_default_port()
        self.update_ports_display(self.current_ports)
        
        # 设置端口扫描线程
        self.port_scanner_thread = QThread()
        self.port_scanner_worker = PortScannerWorker()
        self.port_scanner_worker.moveToThread(self.port_scanner_thread)
        self.port_scanner_thread.started.connect(self.port_scanner_worker.run)
        self.port_scanner_worker.ports_updated.connect(self.on_ports_updated)
        self.port_scanner_thread.start()
        
        # 显示日志文件路径
        if self.log_path:
            log_path_html = f'--- [系统] 日志文件: <a href="file:///{self.log_path}" style="color: #87CEEB;">{self.log_path}</a> ---'
            self.data_display.append(log_path_html)
            
        self.logger.info("UI初始化完成。")
    def initUI(self):
        # 创建主窗口布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建控制栏布局
        controls_layout = QHBoxLayout()
        
        # 串口选择部分
        controls_layout.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.port_model = QStandardItemModel()
        self.port_combo.setModel(self.port_model)
        controls_layout.addWidget(self.port_combo)
        
        # 刷新和打开串口按钮
        self.refresh_button = QPushButton("刷新")
        controls_layout.addWidget(self.refresh_button)
        
        self.toggle_button = QPushButton("打开串口")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setMinimumWidth(100)
        controls_layout.addWidget(self.toggle_button)
        
        controls_layout.addStretch(1)
        
        # 波特率选择部分
        controls_layout.addWidget(QLabel("波特率:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(self.settings['available_baud_rates'])
        
        # 设置默认波特率
        default_baud = self.settings['default_baud_rate']
        if default_baud in self.settings['available_baud_rates']:
            self.baud_combo.setCurrentText(default_baud)
        elif self.settings['available_baud_rates']:
            self.baud_combo.setCurrentIndex(0)
            
        controls_layout.addWidget(self.baud_combo)
        main_layout.addLayout(controls_layout)
        # 创建过滤器布局
        filter_group_layout = QVBoxLayout()
        filter_group_layout.setSpacing(5)
        
        # 包含过滤器
        include_layout = QHBoxLayout()
        include_layout.addWidget(QLabel("实时显示包含:"))
        self.include_filter_input = QLineEdit()
        self.include_filter_input.setPlaceholderText("例如: error;warning (用';'分隔)")
        include_layout.addWidget(self.include_filter_input)
        filter_group_layout.addLayout(include_layout)
        
        # 排除过滤器
        exclude_layout = QHBoxLayout()
        exclude_layout.addWidget(QLabel("实时排除包含:"))
        self.exclude_filter_input = QLineEdit()
        self.exclude_filter_input.setPlaceholderText("例如: debug;info (用';'分隔)")
        exclude_layout.addWidget(self.exclude_filter_input)
        filter_group_layout.addLayout(exclude_layout)
        
        main_layout.addLayout(filter_group_layout)
        
        # 数据显示区域
        self.data_display = QTextBrowser()
        self.data_display.setReadOnly(True)
        self.data_display.setOpenExternalLinks(True)
        main_layout.addWidget(self.data_display)
        
        # 历史记录过滤器布局
        history_filter_layout = QHBoxLayout()
        history_filter_layout.addWidget(QLabel("筛选历史记录:"))
        self.history_filter_input = QLineEdit()
        self.history_filter_input.setPlaceholderText("在此输入关键字，按'应用'筛选已显示内容...")
        
        self.apply_history_filter_button = QPushButton("应用筛选")
        history_filter_layout.addWidget(self.history_filter_input)
        history_filter_layout.addWidget(self.apply_history_filter_button)
        main_layout.addLayout(history_filter_layout)
        
        # 操作按钮布局
        actions_layout = QHBoxLayout()
        self.clear_button = QPushButton("清空所有数据")
        self.save_visible_button = QPushButton("保存当前显示")
        self.save_all_button = QPushButton("保存全部记录")
        
        actions_layout.addWidget(self.clear_button)
        actions_layout.addWidget(self.save_visible_button)
        actions_layout.addWidget(self.save_all_button)
        main_layout.addLayout(actions_layout)
        
        # 连接信号槽
        self.connect_signals()
    def connect_signals(self):
        # 端口控制信号
        self.refresh_button.clicked.connect(lambda: 
            self.on_ports_updated([port.device for port in serial.tools.list_ports.comports()]))
        self.toggle_button.toggled.connect(self.toggle_port)
        self.port_combo.currentTextChanged.connect(self.save_current_port_as_default)
        
        # 过滤器信号
        self.include_filter_input.returnPressed.connect(self.apply_filter_status)
        self.exclude_filter_input.returnPressed.connect(self.apply_filter_status)
        self.apply_history_filter_button.clicked.connect(self.refilter_display)
        self.history_filter_input.returnPressed.connect(self.refilter_display)
        
        # 数据操作信号
        self.clear_button.clicked.connect(self.clear_all_data)
        self.save_visible_button.clicked.connect(self.save_visible_data)
        self.save_all_button.clicked.connect(self.save_all_data)
    def _attempt_open_port(self):
        self.toggle_button.setText("关闭串口")
        self.set_controls_enabled(False)
        
        port_name = self.target_port
        baud_text = self.baud_combo.currentText()
        
        try:
            # 验证端口和波特率
            if not port_name or "无可用串口" in port_name:
                raise ValueError("无效的串口选择")
                
            if not baud_text.isdigit():
                raise ValueError(f"无效的波特率: {baud_text}")
                
            baud_rate = int(baud_text)
            self.logger.info(f"尝试打开串口 {port_name}，波特率 {baud_rate}...")
            
            # 配置串口参数
            self.serial.port = port_name
            self.serial.baudrate = baud_rate
            self.serial.bytesize = serial.EIGHTBITS
            self.serial.parity = serial.PARITY_NONE
            self.serial.stopbits = serial.STOPBITS_ONE
            self.serial.open()
            
            self.logger.info(f"串口 {port_name} 打开成功。")
            
            # 创建并启动串口工作线程
            self.serial_worker = SerialWorker(self.serial, self.logger)
            self.worker_thread = QThread()
            self.serial_worker.moveToThread(self.worker_thread)
            self.worker_thread.finished.connect(self.on_thread_finished)
            self.serial_worker.data_received.connect(self.append_data)
            self.serial_worker.error_occurred.connect(self.on_serial_error)
            self.worker_thread.started.connect(self.serial_worker.run)
            self.worker_thread.start()
            
        except Exception as e:
            self.logger.error(f"打开串口 {port_name} 失败: {e}")
            self.on_serial_error(f"无法打开串口 {port_name}: {e}")
    def toggle_port(self, checked):
        self.is_port_intentionally_opened = checked
        
        if checked:
            # 打开串口
            self.target_port = self.port_combo.currentText()
            
            # 确保按钮状态正确
            self.toggle_button.blockSignals(True)
            self.toggle_button.setChecked(True)
            self.toggle_button.blockSignals(False)
            
            self._attempt_open_port()
        else:
            # 关闭串口
            self.logger.info(f"用户请求关闭串口 {self.target_port}。")
            self.close_serial_port()
    def on_ports_updated(self, new_ports_list):
        # 如果端口列表没有变化，不做处理
        if new_ports_list == self.current_ports:
            return
            
        self.logger.info(f"串口列表变化: {self.current_ports} -> {new_ports_list}")
        self.update_ports_display(new_ports_list)
        
        # 如果用户已经打开了串口，但串口已断开，尝试自动重连
        if self.is_port_intentionally_opened and self.target_port and not self.serial.is_open:
            if self.target_port in self.current_ports:
                self.logger.info(f"检测到目标端口 {self.target_port}，尝试自动重连...")
                self.data_display.append(f"--- [系统] 检测到目标端口 {self.target_port}，自动重连 ---")
                
                # 设置按钮状态并尝试重连
                self.toggle_button.blockSignals(True)
                self.toggle_button.setChecked(True)
                self.toggle_button.blockSignals(False)
                self._attempt_open_port()
    def update_ports_display(self, new_ports_list):
        # 更新当前端口列表
        self.current_ports = new_ports_list
        
        # 阻止信号触发并清空模型
        self.port_combo.blockSignals(True)
        self.port_model.clear()
        
        # 准备要显示的端口列表
        ports_to_display = set(new_ports_list)
        if self.target_port:
            ports_to_display.add(self.target_port)
            
        # 如果没有可用端口，显示提示
        if not ports_to_display:
            self.port_model.appendRow(QStandardItem("无可用串口"))
        else:
            # 添加所有端口到下拉列表
            for port_name in sorted(list(ports_to_display)):
                item = QStandardItem(port_name)
                if port_name not in new_ports_list:
                    # 标记已断开的端口
                    item.setForeground(QColor("red"))
                    item.setToolTip(f"端口 {port_name} 目前已断开连接")
                self.port_model.appendRow(item)
        
        # 设置当前选中的端口
        if self.target_port:
            index = self.port_combo.findText(self.target_port)
            if index != -1:
                self.port_combo.setCurrentIndex(index)
        elif self.port_model.rowCount() > 0:
            self.port_combo.setCurrentIndex(0)
            
        # 恢复信号处理
        self.port_combo.blockSignals(False)
    def on_thread_finished(self):
        # 关闭串口如果还没有关闭
        if self.serial.is_open:
            self.logger.info(f"串口 {self.serial.port} 已关闭。")
            self.serial.close()
        
        # 清理线程资源
        self.serial_worker = None
        self.worker_thread = None
        
        # 恢复控件状态
        self.set_controls_enabled(True)
        self.toggle_button.setEnabled(True)
        
        # 重置按钮状态
        self.toggle_button.blockSignals(True)
        self.toggle_button.setText("打开串口")
        self.toggle_button.setChecked(False)
        self.toggle_button.blockSignals(False)
    def closeEvent(self, event):
        self.logger.info("应用程序关闭...")
        
        # 停止端口扫描线程
        self.port_scanner_worker.stop()
        self.port_scanner_thread.quit()
        self.port_scanner_thread.wait(1500)
        
        # 如果串口线程正在运行，停止它
        if self.worker_thread and self.worker_thread.isRunning():
            self.serial_worker.stop()
            self.worker_thread.quit()
            self.worker_thread.wait(2000)
            
        event.accept()
    def on_serial_error(self, error_message):
        # 记录错误
        self.logger.error(f"on_serial_error: {error_message}")
        
        # 在UI中显示错误
        error_log = f'<font color="red">--- [串口错误] {error_message} ---</font>'
        self.data_display.append(error_log)
        self.log_buffer.append(f"--- [串口错误] {error_message} ---")
        
        # 如果线程还在运行，关闭串口
        if self.worker_thread and self.worker_thread.isRunning():
            self.close_serial_port()
    def save_current_port_as_default(self, port_name):
        # 如果选择了有效的端口，保存为默认值
        if port_name and "无可用串口" not in port_name:
            self.logger.info(f"用户选择新端口 {port_name}，保存为默认值。")
            self.target_port = port_name
            self.settings_manager.save_setting('default_serial_port', port_name)
            
    def apply_default_port(self):
        # 从配置中加载默认端口
        preferred_port = self.settings.get('default_serial_port', '')
        if preferred_port:
            self.target_port = preferred_port
            
        self.logger.info(f"从配置加载默认目标端口: '{preferred_port}'")
    def clear_all_data(self):
        # 清空所有数据
        self.log_buffer.clear()
        self.data_display.clear()
        self.logger.info("所有数据已被用户清空。")
    def append_data(self, text):
        # 获取当前过滤器设置
        include_text = self.include_filter_input.text().strip()
        exclude_text = self.exclude_filter_input.text().strip()
        
        # 处理关键字列表
        include_keywords = [k.strip() for k in include_text.split(';') if k.strip()]
        exclude_keywords = [k.strip() for k in exclude_text.split(';') if k.strip()]
        
        # 应用排除过滤器
        if exclude_keywords and any(keyword in text for keyword in exclude_keywords):
            return
            
        # 应用包含过滤器
        if include_keywords and not any(keyword in text for keyword in include_keywords):
            return
            
        # 添加到日志缓冲区
        self.log_buffer.append(text)
        
        # 检查历史记录过滤器
        history_filter_text = self.history_filter_input.text().strip()
        if not history_filter_text or history_filter_text in text:
            # 显示数据并滚动到底部
            self.data_display.append(text)
            self.data_display.verticalScrollBar().setValue(
                self.data_display.verticalScrollBar().maximum())
    def refilter_display(self):
        # 获取当前过滤器文本
        history_filter_text = self.history_filter_input.text().strip()
        self.logger.info(f"应用历史筛选，关键字: '{history_filter_text}'")
        
        # 清空当前显示
        self.data_display.clear()
        
        # 根据过滤器显示内容
        if not history_filter_text:
            # 无过滤器，显示所有内容
            self.data_display.setPlainText("\n".join(self.log_buffer))
        else:
            # 有过滤器，只显示匹配的行
            filtered_lines = [line for line in self.log_buffer if history_filter_text in line]
            self.data_display.setPlainText("\n".join(filtered_lines))
        
        # 滚动到底部并刷新UI
        self.data_display.verticalScrollBar().setValue(
            self.data_display.verticalScrollBar().maximum())
        QApplication.processEvents()
    def save_visible_data(self):
        """保存当前显示的数据"""
        self._save_content_to_file(self.data_display.toPlainText(), "visible_")
        
    def save_all_data(self):
        """保存所有数据记录"""
        self._save_content_to_file("\n".join(self.log_buffer), "all_")
        
    def _save_content_to_file(self, content, prefix=""):
        """将内容保存到文件"""
        # 检查是否有内容可保存
        if not content:
            QMessageBox.information(self, "提示", "没有数据可以保存.")
            return
            
        # 生成默认文件名
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
        default_filename = f"serial_data_{prefix}{timestamp}.txt"
        self.logger.info(f"准备保存数据到文件: {default_filename}")
        
        # 显示保存对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存数据", default_filename, "Text Files (*.txt);;All Files (*)")
            
        if file_path:
            try:
                # 尝试保存文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                self.logger.info(f"数据成功保存到: {file_path}")
                QMessageBox.information(self, "成功", f"数据已成功保存到:\n{file_path}")
                
            except Exception as e:
                self.logger.error(f"保存文件失败: {e}")
                QMessageBox.critical(self, "保存失败", f"保存文件时发生错误: {e}")
    def set_controls_enabled(self, is_enabled):
        """设置控件的启用状态"""
        self.port_combo.setEnabled(is_enabled)
        self.baud_combo.setEnabled(is_enabled)
        self.refresh_button.setEnabled(is_enabled)
        
    def close_serial_port(self):
        """关闭串口连接"""
        if self.worker_thread and self.worker_thread.isRunning():
            # 如果线程正在运行，停止它
            self.toggle_button.setText("关闭中…")
            self.toggle_button.setEnabled(False)
            self.serial_worker.stop()
            self.worker_thread.quit()
        else:
            # 如果线程没有运行，直接调用完成函数
            self.on_thread_finished()
    def apply_filter_status(self):
        """应用实时过滤器并显示状态"""
        # 获取过滤器文本
        include_text = self.include_filter_input.text().strip()
        exclude_text = self.exclude_filter_input.text().strip()
        
        # 处理关键字列表
        include_keywords = [k.strip() for k in include_text.split(';') if k.strip()]
        exclude_keywords = [k.strip() for k in exclude_text.split(';') if k.strip()]
        
        # 如果没有过滤器，显示清空消息
        if not include_keywords and not exclude_keywords:
            self.data_display.append("--- [所有实时筛选已清空] ---")
            return
            
        # 准备过滤器状态消息
        include_part = f"显示: {', '.join([f'{k}' for k in include_keywords])}" if include_keywords else "显示: [所有]"
        exclude_part = f"排除: {', '.join([f'{k}' for k in exclude_keywords])}" if exclude_keywords else "排除: [无]"
        
        # 显示过滤器状态
        self.data_display.append(f"--- [实时筛选已更新 | {include_part} | {exclude_part}] ---")

if __name__ == '__main__':
    # 初始化配置和日志系统
    settings_manager = SettingsManager()
    logger, log_file_path = setup_logging(settings_manager.settings)
    
    # 创建应用程序
    app = QApplication(sys.argv)
    
    # 设置全局字体
    default_font = QFont()
    default_font.setFamilies(["Consolas", "Monaco", "Courier New", "monospace"])
    default_font.setPointSize(settings_manager.settings['font_size'])
    app.setFont(default_font)
    
    # 创建并显示主窗口
    window = SerialApp(settings_manager, logger, log_file_path)
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec())