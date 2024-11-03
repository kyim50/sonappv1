import socket
import threading
import sounddevice as sd
import numpy as np

SAMPLE_RATE = 44100
CHANNELS = 1
HOST = '127.0.0.1'
PORT = 65432
BUFFER_SIZE = 4096  # Adjust this based on your needs

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
            
            # Broadcast audio data to all clients (or handle it as needed)
            for client in clients:
                if client != conn:  # Don't send back to the sender
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
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS) as stream:
        print("Audio input stream started")
        while True:
            data = stream.read(BUFFER_SIZE)[0]  # Read audio data from the stream
            audio_bytes = data.astype(np.float32).tobytes()  # Convert to bytes
            for client in clients:  # Send audio to all connected clients
                try:
                    client.sendall(audio_bytes)
                except Exception as e:
                    print(f"Error sending audio to client: {e}")

if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    audio_input_stream()  # Start capturing and sending audio
