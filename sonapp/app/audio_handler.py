import sounddevice as sd
import socket
import threading
import numpy as np
import time

# Set constants
CHANNELS = 1
HOST = '127.0.0.1'  # Replace with your server's IP
PORT = 65432        # Replace with your server's port
BUFFER_SIZE = 32    # Further reduced buffer size for even lower latency

# Automatically find input and output devices
devices = sd.query_devices()
INPUT_DEVICE_ID = None
OUTPUT_DEVICE_ID = None

# Find the first input and output device
for idx, device in enumerate(devices):
    max_input_channels = device.get('maxInputChannels', 0)  # Use get to avoid KeyError
    max_output_channels = device.get('maxOutputChannels', 0)  # Use get to avoid KeyError
    
    if max_input_channels > 0 and INPUT_DEVICE_ID is None:
        INPUT_DEVICE_ID = idx
    if max_output_channels > 0 and OUTPUT_DEVICE_ID is None:
        OUTPUT_DEVICE_ID = idx
    
    if INPUT_DEVICE_ID is not None and OUTPUT_DEVICE_ID is not None:
        break  # Exit the loop if both devices are found

if INPUT_DEVICE_ID is None or OUTPUT_DEVICE_ID is None:
    print("Input Device ID:", INPUT_DEVICE_ID)
    print("Output Device ID:", OUTPUT_DEVICE_ID)
    raise RuntimeError("No input or output device found.")


# Get the maximum sample rate of the output device
output_device_info = sd.query_devices(OUTPUT_DEVICE_ID, 'output')
SAMPLE_RATE = min(int(output_device_info['default_samplerate']), 48000)  # Use a maximum of 48000 Hz

# Create socket connection
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's algorithm

def connect_to_server():
    global sock
    while True:
        try:
            sock.connect((HOST, PORT))
            print("Connected to server for sending audio")
            break  # Exit the loop on successful connection
        except ConnectionRefusedError:
            print("Connection refused, retrying in 1 second...")
            time.sleep(1)  # Wait for a second before retrying

def audio_callback(outdata, frames, time, status):
    if status:
        print(status)
    try:
        audio_data = sock.recv(BUFFER_SIZE * CHANNELS * 4)  # Adjust for float32 size
        audio_array = np.frombuffer(audio_data, dtype=np.float32)

        # Ensure the output matches the expected shape
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

# Start threads for audio communication
threading.Thread(target=start_audio_communication, daemon=True).start()
connect_to_server()  # Ensure the connection to the server is established
send_audio()