import sys
import time
import json
import numpy as np

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QFrame, QSplitter, QTabWidget, QTextEdit)
from PyQt6.QtGui import QColor, QPainter, QPen
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
        painter.drawRect(0, 0, w, h)

        painter.translate(w / 2, h / 2)
        painter.rotate(-self.roll)

        pitch_offset = self.pitch * 2.5

        sky_color = QColor("#0284c7")
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

        painter.setPen(QPen(QColor("#f59e0b"), 3))
        painter.drawLine(-40, 0, -15, 0)
        painter.drawLine(15, 0, 40, 0)
        painter.drawLine(0, 0, 0, 15)
        painter.drawPoint(0, 0)

        painter.resetTransform()
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawArc(10, 10, w - 20, h - 20, 30 * 16, 120 * 16)


# ==========================================
# 2. Professional GCS UI (PyQt6)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self, nav_system: NavigationSystem):
        super().__init__()
        self.nav = nav_system  # שמיעת נתונים ממנוע הניווט

        self.setWindowTitle("Mission Control Center - Professional GCS")
        self.resize(1600, 900)

        self.setStyleSheet("""
            QMainWindow { background-color: #0f172a; }
            QLabel { font-family: 'Segoe UI', -apple-system, sans-serif; color: #e2e8f0; }
            QFrame { border: none; }
            QTabWidget::pane { border: 1px solid #334155; border-radius: 4px; background: #0b0f19; }
            QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 8px 16px; border-radius: 4px 4px 0 0; margin-right: 2px; font-weight: bold; }
            QTabBar::tab:selected { background: #38bdf8; color: #0f172a; }
            QTextEdit { background-color: #0b0f19; color: #10b981; font-family: 'Consolas', monospace; border: none; padding: 10px; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # TOP MISSION BAR
        header_frame = QFrame()
        header_frame.setStyleSheet("background: #1e293b; border-radius: 6px;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 8, 16, 8)

        sys_title = QLabel("MISSION CONTROL ALFA")
        sys_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc; letter-spacing: 1px;")

        self.pulse_indicator = QLabel("● LIVE")
        self.pulse_indicator.setStyleSheet("color: #64748b; font-weight: 900; font-size: 14px;")

        self.lbl_top_status = QLabel("UAV: OFFLINE")
        self.lbl_top_status.setStyleSheet("background: #ef4444; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;")

        header_layout.addWidget(sys_title)
        header_layout.addStretch()
        header_layout.addWidget(self.pulse_indicator)
        header_layout.addSpacing(20)
        header_layout.addWidget(self.lbl_top_status)
        root_layout.addWidget(header_frame)

        # MAIN SPLITTER
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT PANEL
        left_panel = QFrame()
        left_panel.setStyleSheet("background: #1e293b; border-radius: 6px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)

        title_pfd = QLabel("PRIMARY FLIGHT DATA")
        title_pfd.setStyleSheet("color: #94a3b8; font-weight: bold; letter-spacing: 1px; font-size: 11px;")
        left_layout.addWidget(title_pfd)

        self.lbl_speed_val = QLabel("0.0")
        self.lbl_speed_val.setStyleSheet("font-size: 42px; font-weight: 900; color: #38bdf8;")
        self.lbl_speed_unit = QLabel("GROUND SPEED (km/h)")
        self.lbl_speed_unit.setStyleSheet("color: #64748b; font-weight: bold;")

        self.lbl_hdg_val = QLabel("000°")
        self.lbl_hdg_val.setStyleSheet("font-size: 42px; font-weight: 900; color: #a78bfa;")
        self.lbl_hdg_unit = QLabel("HEADING")
        self.lbl_hdg_unit.setStyleSheet("color: #64748b; font-weight: bold;")

        left_layout.addWidget(self.lbl_speed_val)
        left_layout.addWidget(self.lbl_speed_unit)
        left_layout.addSpacing(15)
        left_layout.addWidget(self.lbl_hdg_val)
        left_layout.addWidget(self.lbl_hdg_unit)
        left_layout.addSpacing(25)

        self.horizon = AttitudeIndicator()
        left_layout.addWidget(self.horizon)
        left_layout.addStretch()

        # CENTER PANEL
        center_splitter = QSplitter(Qt.Orientation.Vertical)

        map_frame = QFrame()
        map_frame.setStyleSheet("background: #0f172a; border-radius: 6px;")
        map_layout = QVBoxLayout(map_frame)
        map_layout.setContentsMargins(0, 0, 0, 0)
        self.web_view = QWebEngineView()
        map_layout.addWidget(self.web_view)
        center_splitter.addWidget(map_frame)

        self.tabs = QTabWidget()
        self.tab_events = QTextEdit()
        self.tab_events.setReadOnly(True)
        self.tabs.addTab(self.tab_events, "MISSION EVENTS")

        self.tab_raw = QTextEdit()
        self.tab_raw.setReadOnly(True)
        self.tab_raw.setStyleSheet("background-color: #0b0f19; color: #94a3b8; font-family: 'Consolas', monospace;")
        self.tabs.addTab(self.tab_raw, "RAW TELEMETRY")

        center_splitter.addWidget(self.tabs)
        center_splitter.setSizes([700, 200])

        # RIGHT PANEL
        right_panel = QFrame()
        right_panel.setStyleSheet("background: #1e293b; border-radius: 6px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        title_health = QLabel("SYSTEM HEALTH")
        title_health.setStyleSheet("color: #94a3b8; font-weight: bold; letter-spacing: 1px; font-size: 11px;")
        right_layout.addWidget(title_health)

        self.ind_link = self.create_health_indicator("UDP Datalink", right_layout)
        self.ind_gps = self.create_health_indicator("GPS 3D Lock", right_layout)
        self.ind_ekf = self.create_health_indicator("EKF Active", right_layout)

        right_layout.addSpacing(20)
        title_net = QLabel("NETWORK STATS")
        title_net.setStyleSheet("color: #94a3b8; font-weight: bold; letter-spacing: 1px; font-size: 11px;")
        right_layout.addWidget(title_net)

        self.lbl_hdop = self.create_stat_row("HDOP", "--", right_layout)
        self.lbl_pkts = self.create_stat_row("Packets/Sec", "0 Hz", right_layout)
        self.lbl_latency = self.create_stat_row("Latency", "-- ms", right_layout)
        self.lbl_time = self.create_stat_row("UTC Time", "--:--:--", right_layout)

        right_layout.addStretch()

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(center_splitter)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([300, 1000, 300])

        root_layout.addWidget(main_splitter)

        # INIT MAP & TIMERS
        self.map_ready = False
        self.web_view.loadFinished.connect(self.on_map_loaded)
        self.setup_base_map(32.0853, 34.7818)

        self.pulse_state = False
        self.last_handled_events = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)

    def create_health_indicator(self, text, parent_layout):
        row = QHBoxLayout()
        lbl_icon = QLabel("🔴")
        lbl_text = QLabel(text)
        lbl_text.setStyleSheet("font-weight: bold; font-size: 13px;")
        row.addWidget(lbl_icon)
        row.addWidget(lbl_text)
        row.addStretch()
        parent_layout.addLayout(row)
        return lbl_icon

    def create_stat_row(self, title, val, parent_layout):
        row = QHBoxLayout()
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #94a3b8;")
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet("font-family: 'Consolas', monospace; font-weight: bold; color: #f8fafc;")
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
                html, body, #map {{ height: 100%; margin: 0; padding: 0; background-color: #0f172a; font-family: 'Segoe UI', sans-serif; }}
                .leaflet-control-layers {{ border-radius: 4px !important; background: #1e293b !important; color: white !important; border: none !important; }}
                .drone-icon {{ background: transparent; border: none; overflow: visible; }}
                .map-fab-container {{
                    position: absolute; bottom: 30px; right: 20px; z-index: 1000;
                    display: flex; flex-direction: column; gap: 10px;
                }}
                .map-fab {{
                    background: #38bdf8; color: #0f172a; border: none; border-radius: 50%;
                    width: 44px; height: 44px; font-weight: bold; cursor: pointer;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: 0.2s;
                }}
                .map-fab:hover {{ background: #0284c7; color: white; transform: scale(1.05); }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div class="map-fab-container">
                <button class="map-fab" onclick="recenterMap()" title="Center UAV">🎯</button>
                <button class="map-fab" onclick="goHome()" title="Go to Home" style="background:#10b981;">🏠</button>
            </div>
            <script>
                var tileOptions = {{ maxZoom: 20, updateWhenIdle: false, keepBuffer: 4, crossOrigin: true }};
                var satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', tileOptions);
                var osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', tileOptions);

                var map = L.map('map', {{ center: [{center_lat}, {center_lon}], zoom: 18, layers: [satelliteLayer], zoomControl: false }});
                L.control.zoom({{position: 'topright'}}).addTo(map);
                L.control.scale({{imperial: false, metric: true, position: 'bottomleft'}}).addTo(map);
                L.control.layers({{ "SATELLITE": satelliteLayer, "STREET MAP": osmLayer }}, null, {{position: 'topleft'}}).addTo(map);

                var ekfPath = L.polyline([], {{color: '#38bdf8', weight: 4, opacity: 0.8}}).addTo(map);
                var accuracyCircle = L.circle([{center_lat}, {center_lon}], {{radius: 0, color: 'rgba(56, 189, 248, 0.4)', fillOpacity: 0.1, weight: 1}}).addTo(map);

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
                                        <stop offset="0%" style="stop-color:#38bdf8;stop-opacity:1" />
                                        <stop offset="100%" style="stop-color:#38bdf8;stop-opacity:0" />
                                      </linearGradient>
                                    </defs>
                                 </svg>
                                 <svg viewBox="0 0 24 24" width="36" height="36" style="position:absolute; top:52px; left:32px;">
                                    <path d="M12,2L4.5,20.3L5.2,21L12,18L18.8,21L19.5,20.3L12,2z" fill="#10b981" stroke="#ffffff" stroke-width="1"/>
                                 </svg>
                               </div>`,
                        iconSize: [0, 0]
                    }});
                }}

                var droneMarker = L.marker([{center_lat}, {center_lon}], {{ icon: getDroneSVG(0) }}).addTo(map);

                map.on('dragstart', function() {{ autoPan = false; }});

                function recenterMap() {{ autoPan = true; map.panTo(dronePos, {{animate: true}}); }}
                function goHome() {{ if(homePos) map.panTo(homePos, {{animate: true}}); autoPan = false; }}

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
            self.timer.start(100)  # 10Hz UI Refresh

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
                self.last_handled_events = len(self.nav.events)

            raw_str = f"Lat: {self.nav.raw_gps_coords[-1][0]:.6f}, Lon: {self.nav.raw_gps_coords[-1][1]:.6f}\nPitch: {pitch:.1f}, Roll: {roll:.1f}\nHDOP: {hdop:.2f}" if self.nav.raw_gps_coords else "No raw data."

        # Connection Pulse & Status
        if is_active:
            self.pulse_state = not self.pulse_state
            color = "#10b981" if self.pulse_state else "#064e3b"
            self.pulse_indicator.setStyleSheet(f"color: {color}; font-weight: 900; font-size: 14px;")
            self.lbl_top_status.setText(f"UAV: {status}")
            self.lbl_top_status.setStyleSheet("background: #10b981; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;")
            self.ind_link.setText("🟢")
        else:
            self.pulse_indicator.setStyleSheet("color: #334155; font-weight: 900; font-size: 14px;")
            self.lbl_top_status.setText("UAV: OFFLINE")
            self.lbl_top_status.setStyleSheet("background: #ef4444; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;")
            self.ind_link.setText("🔴")

        # PFD
        self.lbl_speed_val.setText(f"{speed:.1f}")
        self.lbl_hdg_val.setText(f"{heading:03.0f}°")
        self.horizon.set_attitude(pitch, roll)

        # Health Dashboard
        self.ind_gps.setText("🟢" if gps_valid else "🔴")
        self.ind_ekf.setText("🟢" if status == "ARMED" else "🟡")

        # Network Stats
        self.lbl_hdop.setText(f"{hdop:.2f}")
        self.lbl_pkts.setText(f"{pkts_sec:.1f} Hz")
        self.lbl_latency.setText(f"{dt_packet * 1000:.0f} ms" if is_active else "-- ms")
        self.lbl_time.setText(self.nav.gps_time_str)

        # Raw Tab
        self.tab_raw.setText(raw_str)

        # Map Update
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
    # 1. יצירת מופע של מנוע הניווט
    nav = NavigationSystem()

    # 2. הפעלת ה-UDP Listener ברקע
    start_udp_listener(nav, port=4210)

    # 3. הפעלת ה-GUI
    app = QApplication(sys.argv)
    window = MainWindow(nav)
    window.show()
    sys.exit(app.exec())