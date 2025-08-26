import sys
import json
import logging
import logging.handlers
import serial
import serial.tools.list_ports
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QComboBox, QTextBrowser, 
                             QLabel, QLineEdit, QMessageBox, QFileDialog)
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QDateTime, QTimer, QUrl
from PyQt6.QtGui import QFont, QStandardItemModel, QStandardItem, QColor, QDesktopServices

# 【修改点2】setup_logging 函数现在接收 settings 字典
def setup_logging(settings):
    """配置日志系统，使用带时间戳的日志名，并根据配置清理旧日志"""
    try:
        if getattr(sys, 'frozen', False): base_path = Path(sys.executable).parent
        else: base_path = Path(__file__).parent
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
                    log_file.unlink(); print(f"已删除超过 {retention_days} 天的旧日志: {log_file.name}")
            except (ValueError, IndexError):
                print(f"无法解析日志文件名: {log_file.name}"); continue
        
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        log_filename = f"serial_tool_{timestamp}.log"
        log_file_path = log_dir / log_filename
        print(f"日志文件将被保存在: {log_file_path}")
        log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        if root_logger.hasHandlers(): root_logger.handlers.clear()
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setFormatter(log_formatter); file_handler.setLevel(logging.DEBUG); root_logger.addHandler(file_handler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter); console_handler.setLevel(logging.INFO); root_logger.addHandler(console_handler)
        return logging.getLogger("SerialApp"), log_file_path
    except Exception as e:
        print(f"日志系统初始化失败: {e}")
        return logging.getLogger("SerialApp"), None

class SettingsManager:
    def __init__(self, filename='config.json'):
        if getattr(sys, 'frozen', False): base_path = Path(sys.executable).parent
        else: base_path = Path(__file__).parent
        self.filename = base_path / filename
        # 【修改点1】新增 log_retention_days 默认配置
        self.defaults = { 
            "font_size": 12, 
            "default_baud_rate": "1000000", 
            "available_baud_rates": [ "9600", "19200", "38400", "57600", "115200", "1000000", "2000000" ], 
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
            if is_updated: self._save_settings(settings)
            return settings
        except (FileNotFoundError, json.JSONDecodeError):
            # logger尚未初始化，这里只能用print
            print(f"配置文件 '{self.filename}' 未找到或格式错误，将创建并使用默认设置。")
            self._save_settings(self.defaults); return self.defaults
    def _save_settings(self, settings):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
    def save_setting(self, key, value):
        self.settings[key] = value; self._save_settings(self.settings)

# ... SerialWorker 和 PortScannerWorker 类保持不变 ...
class SerialWorker(QObject):
    data_received = pyqtSignal(str); error_occurred = pyqtSignal(str)
    def __init__(self, serial_instance, logger):
        super().__init__(); self.ser = serial_instance; self.logger = logger; self._is_running = True
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
                self.logger.error(f"串口读取错误: {e}"); self.error_occurred.emit(f"串口读取错误: {e}"); self._is_running = False
            except Exception as e:
                self.logger.error(f"未知线程错误: {e}"); self.error_occurred.emit(f"发生未知错误: {e}"); self._is_running = False
    def stop(self): self._is_running = False
class PortScannerWorker(QObject):
    ports_updated = pyqtSignal(list)
    def __init__(self):
        super().__init__(); self._is_running = True
    def run(self):
        while self._is_running:
            ports = [port.device for port in serial.tools.list_ports.comports()]
            self.ports_updated.emit(ports); QThread.msleep(1000)
    def stop(self): self._is_running = False

class SerialApp(QMainWindow):
    # ... 此类完全不变 ...
    def __init__(self, settings_manager, logger, log_path):
        super().__init__()
        self.settings_manager = settings_manager; self.settings = self.settings_manager.settings
        self.logger = logger; self.log_path = log_path
        self.logger.info("应用程序启动中...")
        self.setWindowTitle("串口助手 v2.5 (稳定版)")
        self.setGeometry(100, 100, 700, 650); self.log_buffer = []
        self.serial = serial.Serial(); self.worker_thread = None; self.serial_worker = None
        self.target_port = None; self.is_port_intentionally_opened = False; self.current_ports = []
        self.is_reconnecting = False
        self.initUI(); self.apply_default_port(); self.update_ports_display(self.current_ports)
        self.port_scanner_thread = QThread()
        self.port_scanner_worker = PortScannerWorker()
        self.port_scanner_worker.moveToThread(self.port_scanner_thread)
        self.port_scanner_thread.started.connect(self.port_scanner_worker.run)
        self.port_scanner_worker.ports_updated.connect(self.on_ports_updated)
        self.port_scanner_thread.start()
        if self.log_path:
            log_path_html = f'--- [系统] 日志文件: <a href="file:///{self.log_path}" style="color: #87CEEB;">{self.log_path}</a> ---'
            self.data_display.append(log_path_html)
        self.logger.info("UI初始化完成。")
    def initUI(self):
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget); controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("串口:")); self.port_combo = QComboBox()
        self.port_model = QStandardItemModel(); self.port_combo.setModel(self.port_model)
        controls_layout.addWidget(self.port_combo); self.refresh_button = QPushButton("刷新")
        controls_layout.addWidget(self.refresh_button); self.toggle_button = QPushButton("打开串口")
        self.toggle_button.setCheckable(True); self.toggle_button.setMinimumWidth(100)
        controls_layout.addWidget(self.toggle_button); controls_layout.addStretch(1)
        controls_layout.addWidget(QLabel("波特率:")); self.baud_combo = QComboBox()
        self.baud_combo.addItems(self.settings['available_baud_rates'])
        default_baud = self.settings['default_baud_rate']
        if default_baud in self.settings['available_baud_rates']: self.baud_combo.setCurrentText(default_baud)
        elif self.settings['available_baud_rates']: self.baud_combo.setCurrentIndex(0)
        controls_layout.addWidget(self.baud_combo); main_layout.addLayout(controls_layout)
        filter_group_layout = QVBoxLayout(); filter_group_layout.setSpacing(5)
        include_layout = QHBoxLayout(); include_layout.addWidget(QLabel("实时显示包含:"))
        self.include_filter_input = QLineEdit(); self.include_filter_input.setPlaceholderText("例如: error;warning (用';'分隔)")
        include_layout.addWidget(self.include_filter_input); filter_group_layout.addLayout(include_layout)
        exclude_layout = QHBoxLayout(); exclude_layout.addWidget(QLabel("实时排除包含:"))
        self.exclude_filter_input = QLineEdit(); self.exclude_filter_input.setPlaceholderText("例如: debug;info (用';'分隔)")
        exclude_layout.addWidget(self.exclude_filter_input); filter_group_layout.addLayout(exclude_layout)
        main_layout.addLayout(filter_group_layout); self.data_display = QTextBrowser()
        self.data_display.setReadOnly(True); self.data_display.setOpenExternalLinks(True)
        main_layout.addWidget(self.data_display); history_filter_layout = QHBoxLayout()
        history_filter_layout.addWidget(QLabel("筛选历史记录:"))
        self.history_filter_input = QLineEdit(); self.history_filter_input.setPlaceholderText("在此输入关键字，按'应用'筛选已显示内容...")
        self.apply_history_filter_button = QPushButton("应用筛选")
        history_filter_layout.addWidget(self.history_filter_input); history_filter_layout.addWidget(self.apply_history_filter_button)
        main_layout.addLayout(history_filter_layout); actions_layout = QHBoxLayout()
        self.clear_button = QPushButton("清空所有数据"); self.save_visible_button = QPushButton("保存当前显示")
        self.save_all_button = QPushButton("保存全部记录"); actions_layout.addWidget(self.clear_button)
        actions_layout.addWidget(self.save_visible_button); actions_layout.addWidget(self.save_all_button)
        main_layout.addLayout(actions_layout); self.connect_signals()
    def connect_signals(self):
        self.refresh_button.clicked.connect(lambda: self.on_ports_updated([port.device for port in serial.tools.list_ports.comports()]))
        self.toggle_button.toggled.connect(self.toggle_port)
        self.include_filter_input.returnPressed.connect(self.apply_filter_status)
        self.exclude_filter_input.returnPressed.connect(self.apply_filter_status)
        self.clear_button.clicked.connect(self.clear_all_data)
        self.port_combo.currentTextChanged.connect(self.save_current_port_as_default)
        self.apply_history_filter_button.clicked.connect(self.refilter_display)
        self.history_filter_input.returnPressed.connect(self.refilter_display)
        self.save_visible_button.clicked.connect(self.save_visible_data)
        self.save_all_button.clicked.connect(self.save_all_data)
    def _attempt_open_port(self):
        self.toggle_button.setText("关闭串口"); self.set_controls_enabled(False)
        port_name = self.target_port; baud_text = self.baud_combo.currentText()
        try:
            if not port_name or "无可用串口" in port_name: raise ValueError("无效的串口选择")
            if not baud_text.isdigit(): raise ValueError(f"无效的波特率: {baud_text}")
            baud_rate = int(baud_text)
            self.logger.info(f"尝试打开串口 {port_name}，波特率 {baud_rate}...")
            self.serial.port = port_name; self.serial.baudrate = baud_rate; self.serial.bytesize = serial.EIGHTBITS; self.serial.parity = serial.PARITY_NONE; self.serial.stopbits = serial.STOPBITS_ONE; self.serial.open()
            self.logger.info(f"串口 {port_name} 打开成功。")
            self.serial_worker = SerialWorker(self.serial, self.logger); self.worker_thread = QThread()
            self.serial_worker.moveToThread(self.worker_thread); self.worker_thread.finished.connect(self.on_thread_finished)
            self.serial_worker.data_received.connect(self.append_data); self.serial_worker.error_occurred.connect(self.on_serial_error)
            self.worker_thread.started.connect(self.serial_worker.run); self.worker_thread.start()
        except Exception as e:
            self.logger.error(f"打开串口 {port_name} 失败: {e}"); self.on_serial_error(f"无法打开串口 {port_name}: {e}")
    def toggle_port(self, checked):
        self.is_port_intentionally_opened = checked
        if checked:
            self.target_port = self.port_combo.currentText()
            self.toggle_button.blockSignals(True); self.toggle_button.setChecked(True); self.toggle_button.blockSignals(False)
            self._attempt_open_port()
        else:
            self.logger.info(f"用户请求关闭串口 {self.target_port}。"); self.close_serial_port()
    def on_ports_updated(self, new_ports_list):
        if new_ports_list == self.current_ports: return
        self.logger.info(f"串口列表变化: {self.current_ports} -> {new_ports_list}")
        self.update_ports_display(new_ports_list)
        if self.is_port_intentionally_opened and self.target_port and not self.serial.is_open:
            if self.target_port in self.current_ports:
                self.logger.info(f"检测到目标端口 {self.target_port}，尝试自动重连...")
                self.data_display.append(f"--- [系统] 检测到目标端口 {self.target_port}，自动重连 ---")
                self.toggle_button.blockSignals(True); self.toggle_button.setChecked(True); self.toggle_button.blockSignals(False); self._attempt_open_port()
    def update_ports_display(self, new_ports_list):
        self.current_ports = new_ports_list; self.port_combo.blockSignals(True); self.port_model.clear()
        ports_to_display = set(new_ports_list)
        if self.target_port: ports_to_display.add(self.target_port)
        if not ports_to_display: self.port_model.appendRow(QStandardItem("无可用串口"))
        else:
            for port_name in sorted(list(ports_to_display)):
                item = QStandardItem(port_name)
                if port_name not in new_ports_list:
                    item.setForeground(QColor("red")); item.setToolTip(f"端口 {port_name} 目前已断开连接")
                self.port_model.appendRow(item)
        if self.target_port:
            index = self.port_combo.findText(self.target_port)
            if index != -1: self.port_combo.setCurrentIndex(index)
        elif self.port_model.rowCount() > 0: self.port_combo.setCurrentIndex(0)
        self.port_combo.blockSignals(False)
    def on_thread_finished(self):
        if self.serial.is_open: self.logger.info(f"串口 {self.serial.port} 已关闭。"); self.serial.close()
        self.serial_worker = None; self.worker_thread = None
        self.set_controls_enabled(True); self.toggle_button.setEnabled(True)
        self.toggle_button.blockSignals(True)
        self.toggle_button.setText("打开串口"); self.toggle_button.setChecked(False)
        self.toggle_button.blockSignals(False)
    def closeEvent(self, event):
        self.logger.info("应用程序关闭...")
        self.port_scanner_worker.stop(); self.port_scanner_thread.quit(); self.port_scanner_thread.wait(1500)
        if self.worker_thread and self.worker_thread.isRunning():
            self.serial_worker.stop(); self.worker_thread.quit(); self.worker_thread.wait(2000)
        event.accept()
    def on_serial_error(self, error_message):
        self.logger.error(f"on_serial_error: {error_message}")
        error_log = f'<font color="red">--- [串口错误] {error_message} ---</font>'
        self.data_display.append(error_log); self.log_buffer.append(f"--- [串口错误] {error_message} ---")
        if self.worker_thread and self.worker_thread.isRunning(): self.close_serial_port()
    def save_current_port_as_default(self, port_name):
        if port_name and "无可用串口" not in port_name:
            self.logger.info(f"用户选择新端口 {port_name}，保存为默认值。")
            self.target_port = port_name; self.settings_manager.save_setting('default_serial_port', port_name)
    def apply_default_port(self):
        preferred_port = self.settings.get('default_serial_port', '')
        if preferred_port: self.target_port = preferred_port
        self.logger.info(f"从配置加载默认目标端口: '{preferred_port}'")
    def clear_all_data(self):
        self.log_buffer.clear(); self.data_display.clear(); self.logger.info("所有数据已被用户清空。")
    def append_data(self, text):
        include_text = self.include_filter_input.text().strip(); exclude_text = self.exclude_filter_input.text().strip()
        include_keywords = [k.strip() for k in include_text.split(';') if k.strip()]
        exclude_keywords = [k.strip() for k in exclude_text.split(';') if k.strip()]
        if exclude_keywords and any(keyword in text for keyword in exclude_keywords): return
        if include_keywords and not any(keyword in text for keyword in include_keywords): return
        self.log_buffer.append(text)
        history_filter_text = self.history_filter_input.text().strip()
        if not history_filter_text or history_filter_text in text:
            self.data_display.append(text)
            self.data_display.verticalScrollBar().setValue(self.data_display.verticalScrollBar().maximum())
    def refilter_display(self):
        history_filter_text = self.history_filter_input.text().strip()
        self.logger.info(f"应用历史筛选，关键字: '{history_filter_text}'")
        self.data_display.clear()
        if not history_filter_text: self.data_display.setPlainText("\n".join(self.log_buffer))
        else: self.data_display.setPlainText("\n".join([line for line in self.log_buffer if history_filter_text in line]))
        self.data_display.verticalScrollBar().setValue(self.data_display.verticalScrollBar().maximum())
        QApplication.processEvents()
    def save_visible_data(self):
        self._save_content_to_file(self.data_display.toPlainText(), "visible_")
    def save_all_data(self):
        self._save_content_to_file("\n".join(self.log_buffer), "all_")
    def _save_content_to_file(self, content, prefix=""):
        if not content: QMessageBox.information(self, "提示", "没有数据可以保存."); return
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
        default_filename = f"serial_data_{prefix}{timestamp}.txt"
        self.logger.info(f"准备保存数据到文件: {default_filename}")
        file_path, _ = QFileDialog.getSaveFileName(self, "保存数据", default_filename, "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
                self.logger.info(f"数据成功保存到: {file_path}")
                QMessageBox.information(self, "成功", f"数据已成功保存到:\n{file_path}")
            except Exception as e:
                self.logger.error(f"保存文件失败: {e}"); QMessageBox.critical(self, "保存失败", f"保存文件时发生错误: {e}")
    def set_controls_enabled(self, is_enabled):
        self.port_combo.setEnabled(is_enabled); self.baud_combo.setEnabled(is_enabled); self.refresh_button.setEnabled(is_enabled)
    def close_serial_port(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.toggle_button.setText("关闭中…"); self.toggle_button.setEnabled(False)
            self.serial_worker.stop(); self.worker_thread.quit()
        else: self.on_thread_finished()
    def apply_filter_status(self):
        include_text = self.include_filter_input.text().strip(); exclude_text = self.exclude_filter_input.text().strip()
        include_keywords = [k.strip() for k in include_text.split(';') if k.strip()]
        exclude_keywords = [k.strip() for k in exclude_text.split(';') if k.strip()]
        if not include_keywords and not exclude_keywords: self.data_display.append("--- [所有实时筛选已清空] ---"); return
        include_part = f"显示: {', '.join([f'{k}' for k in include_keywords])}" if include_keywords else "显示: [所有]"
        exclude_part = f"排除: {', '.join([f'{k}' for k in exclude_keywords])}" if exclude_keywords else "排除: [无]"
        self.data_display.append(f"--- [实时筛选已更新 | {include_part} | {exclude_part}] ---")

if __name__ == '__main__':
    # 【修改点3】调整启动顺序和函数调用
    settings_manager = SettingsManager()
    logger, log_file_path = setup_logging(settings_manager.settings)
    
    app = QApplication(sys.argv)
    
    default_font = QFont()
    default_font.setFamilies(["Consolas", "Monaco", "Courier New", "monospace"])
    default_font.setPointSize(settings_manager.settings['font_size'])
    app.setFont(default_font)

    window = SerialApp(settings_manager, logger, log_file_path)
    window.show()
    sys.exit(app.exec())