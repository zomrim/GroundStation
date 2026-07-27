import sys
import time
import json
import numpy as np

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QFrame, QTextEdit, QStackedWidget,
                             QPushButton, QLineEdit)
from PyQt6.QtGui import QColor, QPainter, QPen, QCursor, QTextCursor
from PyQt6.QtWebEngineWidgets import QWebEngineView

# ייבוא מחלקת המנוע והאזנת ה-UDP מהקובץ הנפרד
from engine import NavigationSystem, start_udp_listener


# ==========================================
# 1. Custom Artificial Horizon Widget
# ==========================================
class AttitudeIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.pitch = 0.0
        self.roll = 0.0

    def set_attitude(self, pitch, roll):
        self.pitch = pitch
        self.roll = roll
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        painter.setClipRect(0, 0, w, h)
        painter.setBrush(QColor("#1e293b"))
        painter.drawRoundedRect(0, 0, w, h, 12, 12)

        painter.translate(w / 2, h / 2)
        painter.rotate(-self.roll)

        pitch_offset = self.pitch * 2.5

        sky_color = QColor("#2F80ED")
        ground_color = QColor("#854d0e")

        painter.fillRect(-w, int(-h * 1.5 + pitch_offset), w * 2, int(h * 1.5), sky_color)
        painter.fillRect(-w, int(pitch_offset), w * 2, int(h * 1.5), ground_color)

        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawLine(-w, int(pitch_offset), w, int(pitch_offset))

        painter.setPen(QPen(QColor("#ffffff"), 1))
        for p in range(-60, 61, 15):
            if p == 0: continue
            y_pos = int(pitch_offset - (p * 2.5))
            width = 30 if p % 30 == 0 else 15
            painter.drawLine(-width, y_pos, width, y_pos)
            if p % 30 == 0:
                painter.drawText(width + 5, y_pos + 4, str(p))
                painter.drawText(-width - 25, y_pos + 4, str(p))

        painter.resetTransform()
        painter.translate(w / 2, h / 2)

        painter.setPen(QPen(QColor("#F2C94C"), 3))
        painter.drawLine(-40, 0, -15, 0)
        painter.drawLine(15, 0, 40, 0)
        painter.drawLine(0, 0, 0, 15)
        painter.drawPoint(0, 0)

        painter.resetTransform()
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawArc(10, 10, w - 20, h - 20, 30 * 16, 120 * 16)


# ==========================================
# 2. Professional High-Performance GCS UI
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self, nav_system: NavigationSystem):
        super().__init__()
        self.nav = nav_system

        self.setWindowTitle("UAV Command & Control - Ultra Fast GCS")
        self.resize(1600, 900)

        self.setStyleSheet("""
            QMainWindow { background-color: #F8FAFC; font-family: 'Inter', -apple-system, sans-serif; }
            QLabel { color: #0F172A; }
            QFrame { border: none; }
            QTextEdit { background-color: #0F172A; color: #38BDF8; font-family: 'Consolas', monospace; border: none; padding: 10px; border-radius: 8px;}
            QPushButton { font-family: 'Inter', sans-serif; font-weight: bold; border-radius: 10px; padding: 8px 16px; }
            QPushButton:hover { opacity: 0.9; }
            QLineEdit { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 8px 12px; color: #0F172A; }
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
        sidebar.setStyleSheet("background-color: #FFFFFF; border-right: 1px solid #E2E8F0;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 24, 10, 24)
        sidebar_layout.setSpacing(20)

        logo_label = QLabel("🚀")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("font-size: 26px; margin-bottom: 15px;")
        sidebar_layout.addWidget(logo_label)

        btn_style = """
            QPushButton { background: transparent; color: #64748B; font-size: 20px; border-radius: 12px; height: 48px; width: 48px;}
            QPushButton:hover { background: #F1F5F9; color: #2F80ED; }
            QPushButton:checked { background: #2F80ED; color: #FFFFFF; }
        """

        self.sidebar_btns = []
        menus = [("🌍", "Dashboard"), ("📊", "Raw Data"), ("📝", "Logs")]

        for i, (icon, name) in enumerate(menus):
            btn = QPushButton(icon)
            btn.setToolTip(name)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda checked, idx=i: self.switch_sidebar_view(idx))
            self.sidebar_btns.append(btn)
            sidebar_layout.addWidget(btn)

        self.sidebar_btns[0].setChecked(True)
        sidebar_layout.addStretch()

        avatar = QLabel("👤")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("font-size: 22px; background: #F1F5F9; border-radius: 24px; height: 48px; width: 48px;")
        sidebar_layout.addWidget(avatar)
        root_layout.addWidget(sidebar)

        # ---------------------------------------------------------
        # 2. CENTER INFORMATION PANEL (380px)
        # ---------------------------------------------------------
        center_panel = QFrame()
        center_panel.setFixedWidth(380)
        center_panel.setStyleSheet("background-color: #F8FAFC;")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(20, 24, 20, 24)
        center_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        self.sys_title = QLabel("Dashboard")
        self.sys_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")
        self.lbl_top_status = QLabel("OFFLINE")
        self.lbl_top_status.setStyleSheet("background: #EF4444; color: white; padding: 4px 12px; border-radius: 10px; font-weight: bold; font-size: 12px;")

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
        self.lbl_speed_val.setStyleSheet("font-size: 36px; font-weight: 900; color: #2F80ED;")
        lbl_speed_title = QLabel("Speed (km/h)")
        lbl_speed_title.setStyleSheet("color: #64748B; font-weight: 600; font-size: 12px;")
        vbox_speed.addWidget(self.lbl_speed_val)
        vbox_speed.addWidget(lbl_speed_title)

        vbox_hdg = QVBoxLayout()
        self.lbl_hdg_val = QLabel("000°")
        self.lbl_hdg_val.setStyleSheet("font-size: 36px; font-weight: 900; color: #0F172A;")
        lbl_hdg_title = QLabel("Heading")
        lbl_hdg_title.setStyleSheet("color: #64748B; font-weight: 600; font-size: 12px;")
        vbox_hdg.addWidget(self.lbl_hdg_val)
        vbox_hdg.addWidget(lbl_hdg_title)

        row_telemetry.addLayout(vbox_speed)
        row_telemetry.addStretch()
        row_telemetry.addLayout(vbox_hdg)

        pfd_layout.addLayout(row_telemetry)
        pfd_layout.addSpacing(15)
        self.horizon = AttitudeIndicator()
        pfd_layout.addWidget(self.horizon)
        dash_layout.addWidget(card_pfd)

        card_health = self.create_card()
        health_layout = QVBoxLayout(card_health)
        lbl_health_title = QLabel("System Health")
        lbl_health_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #0F172A;")
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
        lbl_raw_title = QLabel("Raw GPS & IMU Data")
        lbl_raw_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #0F172A;")
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
        lbl_events_title = QLabel("Mission Events Log")
        lbl_events_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #0F172A;")
        self.tab_events = QTextEdit()
        self.tab_events.setReadOnly(True)
        self.tab_events.setStyleSheet("background-color: #0F172A; color: #10B981; font-family: 'Consolas', monospace; border-radius: 8px;")
        events_layout.addWidget(lbl_events_title)
        events_layout.addWidget(self.tab_events)
        logs_layout.addWidget(card_events)

        self.stacked_widget.addWidget(self.page_dashboard)
        self.stacked_widget.addWidget(self.page_raw)
        self.stacked_widget.addWidget(self.page_logs)

        center_layout.addWidget(self.stacked_widget)
        root_layout.addWidget(center_panel)

        # ---------------------------------------------------------
        # 3. RIGHT MAP AREA (Flexible Width)
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
        btn_new_mission.setStyleSheet("background: #2F80ED; color: white; border: none;")
        btn_new_mission.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_new_mission.clicked.connect(lambda: self.nav.log_event("UI", "New Mission created"))

        btn_export = QPushButton("Export")
        btn_export.setStyleSheet("background: #FFFFFF; color: #0F172A; border: 1px solid #E2E8F0;")
        btn_export.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_export.clicked.connect(lambda: self.nav.log_event("UI", "Telemetry Export Triggered"))

        self.pulse_indicator = QLabel("● LIVE")
        self.pulse_indicator.setStyleSheet("color: #64748B; font-weight: 900; font-size: 14px;")

        toolbar_layout.addWidget(self.search_box)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.pulse_indicator)
        toolbar_layout.addSpacing(16)
        toolbar_layout.addWidget(btn_export)
        toolbar_layout.addWidget(btn_new_mission)

        map_layout.addLayout(toolbar_layout)

        map_frame = self.create_card()
        map_frame.setStyleSheet("background: #0F172A; border-radius: 16px; border: 1px solid #E2E8F0;")
        map_frame_layout = QVBoxLayout(map_frame)
        map_frame_layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(QColor("#0F172A"))
        self.web_view.setStyleSheet("border-radius: 16px;")
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

    def switch_sidebar_view(self, index):
        for i, btn in enumerate(self.sidebar_btns):
            btn.setChecked(i == index)
        self.stacked_widget.setCurrentIndex(index)
        titles = ["Dashboard", "Raw Telemetry", "Mission Logs"]
        self.sys_title.setText(titles[index])

    def on_search_pressed(self):
        txt = self.search_box.text()
        if txt:
            self.nav.log_event("UI", f"Searched for: {txt}")
            self.search_box.clear()

    def create_card(self):
        """כרטיסייה מודרנית עם מסגרת עדינה (ללא QGraphicsDropShadowEffect שהאיר את ה-CPU)"""
        card = QFrame()
        card.setStyleSheet("background-color: #FFFFFF; border-radius: 16px; border: 1px solid #E2E8F0;")
        return card

    def create_status_row(self, text, parent_layout):
        row = QHBoxLayout()
        lbl_text = QLabel(text)
        lbl_text.setStyleSheet("color: #64748B; font-weight: 600; font-size: 13px;")
        indicator = QLabel()
        indicator.setFixedSize(12, 12)
        indicator.setStyleSheet("background-color: #EF4444; border-radius: 6px;")
        row.addWidget(lbl_text)
        row.addStretch()
        row.addWidget(indicator)
        parent_layout.addLayout(row)
        return indicator

    def create_stat_row(self, title, val, parent_layout):
        row = QHBoxLayout()
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #64748B; font-size: 13px;")
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet("font-weight: bold; color: #0F172A; font-size: 13px;")
        row.addWidget(lbl_t)
        row.addStretch()
        row.addWidget(lbl_v)
        parent_layout.addLayout(row)
        return lbl_v

    def setup_base_map(self, center_lat, center_lon):
        # מפה נקייה ומהירה בדיוק כמו בקוד המקורי, עם קריאת JS יחידה ומרוכזת
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"/>
            <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
            <style>
                html, body, #map {{ height: 100%; margin: 0; padding: 0; background-color: #0F172A; font-family: 'Inter', sans-serif; border-radius: 16px; }}
                .leaflet-control-layers {{ border-radius: 8px !important; background: #1E293B !important; color: white !important; border: none !important; }}
                .drone-icon {{ background: transparent; border: none; overflow: visible; }}
                .map-fab-container {{
                    position: absolute; bottom: 30px; right: 20px; z-index: 1000;
                    display: flex; flex-direction: column; gap: 10px;
                }}
                .map-fab {{
                    background: #FFFFFF; color: #0F172A; border: 1px solid #E2E8F0; border-radius: 12px;
                    width: 44px; height: 44px; font-weight: bold; cursor: pointer;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.15); transition: 0.2s; font-size: 18px;
                }}
                .map-fab:hover {{ background: #F8FAFC; transform: scale(1.05); }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div class="map-fab-container">
                <button class="map-fab" onclick="recenterMap()" title="Center UAV">🎯</button>
                <button class="map-fab" onclick="goHome()" title="Go to Home" style="color:#10B981;">🏠</button>
            </div>
            <script>
                var tileOptions = {{ maxZoom: 20, updateWhenIdle: false, keepBuffer: 4, crossOrigin: true }};
                var satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', tileOptions);
                var osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', tileOptions);

                var map = L.map('map', {{ center: [{center_lat}, {center_lon}], zoom: 18, layers: [satelliteLayer], zoomControl: false }});
                L.control.zoom({{position: 'bottomright'}}).addTo(map);
                L.control.scale({{imperial: false, metric: true, position: 'bottomleft'}}).addTo(map);
                L.control.layers({{ "SATELLITE": satelliteLayer, "STREET MAP": osmLayer }}, null, {{position: 'topleft'}}).addTo(map);

                var ekfPath = L.polyline([], {{color: '#2F80ED', weight: 4, opacity: 0.8}}).addTo(map);
                var accuracyCircle = L.circle([{center_lat}, {center_lon}], {{radius: 0, color: 'rgba(47, 128, 237, 0.4)', fillOpacity: 0.1, weight: 1}}).addTo(map);

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
                                        <stop offset="0%" style="stop-color:#2F80ED;stop-opacity:1" />
                                        <stop offset="100%" style="stop-color:#2F80ED;stop-opacity:0" />
                                      </linearGradient>
                                    </defs>
                                 </svg>
                                 <svg viewBox="0 0 24 24" width="36" height="36" style="position:absolute; top:52px; left:32px;">
                                    <path d="M12,2L4.5,20.3L5.2,21L12,18L18.8,21L19.5,20.3L12,2z" fill="#10B981" stroke="#FFFFFF" stroke-width="1"/>
                                 </svg>
                               </div>`,
                        iconSize: [0, 0]
                    }});
                }}

                var droneMarker = L.marker([{center_lat}, {center_lon}], {{ icon: getDroneSVG(0) }}).addTo(map);

                map.on('dragstart', function() {{ autoPan = false; }});

                function recenterMap() {{ autoPan = true; map.panTo(dronePos, {{animate: true}}); }}
                function goHome() {{ if(homePos) map.panTo(homePos, {{animate: true}}); autoPan = false; }}

                // פונקציית העדכון המרכזית (כמו בקוד המקורי - קריאה אחת בלבד מ-Python)
                function updateMapData(ekfCoords, heading, hdop, homeLat, homeLon) {{
                    if (ekfCoords.length === 0) return;

                    ekfPath.setLatLngs(ekfCoords);
                    dronePos = ekfCoords[ekfCoords.length - 1];

                    droneMarker.setLatLng(dronePos);
                    droneMarker.setIcon(getDroneSVG(heading));

                    accuracyCircle.setLatLng(dronePos);
                    accuracyCircle.setRadius(hdop * 3.0);

                    if (homeLat !== null && homeLon !== null && homeMarker === null) {{
                        homePos = [homeLat, homeLon];
                        var hIcon = L.divIcon({{html: '<div style="font-size:20px;">🏠</div>', className: '', iconSize:[20,20], iconAnchor:[10,20]}});
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
            self.timer.start(100) # 10Hz Refresh

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

            # עדכון לוגים
            if len(self.nav.events) > self.last_handled_events:
                new_events = self.nav.events[self.last_handled_events:]
                for e in new_events:
                    self.tab_events.append(e)
                self.tab_events.moveCursor(QTextCursor.MoveOperation.End)
                self.last_handled_events = len(self.nav.events)

            # עדכון טלמטריה גולמית
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
            color = "#10B981" if self.pulse_state else "#64748B"
            self.pulse_indicator.setStyleSheet(f"color: {color}; font-weight: 900; font-size: 14px;")
            self.lbl_top_status.setText(f"{status}")
            self.lbl_top_status.setStyleSheet("background: #10B981; color: white; padding: 4px 12px; border-radius: 10px; font-weight: bold; font-size: 12px;")
            self.ind_link.setStyleSheet("background-color: #10B981; border-radius: 6px;")
        else:
            self.pulse_indicator.setStyleSheet("color: #64748B; font-weight: 900; font-size: 14px;")
            self.lbl_top_status.setText("OFFLINE")
            self.lbl_top_status.setStyleSheet("background: #EF4444; color: white; padding: 4px 12px; border-radius: 10px; font-weight: bold; font-size: 12px;")
            self.ind_link.setStyleSheet("background-color: #EF4444; border-radius: 6px;")

        # PFD
        self.lbl_speed_val.setText(f"{speed:.1f}")
        self.lbl_hdg_val.setText(f"{heading:03.0f}°")
        self.horizon.set_attitude(pitch, roll)

        # Health Indicators
        self.ind_gps.setStyleSheet("background-color: #10B981; border-radius: 6px;" if gps_valid else "background-color: #EF4444; border-radius: 6px;")
        self.ind_ekf.setStyleSheet("background-color: #10B981; border-radius: 6px;" if status == "ARMED" else "background-color: #F59E0B; border-radius: 6px;")

        # Stats
        self.lbl_hdop.setText(f"{hdop:.2f}")
        self.lbl_pkts.setText(f"{pkts_sec:.1f} Hz")
        self.lbl_latency.setText(f"{dt_packet * 1000:.0f} ms" if is_active else "-- ms")

        # MAP UPDATE - קריאה אחת בודדת כמו בקוד המקורי
        if self.map_ready and is_active:
            ekf_c = [[c[0], c[1]] for c in self.nav.ekf_coords if not np.isnan(c[0])]

            h_lat_str = str(home_l) if home_l is not None else "null"
            h_lon_str = str(home_lon) if home_lon is not None else "null"

            ekf_json = json.dumps(ekf_c)
            js_cmd = f"updateMapData({ekf_json}, {heading:.1f}, {hdop:.2f}, {h_lat_str}, {h_lon_str});"
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