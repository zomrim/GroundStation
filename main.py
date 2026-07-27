# main.py
import sys
from PyQt6.QtWidgets import QApplication

# ייבוא הרכיבים מתוך הקבצים המפוצלים
from engine import NavigationSystem, start_udp_listener
from GUI import MainWindow


def main():
    # 1. יצירת מופע של מנוע הניווט (Engine)
    nav_engine = NavigationSystem()

    # 2. הפעלת ה-UDP Listener ברקע
    start_udp_listener(nav_engine, port=4210)

    # 3. הפעלת ה-GUI והזרמת המנוע אליו
    app = QApplication(sys.argv)
    window = MainWindow(nav_engine)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()