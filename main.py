import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

# ייבוא הרכיבים מתוך הקבצים המפוצלים
from engine import NavigationSystem, start_udp_listener
# ודא ששם המחלקה תואם למה ששמרת בקובץ ה-GUI (GCSMainWindow או MainWindow)
from GUI import MainWindow


def main():
    # --- הגדרות חווית משתמש (UX) ותצוגה מתקדמות ---
    # הפעלת תמיכה חלקה במסכי High-DPI (למשל מסכי 4K או Mac Retina)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    # הגדרת פונט גלובלי נקי ומודרני לכלל האפליקציה (כמו ב-SaaS מודרני)
    font = QFont("Inter", 10)
    app.setFont(font)

    # --- אתחול לוגיקת המערכת (Engine) ---
    # 1. יצירת מופע של מנוע הניווט
    nav_engine = NavigationSystem()

    # 2. הפעלת ה-UDP Listener ברקע להאזנה לטלמטריה (על פורט 4210)
    start_udp_listener(nav_engine, port=4210)

    # --- אתחול הממשק הגרפי (GUI) ---
    # 3. הפעלת חלון תחנת הקרקע והעברת מנוע הניווט אליו
    window = MainWindow(nav_engine)
    window.show()

    # הרצת הלולאה הראשית של הממשק
    sys.exit(app.exec())


if __name__ == '__main__':
    main()