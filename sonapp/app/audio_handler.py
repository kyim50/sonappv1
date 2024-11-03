import sounddevice as sd
import socket
import threading
import numpy as np

# Set constants
CHANNELS = 1
HOST = '127.0.0.1'
PORT = 65432
BUFFER_SIZE = 256  # Reduced buffer size for lower latency

# Select input/output devices
INPUT_DEVICE_ID = 1  # Replace with your input device ID
OUTPUT_DEVICE_ID = 12  # Replace with your output device ID

# Get the maximum sample rate of the output device
output_device_info = sd.query_devices(OUTPUT_DEVICE_ID, 'output')
SAMPLE_RATE = min(int(output_device_info['default_samplerate']), 48000)  # Use a maximum of 48000 Hz

def audio_callback(outdata, frames, time, status):
    if status:
        print(status)
    try:
        audio_data = sock.recv(BUFFER_SIZE * CHANNELS * 4)  # Adjust for float32 size
        audio_array = np.frombuffer(audio_data, dtype=np.float32)

        if audio_array.size > frames:
            outdata[:] = audio_array[:frames].reshape(-1, CHANNELS)
        else:
            outdata[:audio_array.size] = audio_array.reshape(-1, CHANNELS)
            outdata[audio_array.size:] = 0  # Fill the rest with zeros if there's less data
    except Exception as e:
        print(f"Error in audio callback: {e}")

def start_audio_communication():
    """Starts the audio communication."""
    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=audio_callback, device=OUTPUT_DEVICE_ID, blocksize=BUFFER_SIZE):
        print("Output audio stream started")
        while True:
            pass  # Keep the stream alive

def send_audio():
    """Captures audio from the microphone and sends it to the server."""
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32', device=INPUT_DEVICE_ID, blocksize=BUFFER_SIZE) as stream:
        print("Input audio stream started")
        while True:
            data = stream.read(BUFFER_SIZE)[0]  # Read audio data from the stream
            audio_bytes = data.tobytes()  # Convert to bytes
            sock.sendall(audio_bytes)  # Send audio data to server

# Create socket connection
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))
print("Connected to server for sending audio")

# Start threads for audio communication
threading.Thread(target=start_audio_communication, daemon=True).start()
send_audio()
