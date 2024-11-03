# app/gui.py
import tkinter as tk
from tkinter import messagebox
import socket
import threading
from game_checker import get_game_state
import keyboard  # Requires the keyboard library
import audio_handler  # Assuming your audio handling code is in this module

class VoiceChatApp:
    def __init__(self, master):
        self.master = master
        self.master.title("League of Legends Voice Chat")
        self.master.geometry("300x400")

        self.server_host = "127.0.0.1"
        self.server_port = 65432
        self.client_socket = None

        # Connection Status
        self.status_label = tk.Label(master, text="Disconnected", fg="red")
        self.status_label.pack(pady=10)

        # Connect Button
        self.connect_button = tk.Button(master, text="Connect", command=self.connect_to_server)
        self.connect_button.pack(pady=10)

        # Mute/Unmute Button
        self.mute_button = tk.Button(master, text="Mute", command=self.toggle_mute)
        self.mute_button.pack(pady=10)

        # Volume Control
        self.volume_scale = tk.Scale(master, from_=0, to=100, orient=tk.HORIZONTAL, label="Volume")
        self.volume_scale.set(50)  # Default volume
        self.volume_scale.pack(pady=10)

        # Push-to-Talk Button
        self.ptt_button = tk.Button(master, text="Push to Talk", command=self.start_ptt)
        self.ptt_button.pack(pady=10)

        # Connected Users List
        self.connected_users_list = tk.Listbox(master)
        self.connected_users_list.pack(pady=10, fill=tk.BOTH, expand=True)

        self.is_muted = False
        self.volume = 50

        # Game State Label
        self.game_state_label = tk.Label(master, text="Game State: Unknown", fg="orange")
        self.game_state_label.pack(pady=10)

        # Check game state every second
        self.check_game_state()

        # PTT key
        self.ptt_key = 'space'  # Default key for PTT

    def connect_to_server(self):
        """Connects to the audio server."""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_host, self.server_port))
            self.status_label.config(text="Connected", fg="green")
            threading.Thread(target=audio_handler.start_audio_communication, daemon=True).start()
            self.update_connected_users()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")

    def toggle_mute(self):
        """Toggles the mute state."""
        self.is_muted = not self.is_muted
        self.mute_button.config(text="Unmute" if self.is_muted else "Mute")

    def start_ptt(self):
        """Start push-to-talk functionality."""
        def ptt():
            if not self.is_muted:
                audio_handler.send_audio_with_ptt(self.ptt_key)  # Assuming this function captures audio only when PTT is active

        # Register the PTT key event
        keyboard.on_press_key(self.ptt_key, lambda _: ptt())
        keyboard.on_release_key(self.ptt_key, lambda _: audio_handler.stop_sending_audio())

    def update_connected_users(self):
        """Updates the list of connected users."""
        self.connected_users_list.delete(0, tk.END)
        # For simplicity, this example uses dummy data; replace this with actual logic to fetch connected users
        self.connected_users_list.insert(tk.END, "User1")
        self.connected_users_list.insert(tk.END, "User2")

    def check_game_state(self):
        """Check and update the game state."""
        state = get_game_state()
        self.game_state_label.config(text=f"Game State: {state}")
        if state == "In Game":
            self.create_voice_channel()
            # Automatically join the voice channel here
            # join_voice_channel()  # Replace with your logic to join the channel
        self.master.after(1000, self.check_game_state)  # Check every second

    def create_voice_channel(self):
        """Create a voice channel for the user."""
        # Implement logic to create a voice channel here
        print("Voice channel created.")

    def receive_audio(self):
        """Placeholder for audio receiving logic. Replace with actual implementation."""
        while self.client_socket:
            try:
                # Here you would receive audio data and process it
                pass
            except Exception as e:
                print(f"Error receiving audio: {e}")
                break

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceChatApp(root)
    root.mainloop()
