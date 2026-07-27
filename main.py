import sys
from PyQt6.QtWidgets import QApplication
from engine import NavigationSystem, start_udp_listener
from GUI import MainWindow

def main():
    nav_engine = NavigationSystem()
    start_udp_listener(nav_engine, port=4210)

    app = QApplication(sys.argv)
    window = MainWindow(nav_engine)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()