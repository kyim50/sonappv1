import tkinter as tk
import threading
import subprocess
import socket
import sounddevice as sd
import numpy as np

# Server configuration
HOST = '127.0.0.1'
PORT = 65432
BUFFER_SIZE = 4096  # Match the buffer size used in server.py

clients = []

def handle_client(conn):
    """Handles communication with a connected client."""
    with conn:
        print(f"Connection from {conn.getpeername()} has been established.")
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                print(f"Connection from {conn.getpeername()} has been closed.")
                break
            
            # Broadcast audio data to all clients
            for client in clients:
                if client != conn:
                    try:
                        client.sendall(data)
                    except Exception as e:
                        print(f"Error sending audio to client: {e}")

def start_server():
    """Starts the audio server and handles incoming clients."""
    global clients
    clients = []
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server started at {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            clients.append(conn)
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()

def audio_input_stream():
    """Continuously captures audio input from the microphone and sends to clients."""
    with sd.InputStream(samplerate=44100, channels=1) as stream:
        print("Audio input stream started")
        while True:
            data = stream.read(BUFFER_SIZE)[0]
            audio_bytes = data.astype(np.float32).tobytes()
            for client in clients:
                try:
                    client.sendall(audio_bytes)
                except Exception as e:
                    print(f"Error sending audio to client: {e}")

def start_audio_communication():
    """Starts the server and audio input stream in separate threads."""
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    audio_thread = threading.Thread(target=audio_input_stream, daemon=True)
    audio_thread.start()

# GUI Setup
class AudioApp:
    def __init__(self, master):
        self.master = master
        master.title("Audio Communication App")

        self.start_button = tk.Button(master, text="Start Server", command=self.start_server)
        self.start_button.pack(pady=20)

        self.connect_button = tk.Button(master, text="Connect", command=self.connect_to_audio_handler, state=tk.DISABLED)
        self.connect_button.pack(pady=20)

        self.disconnect_button = tk.Button(master, text="Disconnect", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.pack(pady=20)

        self.mute_button = tk.Button(master, text="Mute", command=self.mute_audio, state=tk.DISABLED)
        self.mute_button.pack(pady=20)

        self.status_label = tk.Label(master, text="Server not started.")
        self.status_label.pack(pady=20)

        self.muted = False
        self.audio_handler_process = None

    def start_server(self):
        """Starts the audio server and updates the GUI."""
        self.start_button.config(state=tk.DISABLED)
        self.status_label.config(text="Starting server...")
        threading.Thread(target=self.run_server_thread, daemon=True).start()

    def run_server_thread(self):
        """Runs the server in a separate thread and updates the status."""
        start_audio_communication()  # Start the server and audio input stream
        self.update_status()  # Update status once the server starts

    def update_status(self):
        """Updates the GUI status."""
        self.status_label.config(text="Server started, ready for connections.")
        self.connect_button.config(state=tk.NORMAL)

    def connect_to_audio_handler(self):
        """Runs audio_handler.py in a separate process."""
        self.connect_button.config(state=tk.DISABLED)
        self.disconnect_button.config(state=tk.NORMAL)
        self.mute_button.config(state=tk.NORMAL)

        # Start audio_handler.py
        self.audio_handler_process = subprocess.Popen(['python', 'audio_handler.py'], cwd='c:/Users/kiman/Desktop/sonapp/sonappv1/sonapp/app/')

    def disconnect(self):
        """Disconnects from the audio handler and cleans up."""
        if self.audio_handler_process:
            self.audio_handler_process.terminate()  # Stop the audio handler
            self.audio_handler_process = None
            self.status_label.config(text="Disconnected from audio handler.")
            self.connect_button.config(state=tk.NORMAL)
            self.disconnect_button.config(state=tk.DISABLED)
            self.mute_button.config(state=tk.DISABLED)

    def mute_audio(self):
        """Mutes/unmutes the audio input."""
        self.muted = not self.muted
        if self.muted:
            sd.default.device = (1, None)  # Mute the input
            self.mute_button.config(text="Unmute")
            self.status_label.config(text="Microphone is muted.")
        else:
            sd.default.device = (0, None)  # Reset to default input device
            self.mute_button.config(text="Mute")
            self.status_label.config(text="Microphone is unmuted.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioApp(root)
    root.mainloop()
