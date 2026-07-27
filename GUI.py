import sys
import time
import json
import numpy as np

from PyQt6.QtCore import Qt, QTimer, QByteArray, QSize
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QFrame, QTextEdit, QStackedWidget,
                             QPushButton, QLineEdit)
from PyQt6.QtGui import QColor, QPainter, QPen, QCursor, QTextCursor, QFont, QPainterPath, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWebEngineWidgets import QWebEngineView

# ייבוא מחלקת המנוע והאזנת ה-UDP מהקובץ הנפרד
from engine import NavigationSystem, start_udp_listener


# ==========================================
# 0. Design Tokens (visual-only, presentation layer)
# ==========================================
PALETTE = {
    "bg": "#0A0E14",       # app background
    "panel": "#10151F",    # cards / map frame
    "sidebar": "#0D1119",  # sidebar surface
    "bezel": "#080B10",    # instrument bezel (HUD)
    "border": "#1E2733",   # hairlines
    "text": "#E7ECF5",     # primary text
    "muted": "#6B7688",    # secondary / labels
    "accent": "#4C8DFF",   # selection / primary
    "success": "#34D399",  # locked / armed / connected
    "warning": "#FBBF24",  # degraded / caution
    "danger": "#F87171",   # offline / lost / jammed
}

MONO_STACK = ["sans-serif"]
UI_STACK = ["sans-serif"]


def mono_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Returns the shared monospace/tabular font used for all live telemetry digits."""
    font = QFont()
    font.setFamilies(MONO_STACK)
    font.setPointSize(size)
    font.setWeight(weight)
    return font


# ==========================================
# 0b. SVG Icon Utility
# ==========================================
def create_svg_icon(svg_xml: str, size: int = 24, color: str = "#64748B") -> QIcon:
    """יוצר QIcon וקטורי מתוך מחרוזת SVG עם התאמת צבע דינמית"""
    svg_data = svg_xml.replace('currentColor', color).encode('utf-8')
    renderer = QSvgRenderer(QByteArray(svg_data))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


SVG_ICONS = {
    "rocket": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-3.05 11a22.35 22.35 0 0 1-3.95 2z"/></svg>',
    "dashboard": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>',
    "telemetry": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>',
    "logs": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/></svg>',
    "user": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
}


# ==========================================
# 1. Advanced Flight HUD Widget
# ==========================================
class AdvancedFlightHUD(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 200)
        self.pitch = 0.0
        self.roll = 0.0
        self.yaw = 0.0
        self.speed = 0.0
        self.altitude = 0.0

    def set_telemetry(self, pitch, roll, yaw, speed, altitude=0.0):
        self.pitch = pitch
        self.roll = roll
        self.yaw = yaw
        self.speed = speed
        self.altitude = altitude
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        outer_path = QPainterPath()
        outer_path.addRoundedRect(0, 0, w, h, 14, 14)
        painter.setClipPath(outer_path)
        painter.fillRect(0, 0, w, h, QColor(PALETTE["bezel"]))

        cx = w / 2
        cy = h / 2 - 8
        hud_r = min(w, h) * 0.38

        # --- אופק מלאכותי ---
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self.roll)

        pitch_offset = self.pitch * 2.2
        sky_color = QColor("#2B5F9E")     # deep aviation-instrument blue
        ground_color = QColor("#7A4A24")  # muted earth tone

        clip_path = QPainterPath()
        clip_path.addEllipse(-hud_r, -hud_r, hud_r * 2, hud_r * 2)
        painter.setClipPath(clip_path)

        painter.fillRect(int(-hud_r * 1.5), int(-hud_r * 2 + pitch_offset), int(hud_r * 3), int(hud_r * 2), sky_color)
        painter.fillRect(int(-hud_r * 1.5), int(pitch_offset), int(hud_r * 3), int(hud_r * 2), ground_color)

        painter.setPen(QPen(QColor(PALETTE["text"]), 2))
        painter.drawLine(int(-hud_r), int(pitch_offset), int(hud_r), int(pitch_offset))

        painter.setPen(QPen(QColor(PALETTE["text"]), 1))
        painter.setFont(mono_font(8))

        for p in range(-60, 61, 15):
            if p == 0: continue
            y_pos = int(pitch_offset - (p * 2.2))
            bar_w = 18 if p % 30 == 0 else 10
            painter.drawLine(-bar_w, y_pos, bar_w, y_pos)
            if p % 30 == 0:
                painter.drawText(bar_w + 3, y_pos + 4, str(p))
                painter.drawText(-bar_w - 20, y_pos + 4, str(p))

        painter.restore()

        # כוונת מרכזית
        painter.setPen(QPen(QColor(PALETTE["warning"]), 3))
        painter.drawLine(int(cx - 25), int(cy), int(cx - 8), int(cy))
        painter.drawLine(int(cx + 8), int(cy), int(cx + 25), int(cy))
        painter.drawLine(int(cx), int(cy - 5), int(cx), int(cy + 10))

        # סרגל מהירות (Speed Tape)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(QPen(QColor(PALETTE["border"]), 1))
        painter.drawRoundedRect(10, 15, 44, int(h - 50), 8, 8)

        painter.setPen(QPen(QColor(PALETTE["accent"]), 1))
        painter.setFont(mono_font(8, QFont.Weight.Bold))
        painter.drawText(14, 30, "SPD")
        painter.setPen(QPen(QColor(PALETTE["text"]), 1))
        painter.setFont(mono_font(9))
        painter.drawText(14, 48, f"{self.speed:.1f}")

        # סרגל גובה (Altitude Tape)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(QPen(QColor(PALETTE["border"]), 1))
        painter.drawRoundedRect(int(w - 54), 15, 44, int(h - 50), 8, 8)

        painter.setPen(QPen(QColor(PALETTE["success"]), 1))
        painter.setFont(mono_font(8, QFont.Weight.Bold))
        painter.drawText(int(w - 50), 30, "ALT")
        painter.setPen(QPen(QColor(PALETTE["text"]), 1))
        painter.setFont(mono_font(9))
        painter.drawText(int(w - 50), 48, f"{self.altitude:.1f}m")

        # נתונים מספריים בתחתית
        painter.setPen(QPen(QColor(PALETTE["muted"]), 1))
        painter.setFont(mono_font(8, QFont.Weight.Medium))
        bot_y = int(h - 12)
        painter.drawText(12, bot_y, f"P: {self.pitch:+.1f}°")
        painter.drawText(int(cx - 24), bot_y, f"R: {self.roll:+.1f}°")
        painter.drawText(int(w - 70), bot_y, f"Y: {self.yaw:03.0f}°")


# ==========================================
# 2. Main Ground Control Station Window
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self, nav_system: NavigationSystem):
        super().__init__()
        self.nav = nav_system

        self.setWindowTitle("UAV Ground Control Station - Fullscreen Edition")
        self.resize(1550, 880)

        # פתיחה אוטומטית במסך מלא (Maximize)
        self.showMaximized()

        ui_family = ", ".join(f"'{f}'" for f in UI_STACK)
        mono_family = ", ".join(f"'{f}'" for f in MONO_STACK)

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {PALETTE["bg"]}; font-family: {ui_family}; }}
            QLabel {{ color: {PALETTE["text"]}; }}
            QFrame {{ border: none; }}
            QTextEdit {{ background-color: {PALETTE["bezel"]}; color: {PALETTE["accent"]}; font-family: {mono_family}; border: 1px solid {PALETTE["border"]}; padding: 12px; border-radius: 10px; }}
            QPushButton {{ font-family: {ui_family}; font-weight: 600; border-radius: 10px; padding: 8px 16px; }}
            QPushButton:hover {{ opacity: 0.9; }}
            QLineEdit {{ background: {PALETTE["panel"]}; border: 1px solid {PALETTE["border"]}; border-radius: 10px; padding: 8px 14px; color: {PALETTE["text"]}; font-size: 13px; }}
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---------------------------------------------------------
        # 1. LEFT SIDEBAR (72px)
        # ---------------------------------------------------------
        sidebar = QFrame()
        sidebar.setFixedWidth(72)
        sidebar.setStyleSheet(f"background-color: {PALETTE['sidebar']}; border-right: 1px solid {PALETTE['border']};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 24, 10, 24)
        sidebar_layout.setSpacing(16)

        logo_btn = QPushButton()
        logo_btn.setIcon(create_svg_icon(SVG_ICONS["rocket"], 26, PALETTE["accent"]))
        logo_btn.setIconSize(QSize(26, 26))
        logo_btn.setStyleSheet("background: transparent; border: none;")
        sidebar_layout.addWidget(logo_btn)

        sidebar_layout.addSpacing(15)

        self.sidebar_btns = []
        menus = [("dashboard", "Dashboard"), ("telemetry", "Raw Telemetry"), ("logs", "Mission Logs")]

        btn_style = f"""
            QPushButton {{ background: transparent; border-radius: 10px; border-left: 3px solid transparent; height: 48px; width: 48px; }}
            QPushButton:hover {{ background: {PALETTE["panel"]}; }}
            QPushButton:checked {{ background: rgba(76, 141, 255, 0.14); border-left: 3px solid {PALETTE["accent"]}; }}
        """

        for i, (icon_key, name) in enumerate(menus):
            btn = QPushButton()
            btn.setToolTip(name)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(btn_style)

            icon_normal = create_svg_icon(SVG_ICONS[icon_key], 22, PALETTE["muted"])
            icon_active = create_svg_icon(SVG_ICONS[icon_key], 22, PALETTE["accent"])
            btn.setIcon(icon_normal)
            btn.setIconSize(QSize(22, 22))

            btn.clicked.connect(lambda checked, idx=i, b=btn, ik=icon_key: self.switch_sidebar_view(idx, b, ik))
            self.sidebar_btns.append((btn, icon_normal, icon_active))
            sidebar_layout.addWidget(btn)

        self.sidebar_btns[0][0].setChecked(True)
        self.sidebar_btns[0][0].setIcon(self.sidebar_btns[0][2])

        sidebar_layout.addStretch()

        avatar_btn = QPushButton()
        avatar_btn.setIcon(create_svg_icon(SVG_ICONS["user"], 22, PALETTE["muted"]))
        avatar_btn.setIconSize(QSize(22, 22))
        avatar_btn.setStyleSheet(f"background: {PALETTE['panel']}; border-radius: 20px; height: 44px; width: 44px;")
        sidebar_layout.addWidget(avatar_btn)

        root_layout.addWidget(sidebar)

        # ---------------------------------------------------------
        # 2. CENTER INFORMATION PANEL (380px)
        # ---------------------------------------------------------
        center_panel = QFrame()
        center_panel.setFixedWidth(380)
        center_panel.setStyleSheet(f"background-color: {PALETTE['bg']};")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(20, 24, 20, 24)
        center_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        self.sys_title = QLabel("Dashboard")
        self.sys_title.setStyleSheet(f"font-size: 21px; font-weight: 800; color: {PALETTE['text']};")
        self.lbl_top_status = QLabel("OFFLINE")
        self.lbl_top_status.setStyleSheet(
            f"background: {PALETTE['danger']}; color: {PALETTE['bg']}; padding: 4px 12px; border-radius: 8px; font-weight: bold; font-size: 11px;")

        header_layout.addWidget(self.sys_title)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_top_status)
        center_layout.addLayout(header_layout)

        self.stacked_widget = QStackedWidget()

        # --- Page 0: Dashboard ---
        self.page_dashboard = QWidget()
        dash_layout = QVBoxLayout(self.page_dashboard)
        dash_layout.setContentsMargins(0, 0, 0, 0)
        dash_layout.setSpacing(16)

        card_pfd = self.create_card()
        pfd_layout = QVBoxLayout(card_pfd)
        row_telemetry = QHBoxLayout()

        vbox_speed = QVBoxLayout()
        self.lbl_speed_val = QLabel("0.0")
        self.lbl_speed_val.setFont(mono_font(26, QFont.Weight.Black))
        self.lbl_speed_val.setStyleSheet(f"color: {PALETTE['accent']};")
        lbl_speed_title = QLabel("SPEED (KM/H)")
        lbl_speed_title.setStyleSheet(f"color: {PALETTE['muted']}; font-weight: 700; font-size: 10px;")
        vbox_speed.addWidget(self.lbl_speed_val)
        vbox_speed.addWidget(lbl_speed_title)

        vbox_hdg = QVBoxLayout()
        self.lbl_hdg_val = QLabel("0°")
        self.lbl_hdg_val.setFont(mono_font(26, QFont.Weight.Black))
        self.lbl_hdg_val.setStyleSheet(f"color: {PALETTE['text']};")
        lbl_hdg_title = QLabel("HEADING")
        lbl_hdg_title.setStyleSheet(f"color: {PALETTE['muted']}; font-weight: 700; font-size: 10px;")
        vbox_hdg.addWidget(self.lbl_hdg_val)
        vbox_hdg.addWidget(lbl_hdg_title)

        row_telemetry.addLayout(vbox_speed)
        row_telemetry.addStretch()
        row_telemetry.addLayout(vbox_hdg)

        pfd_layout.addLayout(row_telemetry)
        pfd_layout.addSpacing(10)

        self.horizon = AdvancedFlightHUD()
        pfd_layout.addWidget(self.horizon)
        dash_layout.addWidget(card_pfd)

        card_health = self.create_card()
        health_layout = QVBoxLayout(card_health)
        lbl_health_title = QLabel("SYSTEM HEALTH")
        lbl_health_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {PALETTE['text']};")
        health_layout.addWidget(lbl_health_title)
        health_layout.addSpacing(8)

        self.ind_link = self.create_status_row("Datalink (UDP)", health_layout)
        self.ind_gps = self.create_status_row("GPS Lock", health_layout)
        self.ind_ekf = self.create_status_row("EKF Filter", health_layout)

        health_layout.addSpacing(12)

        self.lbl_hdop = self.create_stat_row("HDOP", "--", health_layout)
        self.lbl_pkts = self.create_stat_row("Packets", "0 Hz", health_layout)
        self.lbl_latency = self.create_stat_row("Latency", "-- ms", health_layout)
        dash_layout.addWidget(card_health)
        dash_layout.addStretch()

        # --- Page 1: Raw Telemetry ---
        self.page_raw = QWidget()
        raw_layout = QVBoxLayout(self.page_raw)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        card_raw = self.create_card()
        card_raw_layout = QVBoxLayout(card_raw)
        lbl_raw_title = QLabel("RAW GPS & IMU DATA")
        lbl_raw_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {PALETTE['text']};")
        self.tab_raw = QTextEdit()
        self.tab_raw.setReadOnly(True)
        card_raw_layout.addWidget(lbl_raw_title)
        card_raw_layout.addWidget(self.tab_raw)
        raw_layout.addWidget(card_raw)

        # --- Page 2: Logs ---
        self.page_logs = QWidget()
        logs_layout = QVBoxLayout(self.page_logs)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        card_events = self.create_card()
        events_layout = QVBoxLayout(card_events)
        lbl_events_title = QLabel("MISSION EVENTS LOG")
        lbl_events_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {PALETTE['text']};")
        self.tab_events = QTextEdit()
        self.tab_events.setReadOnly(True)
        self.tab_events.setStyleSheet(
            f"background-color: {PALETTE['bezel']}; color: {PALETTE['success']}; font-family: {mono_family}; border: 1px solid {PALETTE['border']}; border-radius: 10px;")
        events_layout.addWidget(lbl_events_title)
        events_layout.addWidget(self.tab_events)
        logs_layout.addWidget(card_events)

        self.stacked_widget.addWidget(self.page_dashboard)
        self.stacked_widget.addWidget(self.page_raw)
        self.stacked_widget.addWidget(self.page_logs)

        center_layout.addWidget(self.stacked_widget)
        root_layout.addWidget(center_panel)

        # ---------------------------------------------------------
        # 3. RIGHT MAP AREA
        # ---------------------------------------------------------
        map_area = QWidget()
        map_layout = QVBoxLayout(map_area)
        map_layout.setContentsMargins(10, 24, 24, 24)
        map_layout.setSpacing(16)

        toolbar_layout = QHBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search locations or press Enter...")
        self.search_box.setFixedWidth(250)
        self.search_box.returnPressed.connect(self.on_search_pressed)

        btn_new_mission = QPushButton("New Mission")
        btn_new_mission.setStyleSheet(f"background: {PALETTE['accent']}; color: {PALETTE['bg']}; border: none;")
        btn_new_mission.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_new_mission.clicked.connect(lambda: self.nav.log_event("UI", "New Mission created"))

        btn_export = QPushButton("Export")
        btn_export.setStyleSheet(f"background: {PALETTE['panel']}; color: {PALETTE['text']}; border: 1px solid {PALETTE['border']};")
        btn_export.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_export.clicked.connect(lambda: self.nav.log_event("UI", "Telemetry Export Triggered"))

        self.pulse_indicator = QLabel("● LIVE")
        self.pulse_indicator.setStyleSheet(f"color: {PALETTE['muted']}; font-weight: 900; font-size: 14px;")

        toolbar_layout.addWidget(self.search_box)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.pulse_indicator)
        toolbar_layout.addSpacing(16)
        toolbar_layout.addWidget(btn_export)
        toolbar_layout.addWidget(btn_new_mission)

        map_layout.addLayout(toolbar_layout)

        map_frame = self.create_card()
        map_frame.setStyleSheet(f"background: {PALETTE['bezel']}; border-radius: 14px; border: 1px solid {PALETTE['border']};")
        map_frame_layout = QVBoxLayout(map_frame)
        map_frame_layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(QColor(PALETTE["bezel"]))
        self.web_view.setStyleSheet("border-radius: 14px;")
        map_frame_layout.addWidget(self.web_view)

        map_layout.addWidget(map_frame)
        root_layout.addWidget(map_area)

        # INIT MAP & TIMERS
        self.map_ready = False
        self.web_view.loadFinished.connect(self.on_map_loaded)
        self.setup_base_map(32.0853, 34.7818)

        self.pulse_state = False
        self.last_handled_events = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)

    def switch_sidebar_view(self, index, active_btn, icon_key):
        for btn, normal_icon, active_icon in self.sidebar_btns:
            if btn == active_btn:
                btn.setChecked(True)
                btn.setIcon(active_icon)
            else:
                btn.setChecked(False)
                btn.setIcon(normal_icon)

        self.stacked_widget.setCurrentIndex(index)
        titles = ["Dashboard", "Raw Telemetry", "Mission Logs"]
        self.sys_title.setText(titles[index])

    def on_search_pressed(self):
        txt = self.search_box.text()
        if txt:
            self.nav.log_event("UI", f"Searched for: {txt}")
            self.search_box.clear()

    def create_card(self):
        card = QFrame()
        card.setStyleSheet(f"background-color: {PALETTE['panel']}; border-radius: 14px; border: 1px solid {PALETTE['border']};")
        return card

    def create_status_row(self, text, parent_layout):
        row = QHBoxLayout()
        lbl_text = QLabel(text)
        lbl_text.setStyleSheet(f"color: {PALETTE['muted']}; font-weight: 600; font-size: 13px;")
        indicator = QLabel()
        indicator.setFixedSize(12, 12)
        indicator.setStyleSheet(f"background-color: {PALETTE['danger']}; border-radius: 6px;")
        row.addWidget(lbl_text)
        row.addStretch()
        row.addWidget(indicator)
        parent_layout.addLayout(row)
        return indicator

    def create_stat_row(self, title, val, parent_layout):
        row = QHBoxLayout()
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 13px;")
        lbl_v = QLabel(val)
        lbl_v.setFont(mono_font(13, QFont.Weight.Bold))
        lbl_v.setStyleSheet(f"color: {PALETTE['text']};")
        row.addWidget(lbl_t)
        row.addStretch()
        row.addWidget(lbl_v)
        parent_layout.addLayout(row)
        return lbl_v

    def setup_base_map(self, center_lat, center_lon):
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"/>
            <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
            <style>
                html, body, #map {{ height: 100%; margin: 0; padding: 0; background-color: {PALETTE["bezel"]}; font-family: sans-serif; border-radius: 14px; }}
                .leaflet-control-layers {{ border-radius: 10px !important; background: {PALETTE["panel"]} !important; color: {PALETTE["text"]} !important; border: 1px solid {PALETTE["border"]} !important; }}
                .leaflet-control-layers-toggle {{ filter: invert(1); }}
                .leaflet-control-zoom a {{ background: {PALETTE["panel"]} !important; color: {PALETTE["text"]} !important; border-color: {PALETTE["border"]} !important; }}
                .leaflet-control-scale-line {{ background: rgba(16, 21, 31, 0.85) !important; color: {PALETTE["text"]} !important; border-color: {PALETTE["border"]} !important; }}
                .drone-icon {{ background: transparent; border: none; overflow: visible; }}

                .map-legend {{
                    position: absolute; bottom: 30px; left: 20px; z-index: 1000;
                    background: rgba(10, 14, 20, 0.9); border: 1px solid {PALETTE["border"]};
                    border-radius: 12px; padding: 12px 16px; color: {PALETTE["text"]}; font-size: 12px;
                    display: flex; flex-direction: column; gap: 8px;
                }}
                .legend-item {{ display: flex; align-items: center; gap: 10px; font-weight: 600; }}
                .legend-line-ekf {{ width: 20px; height: 4px; background: {PALETTE["accent"]}; border-radius: 2px; }}
                .legend-line-raw {{ width: 20px; height: 0px; border-top: 3px dashed {PALETTE["danger"]}; }}
                .nav-mode-badge {{ font-size: 10px; font-weight: bold; padding: 3px 8px; border-radius: 8px; text-transform: uppercase; margin-top: 2px; text-align: center; }}

                .map-fab-container {{
                    position: absolute; top: 30px; right: 20px; z-index: 1000;
                    display: flex; flex-direction: column; gap: 10px;
                }}
                .map-fab {{
                    background: rgba(10, 14, 20, 0.9); color: {PALETTE["text"]}; border: 1px solid {PALETTE["border"]}; border-radius: 10px;
                    width: 44px; height: 44px; font-weight: bold; cursor: pointer;
                    transition: 0.2s; font-size: 18px;
                    display: flex; align-items: center; justify-content: center;
                }}
                .map-fab:hover {{ background: {PALETTE["panel"]}; }}
            </style>
        </head>
        <body>
            <div id="map"></div>

            <div class="map-legend">
                <div class="legend-item">
                    <div class="legend-line-ekf"></div>
                    <span>EKF Trajectory (Filter)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-line-raw"></div>
                    <span>Raw GPS Trajectory</span>
                </div>
                <div id="navModeBadge" class="nav-mode-badge" style="background: rgba(52, 211, 153, 0.18); color: {PALETTE["success"]};">
                    GPS LOCK ACTIVE
                </div>
            </div>

            <div class="map-fab-container">
                <button class="map-fab" onclick="recenterMap()" title="Center UAV">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/>
                    </svg>
                </button>
                <button class="map-fab" onclick="goHome()" title="Go to Home;">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
                    </svg>
                </button>
            </div>
            <script>
                var tileOptions = {{ maxZoom: 20, updateWhenIdle: false, keepBuffer: 4, crossOrigin: true }};
                var darkLayer = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', tileOptions);
                var satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', tileOptions);
                var osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', tileOptions);

                var map = L.map('map', {{ center: [{center_lat}, {center_lon}], zoom: 18, layers: [darkLayer], zoomControl: false }});
                L.control.zoom({{position: 'bottomright'}}).addTo(map);
                L.control.scale({{imperial: false, metric: true, position: 'bottomleft'}}).addTo(map);
                L.control.layers({{ "DARK": darkLayer, "SATELLITE": satelliteLayer, "STREET MAP": osmLayer }}, null, {{position: 'topleft'}}).addTo(map);

                var ekfPath = L.polyline([], {{color: '{PALETTE["accent"]}', weight: 4, opacity: 0.9}}).addTo(map);
                var rawGpsPath = L.polyline([], {{color: '{PALETTE["danger"]}', weight: 3, opacity: 0.7, dashArray: '5, 8'}}).addTo(map);

                var accuracyCircle = L.circle([{center_lat}, {center_lon}], {{radius: 0, color: 'rgba(76, 141, 255, 0.4)', fillOpacity: 0.1, weight: 1}}).addTo(map);

                var homeMarker = null;
                var dronePos = [{center_lat}, {center_lon}];
                var homePos = null;
                var autoPan = true;

                function getDroneSVG(heading) {{
                    return L.divIcon({{
                        className: 'drone-icon',
                        html: `<div style="transform: rotate(${{heading}}deg); transform-origin: 50% 70%; width: 100px; height: 100px; margin-left: -50px; margin-top: -70px;">
                                 <polygon points="50,70 10,0 90,0" fill="url(#grad)" opacity="0.4"/>
                                 <svg width="0" height="0">
                                    <defs>
                                      <linearGradient id="grad" x1="0%" y1="100%" x2="0%" y2="0%">
                                        <stop offset="0%" style="stop-color:{PALETTE["accent"]};stop-opacity:1" />
                                        <stop offset="100%" style="stop-color:{PALETTE["accent"]};stop-opacity:0" />
                                      </linearGradient>
                                    </defs>
                                 </svg>
                                 <svg viewBox="0 0 24 24" width="36" height="36" style="position:absolute; top:52px; left:32px;">
                                    <path d="M12,2L4.5,20.3L5.2,21L12,18L18.8,21L19.5,20.3L12,2z" fill="{PALETTE["accent"]}" stroke="{PALETTE["text"]}" stroke-width="1"/>
                                 </svg>
                               </div>`,
                        iconSize: [0, 0]
                    }});
                }}

                var droneMarker = L.marker([{center_lat}, {center_lon}], {{ icon: getDroneSVG(0), zIndexOffset: 1000}}).addTo(map);

                map.on('dragstart', function() {{ autoPan = false; }});

                function recenterMap() {{ autoPan = true; map.panTo(dronePos, {{animate: true}}); }}
                function goHome() {{ if(homePos) map.panTo(homePos, {{animate: true}}); autoPan = false; }}

                function updateMapData(ekfCoords, rawCoords, heading, hdop, homeLat, homeLon, gpsValid) {{
                    if (ekfCoords.length === 0) return;

                    ekfPath.setLatLngs(ekfCoords);
                    if (rawCoords.length > 0) {{
                        rawGpsPath.setLatLngs(rawCoords);
                    }}

                    dronePos = ekfCoords[ekfCoords.length - 1];

                    droneMarker.setLatLng(dronePos);
                    droneMarker.setIcon(getDroneSVG(heading));

                    accuracyCircle.setLatLng(dronePos);
                    accuracyCircle.setRadius(hdop * 3.0);

                    var badge = document.getElementById('navModeBadge');
                    if (gpsValid) {{
                        badge.innerText = 'GPS LOCK ACTIVE';
                        badge.style.background = 'rgba(52, 211, 153, 0.18)';
                        badge.style.color = '{PALETTE["success"]}';
                        accuracyCircle.setStyle({{color: 'rgba(76, 141, 255, 0.4)', fillColor: '{PALETTE["accent"]}'}});
                    }} else {{
                        badge.innerText = '⚠ DEAD RECKONING / JAMMED';
                        badge.style.background = 'rgba(248, 113, 113, 0.18)';
                        badge.style.color = '{PALETTE["danger"]}';
                        accuracyCircle.setStyle({{color: '{PALETTE["danger"]}', fillColor: '{PALETTE["danger"]}'}});
                    }}

                    if (homeLat !== null && homeLon !== null && homeMarker === null) {{
                        homePos = [homeLat, homeLon];
                        var hIcon = L.divIcon({{
                            html: `<div style="background: #000000; width: 32px; height: 32px; border-radius: 10px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3); border: 2px solid #FFFFFF;">
                                     <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#FFFFFF" stroke-width="2.5">
                                        <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
                                     </svg>
                                   </div>`,
                            className: '', 
                            iconSize: [15, 15], 
                            iconAnchor: [10, 10]
                        }});
                        homeMarker = L.marker(homePos, {{icon: hIcon}}).addTo(map);
                    }}

                    if (autoPan) {{
                        var dist = map.distance(map.getCenter(), dronePos);
                        if (dist > 2000) map.setView(dronePos, 18, {{animate: false}});
                        else map.panTo(dronePos, {{animate: true, duration: 0.5}});
                    }}
                }}
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)

    def on_map_loaded(self, success):
        if success:
            self.map_ready = True
            self.timer.start(100)

    def update_gui(self):
        with self.nav.lock:
            dt_packet = time.time() - self.nav.last_packet_time
            is_active = (dt_packet < 2.0) and self.nav.udp_connected

            speed = self.nav.current_speed if not np.isnan(self.nav.current_speed) else 0.0
            heading = self.nav.yaw if not np.isnan(self.nav.yaw) else 0.0
            pitch = self.nav.pitch if not np.isnan(self.nav.pitch) else 0.0
            roll = self.nav.roll if not np.isnan(self.nav.roll) else 0.0
            hdop = self.nav.hdop if not np.isnan(self.nav.hdop) else 99.9

            gps_valid = self.nav.gps_valid
            status = self.nav.system_status
            home_l = self.nav.home_lat
            home_lon = self.nav.home_lon

            now = time.time()
            dt_start = now - self.nav.start_time
            pkts_sec = self.nav.packet_count / dt_start if dt_start > 0 else 0

            if len(self.nav.events) > self.last_handled_events:
                new_events = self.nav.events[self.last_handled_events:]
                for e in new_events:
                    self.tab_events.append(e)
                self.tab_events.moveCursor(QTextCursor.MoveOperation.End)
                self.last_handled_events = len(self.nav.events)

            if self.nav.raw_gps_coords:
                raw_str = (f"=== RAW SENSOR DATA ===\n"
                           f"Latitude:   {self.nav.raw_gps_coords[-1][0]:.7f}\n"
                           f"Longitude:  {self.nav.raw_gps_coords[-1][1]:.7f}\n"
                           f"Pitch:      {pitch:.2f}°\n"
                           f"Roll:       {roll:.2f}°\n"
                           f"Yaw/Hdg:    {heading:.2f}°\n"
                           f"Speed:      {speed:.2f} km/h\n"
                           f"HDOP:       {hdop:.2f}\n"
                           f"Valid GPS:  {gps_valid}\n"
                           f"Total Pkts: {self.nav.packet_count}\n"
                           f"Uptime:     {dt_start:.1f}s")
            else:
                raw_str = "Waiting for telemetry link..."

            self.tab_raw.setText(raw_str)

        # Connection Pulse & Status
        if is_active:
            self.pulse_state = not self.pulse_state
            color = PALETTE["success"] if self.pulse_state else PALETTE["muted"]
            self.pulse_indicator.setStyleSheet(f"color: {color}; font-weight: 900; font-size: 14px;")
            self.lbl_top_status.setText(f"{status}")
            self.lbl_top_status.setStyleSheet(
                f"background: {PALETTE['success']}; color: {PALETTE['bg']}; padding: 4px 12px; border-radius: 8px; font-weight: bold; font-size: 11px;")
            self.ind_link.setStyleSheet(f"background-color: {PALETTE['success']}; border-radius: 6px;")
        else:
            self.pulse_indicator.setStyleSheet(f"color: {PALETTE['muted']}; font-weight: 900; font-size: 14px;")
            self.lbl_top_status.setText("OFFLINE")
            self.lbl_top_status.setStyleSheet(
                f"background: {PALETTE['danger']}; color: {PALETTE['bg']}; padding: 4px 12px; border-radius: 8px; font-weight: bold; font-size: 11px;")
            self.ind_link.setStyleSheet(f"background-color: {PALETTE['danger']}; border-radius: 6px;")

        # PFD Telemetry Header & HUD Update
        self.lbl_speed_val.setText(f"{speed:.1f}")
        self.lbl_hdg_val.setText(f"{heading:0.0f}°")

        self.horizon.set_telemetry(pitch, roll, heading, speed, altitude=0.0)

        # Health Indicators
        self.ind_gps.setStyleSheet(
            f"background-color: {PALETTE['success']}; border-radius: 6px;" if gps_valid else f"background-color: {PALETTE['danger']}; border-radius: 6px;")
        self.ind_ekf.setStyleSheet(
            f"background-color: {PALETTE['success']}; border-radius: 6px;" if status == "ARMED" else f"background-color: {PALETTE['warning']}; border-radius: 6px;")

        # Stats
        self.lbl_hdop.setText(f"{hdop:.2f}")
        self.lbl_pkts.setText(f"{pkts_sec:.1f} Hz")
        self.lbl_latency.setText(f"{dt_packet * 1000:.0f} ms" if is_active else "-- ms")

        # MAP UPDATE
        if self.map_ready and is_active:
            ekf_c = [[c[0], c[1]] for c in self.nav.ekf_coords if not np.isnan(c[0])]
            raw_c = [[c[0], c[1]] for c in self.nav.raw_gps_coords if not np.isnan(c[0])]

            h_lat_str = str(home_l) if home_l is not None else "null"
            h_lon_str = str(home_lon) if home_lon is not None else "null"
            gps_val_str = "true" if gps_valid else "false"

            ekf_json = json.dumps(ekf_c)
            raw_json = json.dumps(raw_c)

            js_cmd = f"updateMapData({ekf_json}, {raw_json}, {heading:.1f}, {hdop:.2f}, {h_lat_str}, {h_lon_str}, {gps_val_str});"
            self.web_view.page().runJavaScript(js_cmd)


# ==========================================
# Main Entry Point
# ==========================================
if __name__ == '__main__':
    nav = NavigationSystem()
    start_udp_listener(nav, port=4210)

    app = QApplication(sys.argv)
    window = MainWindow(nav)
    window.show()
    sys.exit(app.exec())