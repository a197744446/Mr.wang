#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鎶栭煶鐩存挱闂寸洃鎺у櫒 v1.0
鐩戞帶澶氫釜鐩存挱闂寸殑寮€鎾?鍏虫挱鐘舵€佸強瀹炴椂鍦ㄧ嚎浜烘暟
鏀寔 Windows / macOS / Linux
渚濊禆: pip install requests pyqt5
"""

import sys
import os
import json
import time
import re
import logging
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("姝ｅ湪瀹夎 requests...")
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGroupBox, QLabel, QPushButton, QLineEdit, QListWidget,
        QListWidgetItem, QTextEdit, QGridLayout, QSpinBox, QSystemTrayIcon,
        QMenu, QAction, QMessageBox, QFileDialog, QSplitter, QFrame,
        QHeaderView, QAbstractItemView, QStyle, QSize
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt5.QtGui import QFont, QColor, QIcon, QPalette
except ImportError:
    print("姝ｅ湪瀹夎 PyQt5...")
    os.system(f"{sys.executable} -m pip install PyQt5 -q")
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGroupBox, QLabel, QPushButton, QLineEdit, QListWidget,
        QListWidgetItem, QTextEdit, QGridLayout, QSpinBox, QSystemTrayIcon,
        QMenu, QAction, QMessageBox, QFileDialog, QSplitter, QFrame,
        QHeaderView, QAbstractItemView, QStyle, QSize
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
    from PyQt5.QtGui import QFont, QColor, QIcon, QPalette


# ==================== 鍏ㄥ眬閰嶇疆 ====================

CONFIG_FILE = Path(__file__).parent / "douyin_monitor_config.json"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://live.douyin.com/",
    "Accept": "application/json, text/plain, */*"
}

DEFAULT_CONFIG = {
    "refresh_interval": 10,
    "rooms": [],
    "enable_notification": True,
    "sound_alert": True
}


# ==================== 鏁版嵁妯″瀷 ====================

class RoomInfo:
    def __init__(self, url="", room_id=""):
        self.url = url
        self.room_id = room_id
        self.anchor_name = f"鎴块棿 {room_id}"
        self.is_live = False
        self.online_count = 0
        self.peak_count = 0
        self.status_text = "绛夊緟妫€娴?
        self.live_start_time = None
        self.was_live = False
        self.last_check = None
        self.error_count = 0
        self.cover_url = ""

    def to_dict(self):
        return {
            "url": self.url,
            "room_id": self.room_id,
            "anchor_name": self.anchor_name
        }


# ==================== API 璇锋眰 ====================

def extract_room_id(input_text):
    """浠庡悇绉嶆牸寮忕殑杈撳叆涓彁鍙栨埧闂碔D"""
    input_text = input_text.strip()

    # https://live.douyin.com/123456789
    match = re.search(r"live\.douyin\.com/(\d+)", input_text)
    if match:
        return match.group(1)

    # https://v.douyin.com/xxxxx/
    match = re.search(r"v\.douyin\.com/(\w+)", input_text)
    if match:
        try:
            resp = requests.get(
                f"https://v.douyin.com/{match.group(1)}/",
                allow_redirects=False, timeout=10, headers=DEFAULT_HEADERS
            )
            location = resp.headers.get("Location", "")
            m2 = re.search(r"/(\d+)", location)
            if m2:
                return m2.group(1)
        except Exception:
            pass
        return match.group(1)

    # 绾暟瀛?    match = re.match(r"^(\d{5,20})$", input_text)
    if match:
        return match.group(1)

    return input_text


def build_live_url(room_id):
    return f"https://live.douyin.com/{room_id}"


def fetch_room_status(room_id):
    """璇锋眰鎶栭煶API鑾峰彇鐩存挱闂寸姸鎬?""
    url = f"https://webcast.amemv.com/webcast/room/reflow/{room_id}"
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_room_data(data):
    """瑙ｆ瀽API杩斿洖鏁版嵁"""
    result = {}

    try:
        status_code = data.get("status_code", -1)
        rooms = data.get("data", [])
        if not rooms:
            return result

        room_obj = rooms[0].get("room", {})

        # 涓绘挱淇℃伅
        owner = room_obj.get("owner", {})
        result["anchor_name"] = owner.get("nickname", "鏈煡涓绘挱")
        result["room_id"] = str(room_obj.get("id_str", ""))
        result["cover_url"] = room_obj.get("cover", {}).get("url_list", [""])[0]

        # 鐩存挱鐘舵€?        result["is_live"] = room_obj.get("status") == 2

        # 鍦ㄧ嚎浜烘暟
        result["online_count"] = room_obj.get("online_user_count", 0)

        # 瑙備紬鎬绘暟
        result["total_view"] = room_obj.get("total_user_count", 0)

    except Exception as e:
        result["error"] = str(e)

    return result


# ==================== 鐩戞帶绾跨▼ ====================

class MonitorThread(QThread):
    room_updated = pyqtSignal(dict)  # {room_id, is_live, anchor_name, online_count, status}
    room_error = pyqtSignal(str, str)  # room_id, error_msg

    def __init__(self, room_info):
        super().__init__()
        self.room_info = room_info

    def run(self):
        try:
            data = fetch_room_status(self.room_info.room_id)
            parsed = parse_room_data(data)

            if "error" in parsed:
                self.room_error.emit(self.room_info.room_id, parsed["error"])
                return

            self.room_updated.emit({
                "room_id": self.room_info.room_id,
                "is_live": parsed.get("is_live", False),
                "anchor_name": parsed.get("anchor_name", "鏈煡"),
                "online_count": parsed.get("online_count", 0),
                "total_view": parsed.get("total_view", 0),
                "cover_url": parsed.get("cover_url", ""),
            })
        except requests.exceptions.Timeout:
            self.room_error.emit(self.room_info.room_id, "璇锋眰瓒呮椂")
        except requests.exceptions.ConnectionError:
            self.room_error.emit(self.room_info.room_id, "缃戠粶杩炴帴澶辫触")
        except Exception as e:
            self.room_error.emit(self.room_info.room_id, str(e)[:50])


# ==================== 涓荤獥鍙?====================

class MonitorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.rooms = []
        self.config = self.load_config()
        self.is_monitoring = False
        self.threads = []

        self.init_ui()
        self.load_rooms_from_config()
        self.init_tray()

    def init_ui(self):
        self.setWindowTitle("馃摵 鎶栭煶鐩存挱闂寸洃鎺у櫒 v1.0")
        self.setMinimumSize(1000, 700)
        self.resize(1100, 750)

        # 鍏ㄥ眬鏍峰紡
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QWidget { background-color: #1e1e2e; color: #cdd6f4; }
            QGroupBox {
                border: 1px solid #45475a;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                font-size: 13px;
                color: #89b4fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 16px;
                color: #cdd6f4;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:pressed { background-color: #585b70; }
            QPushButton:disabled { background-color: #1e1e2e; color: #585b70; }
            QLineEdit, QSpinBox {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px 10px;
                color: #cdd6f4;
                font-size: 12px;
            }
            QListWidget {
                background-color: #181825;
                border: 1px solid #45475a;
                border-radius: 6px;
                font-size: 12px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #313244;
            }
            QListWidget::item:selected {
                background-color: #45475a;
            }
            QTextEdit {
                background-color: #181825;
                border: 1px solid #45475a;
                border-radius: 6px;
                font-family: Consolas, monospace;
                font-size: 11px;
                padding: 6px;
            }
            QLabel { font-size: 12px; }
        """)

        # 涓绘帶浠?        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # === 椤堕儴鎺у埗鏍?===
        top_frame = QFrame()
        top_frame.setStyleSheet("QFrame { background-color: #313244; border-radius: 8px; padding: 8px; }")
        top_layout = QHBoxLayout(top_frame)

        title_lbl = QLabel("馃摵 鎶栭煶鐩存挱闂寸洃鎺у櫒")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f38ba8; padding: 0 10px;")
        top_layout.addWidget(title_lbl)

        top_layout.addStretch()

        self.btn_add = QPushButton("鉃?娣诲姞鎴块棿")
        self.btn_add.setStyleSheet("background-color: #89b4fa; color: #1e1e2e; font-size: 13px; padding: 10px 20px;")
        self.btn_add.clicked.connect(self.add_room)
        top_layout.addWidget(self.btn_add)

        self.btn_remove = QPushButton("鉃?绉婚櫎")
        self.btn_remove.setStyleSheet("background-color: #fab387; color: #1e1e2e; font-size: 13px; padding: 10px 20px;")
        self.btn_remove.clicked.connect(self.remove_room)
        top_layout.addWidget(self.btn_remove)

        self.btn_start = QPushButton("鈻?寮€濮嬬洃鎺?)
        self.btn_start.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e; font-size: 13px; font-weight: bold; padding: 10px 24px;")
        self.btn_start.clicked.connect(self.toggle_monitor)
        top_layout.addWidget(self.btn_start)

        main_layout.addWidget(top_frame)

        # === 璁剧疆鏍?===
        setting_frame = QFrame()
        setting_frame.setStyleSheet("QFrame { background-color: #313244; border-radius: 8px; padding: 4px; }")
        setting_layout = QHBoxLayout(setting_frame)

        setting_layout.addWidget(QLabel("鍒锋柊闂撮殧:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(3, 300)
        self.spin_interval.setValue(self.config.get("refresh_interval", 10))
        self.spin_interval.setSuffix(" 绉?)
        self.spin_interval.valueChanged.connect(self.update_interval)
        setting_layout.addWidget(self.spin_interval)
        setting_layout.addSpacing(20)

        self.lbl_stats = QLabel("鐩戞帶涓? 0 | 鍦ㄧ嚎鐩存挱: 0 | 鎬诲湪绾? 0")
        self.lbl_stats.setStyleSheet("color: #94e2d5; font-weight: bold; font-size: 13px;")
        setting_layout.addWidget(self.lbl_stats)
        setting_layout.addStretch()

        btn_export = QPushButton("馃搵 瀵煎嚭鏃ュ織")
        btn_export.clicked.connect(self.export_log)
        setting_layout.addWidget(btn_export)

        btn_clear = QPushButton("馃棏 娓呯┖鏃ュ織")
        btn_clear.clicked.connect(self.clear_log)
        setting_layout.addWidget(btn_clear)

        main_layout.addWidget(setting_frame)

        # === 涓诲尯鍩熷垎鍓?===
        splitter = QSplitter(Qt.Horizontal)

        # 宸︿晶: 鏃ュ織
        log_group = QGroupBox("馃搳 鐩戞帶鏃ュ織")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        splitter.addWidget(log_group)

        # 鍙充晶: 鎴块棿鍒楄〃 + 璇︽儏
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        room_group = QGroupBox("馃彔 鐩戞帶鎴块棿鍒楄〃")
        room_layout = QVBoxLayout(room_group)
        self.room_list = QListWidget()
        self.room_list.setFont(QFont("Microsoft YaHei UI", 11))
        room_layout.addWidget(self.room_list)
        right_layout.addWidget(room_group)

        detail_group = QGroupBox("馃搵 鎴块棿璇︽儏")
        detail_layout = QGridLayout(detail_group)
        self.detail_labels = {}
        fields = [
            ("鐘舵€?, "status"), ("涓绘挱", "anchor"), ("鍦ㄧ嚎浜烘暟", "online"),
            ("宄板€间汉鏁?, "peak"), ("寮€鎾椂闂?, "start_time"), ("鐩存挱闂撮摼鎺?, "url")
        ]
        for i, (label, key) in enumerate(fields):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #a6adc8; font-weight: bold;")
            detail_layout.addWidget(lbl, i, 0)
            val = QLabel("--")
            val.setStyleSheet("color: #cdd6f4;")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if key == "url":
                val.setOpenExternalLinks(True)
            detail_layout.addWidget(val, i, 1)
            self.detail_labels[key] = val

        btn_open = QPushButton("馃敆 鎵撳紑鐩存挱闂?)
        btn_open.setStyleSheet("background-color: #cba6f7; color: #1e1e2e;")
        btn_open.clicked.connect(self.open_live_url)
        detail_layout.addWidget(btn_open, len(fields), 0, 1, 2)

        right_layout.addWidget(detail_group)
        splitter.addWidget(right_widget)

        splitter.setSizes([550, 500])
        main_layout.addWidget(splitter, stretch=1)

        # 鐘舵€佹爮
        self.statusBar().showMessage("灏辩华 | 娣诲姞鐩存挱闂碪RL寮€濮嬬洃鎺?)
        self.statusBar().setStyleSheet("color: #a6adc8; background-color: #181825; padding: 4px;")

        # 鎴块棿鐐瑰嚮
        self.room_list.currentRowChanged.connect(self.show_room_detail)

        # 瀹氭椂鍣?        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.tick_counter = 0

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray.setToolTip("鎶栭煶鐩存挱闂寸洃鎺у櫒")

        tray_menu = QMenu()
        show_action = QAction("鏄剧ず绐楀彛", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("閫€鍑?, self)
        quit_action.triggered.connect(self.quit_app)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray.setContextMenu(tray_menu)
        self.tray.show()

    # ==================== 鏃ュ織 ====================

    def log(self, msg, color=None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        if color:
            self.log_text.append(f'<span style="color: {color};">[{timestamp}] {msg}</span>')
        else:
            self.log_text.append(f'<span style="color: #cdd6f4;">[{timestamp}] {msg}</span>')
        self.log_text.scrollToBottom()

    def export_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "瀵煎嚭鏃ュ織", f"douyin_monitor_{datetime.now():%Y%m%d}.log", "鏃ュ織鏂囦欢 (*.log *.txt)")
        if path:
            plain = self.log_text.toPlainText()
            with open(path, "w", encoding="utf-8") as f:
                f.write(plain)
            self.log(f"鉁?鏃ュ織宸插鍑哄埌: {path}", "#a6e3a1")

    def clear_log(self):
        self.log_text.clear()

    # ==================== 鎴块棿绠＄悊 ====================

    def add_room(self):
        url, ok = QInputDialog.getText(
            self, "娣诲姞鐩戞帶鎴块棿",
            "璇疯緭鍏ユ姈闊崇洿鎾棿閾炬帴鎴栨埧闂碔D:\n\n绀轰緥:\n  https://live.douyin.com/123456789\n  https://v.douyin.com/xxxxx/\n  绮樿创鐩存挱闂村垎浜枃鏈?,
            QLineEdit.Normal, ""
        )
        if not ok or not url.strip():
            return

        room_id = extract_room_id(url.strip())
        live_url = build_live_url(room_id)

        if any(r.room_id == room_id for r in self.rooms):
            QMessageBox.information(self, "鎻愮ず", "璇ユ埧闂村凡鍦ㄧ洃鎺у垪琛ㄤ腑锛?)
            return

        room = RoomInfo(url=live_url, room_id=room_id)
        room.status_text = "宸叉坊鍔狅紝绛夊緟妫€娴?
        self.rooms.append(room)
        self.update_room_list()
        self.save_config()
        self.log(f"鉃?宸叉坊鍔犳埧闂? {live_url}", "#a6e3a1")
        self.statusBar().showMessage(f"宸叉坊鍔犳埧闂达紝褰撳墠鍏?{len(self.rooms)} 涓埧闂?)

    def remove_room(self):
        idx = self.room_list.currentRow()
        if idx < 0:
            QMessageBox.information(self, "鎻愮ず", "璇峰厛閫夋嫨瑕佺Щ闄ょ殑鎴块棿")
            return
        room = self.rooms[idx]
        self.rooms.pop(idx)
        self.update_room_list()
        self.save_config()
        self.log(f"鉃?宸茬Щ闄ゆ埧闂? {room.anchor_name} ({room.url})", "#fab387")

    def update_room_list(self):
        self.room_list.clear()
        for room in self.rooms:
            icon = "馃敶" if room.is_live else "鈿?
            count = f" [{room.online_count:,}浜篯" if room.is_live else ""
            item = QListWidgetItem(f"{icon} {room.anchor_name}{count}  鈥? {room.status_text}")

            if room.is_live:
                item.setForeground(QColor("#f38ba8"))
            else:
                item.setForeground(QColor("#6c7086"))

            self.room_list.addItem(item)

    def show_room_detail(self, idx):
        if idx < 0 or idx >= len(self.rooms):
            return
        room = self.rooms[idx]

        status = "馃敶 姝ｅ湪鐩存挱" if room.is_live else "鈿?鏈紑鎾?
        status_color = "#f38ba8" if room.is_live else "#6c7086"

        self.detail_labels["status"].setText(f'<span style="color: {status_color}; font-weight: bold;">{status}</span>')
        self.detail_labels["anchor"].setText(room.anchor_name)
        self.detail_labels["online"].setText(f"{room.online_count:,}浜? if room.is_live else "--")
        self.detail_labels["peak"].setText(f"{room.peak_count:,}浜? if room.peak_count > 0 else "--")
        self.detail_labels["start_time"].setText(
            room.live_start_time.strftime("%H:%M:%S") if room.live_start_time else "--"
        )
        self.detail_labels["url"].setText(
            f'<a href="{room.url}" style="color: #89b4fa;">{room.url}</a>'
        )

    def open_live_url(self):
        idx = self.room_list.currentRow()
        if idx >= 0 and idx < len(self.rooms):
            import webbrowser
            webbrowser.open(self.rooms[idx].url)

    # ==================== 鐩戞帶鎺у埗 ====================

    def toggle_monitor(self):
        if self.is_monitoring:
            self.stop_monitor()
        else:
            self.start_monitor()

    def start_monitor(self):
        if not self.rooms:
            QMessageBox.information(self, "鎻愮ず", "璇峰厛娣诲姞鑷冲皯涓€涓洃鎺ф埧闂达紒")
            return

        self.is_monitoring = True
        self.tick_counter = 0
        self.btn_start.setText("鈴?鏆傚仠鐩戞帶")
        self.btn_start.setStyleSheet("background-color: #f9e2af; color: #1e1e2e; font-size: 13px; font-weight: bold; padding: 10px 24px;")
        self.refresh_timer.start(1000)
        self.log("馃殌 鐩戞帶宸插惎鍔?, "#a6e3a1")
        self.statusBar().showMessage("鐩戞帶杩愯涓?..")

    def stop_monitor(self):
        self.is_monitoring = False
        self.refresh_timer.stop()
        self.btn_start.setText("鈻?寮€濮嬬洃鎺?)
        self.btn_start.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e; font-size: 13px; font-weight: bold; padding: 10px 24px;")

        for t in self.threads:
            t.quit()
            t.wait(1000)
        self.threads.clear()

        self.log("鈴?鐩戞帶宸插仠姝?, "#f38ba8")
        self.statusBar().showMessage("鐩戞帶宸插仠姝?)

    def refresh_all(self):
        self.tick_counter += 1
        if self.tick_counter < self.config.get("refresh_interval", 10):
            return
        self.tick_counter = 0

        if not self.rooms:
            return

        self.log(f"馃攧 寮€濮嬪埛鏂?{len(self.rooms)} 涓埧闂?..", "#89b4fa")
        self.statusBar().showMessage("姝ｅ湪鍒锋柊鏁版嵁...")

        # 鍚姩澶氱嚎绋嬪苟鍙戣姹?        for t in self.threads:
            t.quit()
            t.wait(1000)
        self.threads.clear()

        for room in self.rooms:
            t = MonitorThread(room)
            t.room_updated.connect(self.on_room_updated)
            t.room_error.connect(self.on_room_error)
            self.threads.append(t)
            t.start()

    def on_room_updated(self, data):
        room_id = data["room_id"]
        room = next((r for r in self.rooms if r.room_id == room_id), None)
        if not room:
            return

        was_live = room.was_live

        # 鏇存柊鏁版嵁
        room.anchor_name = data.get("anchor_name", room.anchor_name)
        room.cover_url = data.get("cover_url", "")
        room.is_live = data.get("is_live", False)
        room.online_count = data.get("online_count", 0)
        room.last_check = datetime.now()
        room.error_count = 0

        if room.online_count > room.peak_count:
            room.peak_count = room.online_count

        # 鐘舵€佸彉鍖栨娴?        if room.is_live and not was_live:
            room.live_start_time = datetime.now()
            room.status_text = "馃敶 姝ｅ湪鐩存挱"
            self.log(f"馃敶 銆愬紑鎾€憑room.anchor_name} 寮€濮嬬洿鎾紒鍦ㄧ嚎: {room.online_count:,}浜?, "#f38ba8")
            self.notify(f"馃敶 寮€鎾彁閱?, f"{room.anchor_name} 姝ｅ湪鐩存挱\n鍦ㄧ嚎: {room.online_count:,}浜?)
            self.tray.showMessage("馃敶 寮€鎾彁閱?, f"{room.anchor_name} 姝ｅ湪鐩存挱 | {room.online_count:,}浜?, QSystemTrayIcon.Information, 5000)

        elif not room.is_live and was_live:
            duration = "--"
            if room.live_start_time:
                delta = datetime.now() - room.live_start_time
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            room.status_text = "鈿?宸插叧鎾?
            self.log(f"鈿?銆愬叧鎾€憑room.anchor_name} 宸茬粨鏉熺洿鎾?(鏃堕暱: {duration}) | 宄板€? {room.peak_count:,}浜?, "#6c7086")
            self.tray.showMessage("鈿?鍏虫挱鎻愰啋", f"{room.anchor_name} 宸茬粨鏉熺洿鎾?, QSystemTrayIcon.Warning, 5000)
            room.peak_count = 0
            room.live_start_time = None
        else:
            room.status_text = f"馃敶 鐩存挱涓?| {room.online_count:,}浜? if room.is_live else "鈿?鏈紑鎾?

        room.was_live = room.is_live
        self.update_room_list()
        self.update_stats()

        # 鍒锋柊璇︽儏
        idx = self.room_list.currentRow()
        if idx >= 0:
            self.show_room_detail(idx)

    def on_room_error(self, room_id, error_msg):
        room = next((r for r in self.rooms if r.room_id == room_id), None)
        if room:
            room.error_count += 1
            room.status_text = f"鈿狅笍 {error_msg}"
            self.update_room_list()

    def update_stats(self):
        online = sum(1 for r in self.rooms if r.is_live)
        total = sum(r.online_count for r in self.rooms if r.is_live)
        self.lbl_stats.setText(
            f"鐩戞帶涓? {len(self.rooms)} | 鍦ㄧ嚎鐩存挱: {online} | 鎬诲湪绾? {total:,}浜?
        )

    def update_interval(self, val):
        self.config["refresh_interval"] = val
        self.save_config()

    def notify(self, title, message):
        """绯荤粺閫氱煡"""
        try:
            self.tray.showMessage(title, message, QSystemTrayIcon.Information, 5000)
        except Exception:
            pass

    # ==================== 閰嶇疆 ====================

    def load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return dict(DEFAULT_CONFIG)

    def save_config(self):
        self.config["rooms"] = [r.to_dict() for r in self.rooms]
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"鈿狅笍 淇濆瓨閰嶇疆澶辫触: {e}", "#fab387")

    def load_rooms_from_config(self):
        for r_data in self.config.get("rooms", []):
            room = RoomInfo(url=r_data.get("url", ""), room_id=r_data.get("room_id", ""))
            room.anchor_name = r_data.get("anchor_name", f"鎴块棿 {room.room_id}")
            room.status_text = "绛夊緟妫€娴?
            self.rooms.append(room)
        self.update_room_list()
        if self.rooms:
            self.log(f"馃搨 宸插姞杞?{len(self.rooms)} 涓埧闂撮厤缃?, "#89b4fa")

    def quit_app(self):
        self.stop_monitor()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("鎶栭煶鐩存挱闂寸洃鎺у櫒", "绋嬪簭宸叉渶灏忓寲鍒版墭鐩橈紝鍙抽敭閫€鍑?, QSystemTrayIcon.Information, 2000)


# ==================== 鍏ュ彛 ====================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 鏆楄壊涓婚璋冭壊鏉?    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 46))
    palette.setColor(QPalette.WindowText, QColor(205, 214, 244))
    palette.setColor(QPalette.Base, QColor(24, 24, 37))
    palette.setColor(QPalette.AlternateBase, QColor(49, 50, 68))
    palette.setColor(QPalette.ToolTipBase, QColor(49, 50, 68))
    palette.setColor(QPalette.ToolTipText, QColor(205, 214, 244))
    palette.setColor(QPalette.Text, QColor(205, 214, 244))
    palette.setColor(QPalette.Button, QColor(49, 50, 68))
    palette.setColor(QPalette.ButtonText, QColor(205, 214, 244))
    palette.setColor(QPalette.Highlight, QColor(137, 180, 250))
    palette.setColor(QPalette.HighlightedText, QColor(30, 30, 46))
    app.setPalette(palette)

    window = MonitorWindow()
    window.show()
    sys.exit(app.exec_())
