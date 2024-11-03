# app/tray_icon.py
import sys
from PyQt5 import QtWidgets, QtGui

def create_tray_icon():
    """Create a system tray icon."""
    app = QtWidgets.QApplication(sys.argv)

    tray_icon = QtWidgets.QSystemTrayIcon()
    tray_icon.setIcon(QtGui.QIcon('resources/icons/icon.png'))  # Replace with your icon path

    tray_icon.setVisible(True)
    tray_icon.show()

    # Add context menu actions
    menu = QtWidgets.QMenu()
    exit_action = menu.addAction("Exit")
    exit_action.triggered.connect(app.quit)

    tray_icon.setContextMenu(menu)

    sys.exit(app.exec_())
