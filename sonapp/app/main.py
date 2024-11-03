# app/main.py
import sys
import threading
import tray_icon
import state_monitor
import server  # Import the server module
import threading
import audio_handler

def main():
    # Start the audio streaming server in a separate thread
    threading.Thread(target=server.start_server, daemon=True).start()

    # Start audio communication immediately
    audio_handler.start_audio_communication()  # Start audio communication for clients

    # Initialize the system tray icon
    tray_icon.create_tray_icon()

    # Start monitoring the League of Legends client state
    state_monitor.start_monitoring()

if __name__ == "__main__":
    main()
