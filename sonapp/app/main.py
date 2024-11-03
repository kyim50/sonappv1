# app/main.py
import sys
import tray_icon
import state_monitor

def main():
    # Initialize the system tray icon
    tray_icon.create_tray_icon()

    # Start monitoring the League of Legends client state
    state_monitor.start_monitoring()

if __name__ == "__main__":
    main()
