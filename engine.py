import socket
import threading
import time
import numpy as np


class NavigationSystem:
    def __init__(self):
        self.x = np.zeros((4, 1))
        self.P = np.eye(4) * 500.0
        self.Q = np.eye(4) * 0.05
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])

        self.ref_lat, self.ref_lon = None, None
        self.home_lat, self.home_lon = None, None

        self.lock = threading.Lock()
        self.raw_gps_coords = []
        self.ekf_coords = []
        self.events = []

        self.system_status = "STANDBY"
        self.last_packet_time = 0
        self.last_gps_time = time.time()

        self.udp_connected = False
        self.gps_valid = False
        self.is_armed = False

        self.current_speed = 0.0
        self.hdop = 99.9
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.gps_time_str = "--:--:--"
        self.packets_sec = 0
        self.packet_count = 0
        self.start_time = time.time()

        self.log_event("SYSTEM", "GCS Initialized. Awaiting telemetry.")

    def log_event(self, category, message):
        timestamp = time.strftime("%H:%M:%S", time.gmtime())
        self.events.append(f"[{timestamp}] [{category}] {message}")
        if len(self.events) > 100:
            self.events.pop(0)

    def latlon_to_xy(self, lat, lon):
        R = 6371000.0
        dlat = np.radians(lat - self.ref_lat)
        dlon = np.radians(lon - self.ref_lon)
        x = dlon * R * np.cos(np.radians(self.ref_lat))
        y = dlat * R
        return x, y

    def xy_to_latlon(self, x, y):
        R = 6371000.0
        lat = self.ref_lat + np.degrees(y / R)
        lon = self.ref_lon + np.degrees(x / (R * np.cos(np.radians(self.ref_lat))))
        return lat, lon

    def predict(self, ax, ay, dt):
        F = np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 0.95, 0], [0, 0, 0, 0.95]])
        B = np.array([[0.5 * (dt ** 2), 0], [0, 0.5 * (dt ** 2)], [dt, 0], [0, dt]])
        self.x = F @ self.x + B @ np.array([[ax], [ay]])
        self.P = F @ self.P @ F.T + self.Q

    def process_packet(self, data_str):
        try:
            parts = data_str.split(',')
            if len(parts) < 10: return

            lat, lon = float(parts[0]), float(parts[1])
            gps_time = parts[2]
            hdop_val = float(parts[3])
            ax_imu, ay_imu, az_imu = float(parts[4]), float(parts[5]), float(parts[6])
            gz_imu = float(parts[9])

            current_time = time.time()
            dt = current_time - self.last_gps_time
            if dt <= 0: dt = 0.1
            self.last_gps_time = current_time

            with self.lock:
                self.packet_count += 1
                if not self.udp_connected:
                    self.log_event("LINK", "Telemetry Link Established")

                self.last_packet_time = current_time
                self.udp_connected = True
                self.gps_time_str = gps_time
                self.hdop = hdop_val

                self.pitch = np.degrees(np.arctan2(ax_imu, np.sqrt(ay_imu ** 2 + az_imu ** 2)))
                self.roll = np.degrees(np.arctan2(ay_imu, np.sqrt(ax_imu ** 2 + az_imu ** 2)))
                self.yaw = (self.yaw - gz_imu * dt) % 360.0

                was_valid = self.gps_valid
                self.gps_valid = (lat != 0.0 and lon != 0.0)

                if self.gps_valid and not was_valid:
                    self.log_event("GPS", f"3D Lock Acquired. HDOP: {self.hdop:.1f}")

                if self.gps_valid:
                    self.raw_gps_coords.append([lat, lon])
                    if self.home_lat is None:
                        self.home_lat, self.home_lon = lat, lon
                        self.log_event("NAV", f"Home Point Updated: {lat:.5f}, {lon:.5f}")

                self.predict(ax_imu, ay_imu, dt)

                if self.ref_lat is None and self.gps_valid:
                    self.ref_lat, self.ref_lon = lat, lon

                if self.ref_lat is not None:
                    z_x, z_y = self.latlon_to_xy(lat, lon)
                    z = np.array([[z_x], [z_y]])
                    innovation = z - (self.H @ self.x)
                    R = np.eye(2) * ((2.5 * max(self.hdop, 0.5)) ** 2)
                    S = self.H @ self.P @ self.H.T + R
                    K = self.P @ self.H.T @ np.linalg.inv(S)
                    self.x = self.x + (K @ innovation)
                    self.P = (np.eye(4) - K @ self.H) @ self.P

                    if not self.is_armed:
                        self.is_armed = True
                        self.system_status = "ARMED"
                        self.log_event("SYS", "Navigation Filter Armed")

                    est_lat, est_lon = self.xy_to_latlon(self.x[0, 0], self.x[1, 0])
                    self.ekf_coords.append([est_lat, est_lon])

                self.current_speed = np.sqrt(self.x[2, 0] ** 2 + self.x[3, 0] ** 2) * 3.6

        except Exception as e:
            pass


def start_udp_listener(nav_system: NavigationSystem, port: int = 4210, stop_event: threading.Event = None):
    """מפעיל Thread שמקשיב לחבילות UDP ומזין את מערכת הניווט.

    stop_event (optional): when provided and set, the loop exits cleanly and the
    socket closes, allowing the GUI's Settings page to rebind on a different
    port. Calling this exactly as before (no stop_event) preserves the original
    always-on behavior -- this is a backward-compatible addition, not a rewrite.
    """
    def udp_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.settimeout(0.5)
        try:
            while stop_event is None or not stop_event.is_set():
                try:
                    data, addr = sock.recvfrom(1024)
                    nav_system.process_packet(data.decode('utf-8').strip())
                except socket.timeout:
                    continue
                except Exception:
                    pass
        finally:
            sock.close()

    thread = threading.Thread(target=udp_loop, daemon=True)
    thread.start()
    return thread