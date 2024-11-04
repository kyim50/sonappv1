import sounddevice as sd
import socket
import threading
import numpy as np
import time

# Set constants
CHANNELS = 1
HOST = '127.0.0.1'
PORT = 65432
BUFFER_SIZE = 32

def list_available_devices():
    """List all available audio devices and their properties"""
    devices = sd.query_devices()
    print("\nAvailable Audio Devices:")
    print("-" * 50)
    for idx, device in enumerate(devices):
        print(f"Device {idx}: {device['name']}")
        print(f"    Max Input Channels: {device['max_input_channels']}")
        print(f"    Max Output Channels: {device['max_output_channels']}")
        print(f"    Default Sample Rate: {device['default_samplerate']}")
        print("-" * 50)

def find_audio_devices():
    """Find suitable input and output devices with error handling"""
    try:
        devices = sd.query_devices()
        input_device_id = sd.default.device[0]
        output_device_id = sd.default.device[1]
        
        # If default devices aren't set, try to find working devices
        if input_device_id < 0 or output_device_id < 0:
            for idx, device in enumerate(devices):
                if device['max_input_channels'] > 0 and input_device_id < 0:
                    input_device_id = idx
                if device['max_output_channels'] > 0 and output_device_id < 0:
                    output_device_id = idx
        
        # Verify devices are valid
        if input_device_id < 0 or output_device_id < 0:
            list_available_devices()
            raise RuntimeError("Could not find suitable audio devices")
        
        # Test devices
        try:
            sd.check_input_settings(device=input_device_id, channels=CHANNELS)
            sd.check_output_settings(device=output_device_id, channels=CHANNELS)
        except sd.PortAudioError as e:
            list_available_devices()
            raise RuntimeError(f"Audio device validation failed: {str(e)}")
            
        return input_device_id, output_device_id
        
    except Exception as e:
        list_available_devices()
        raise RuntimeError(f"Error finding audio devices: {str(e)}")

def get_safe_sample_rate(device_id, device_type='output'):
    """Get a safe sample rate for the device"""
    try:
        device_info = sd.query_devices(device_id, device_type)
        return min(int(device_info['default_samplerate']), 48000)
    except Exception as e:
        raise RuntimeError(f"Error getting sample rate for device {device_id}: {str(e)}")

class AudioStream:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.running = True
        
    def connect_to_server(self):
        """Connect to the server with retry logic"""
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries:
            try:
                self.sock.connect((HOST, PORT))
                print("Connected to server for sending audio")
                return True
            except ConnectionRefusedError:
                retry_count += 1
                print(f"Connection refused, retry {retry_count}/{max_retries} in 1 second...")
                time.sleep(1)
        
        raise RuntimeError("Failed to connect to server after maximum retries")

    def audio_callback(self, outdata, frames, time, status):
        """Handle audio output callback"""
        if status:
            print(f"Output stream status: {status}")
        try:
            audio_data = self.sock.recv(BUFFER_SIZE * CHANNELS * 4)
            if not audio_data:  # Connection closed
                raise RuntimeError("Server connection closed")
                
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            if audio_array.size > frames:
                outdata[:] = audio_array[:frames].reshape(-1, CHANNELS)
            else:
                outdata[:audio_array.size] = audio_array.reshape(-1, CHANNELS)
                outdata[audio_array.size:] = 0
        except Exception as e:
            print(f"Error in audio callback: {e}")
            outdata.fill(0)

    def start_audio_communication(self):
        """Start audio output stream"""
        try:
            with sd.OutputStream(
                samplerate=self.sample_rate,
                channels=CHANNELS,
                callback=self.audio_callback,
                device=self.output_device_id,
                blocksize=BUFFER_SIZE
            ) as stream:
                print("Output audio stream started")
                while self.running:
                    time.sleep(0.1)
        except Exception as e:
            raise RuntimeError(f"Error in output stream: {str(e)}")

    def send_audio(self):
        """Handle audio input and sending"""
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=CHANNELS,
                dtype='float32',
                device=self.input_device_id,
                blocksize=BUFFER_SIZE
            ) as stream:
                print("Input audio stream started")
                while self.running:
                    try:
                        data = stream.read(BUFFER_SIZE)[0]
                        audio_bytes = data.tobytes()
                        self.sock.sendall(audio_bytes)
                    except Exception as e:
                        print(f"Error sending audio: {e}")
                        break
        except Exception as e:
            raise RuntimeError(f"Error in input stream: {str(e)}")

    def run(self):
        """Main method to run the audio stream"""
        try:
            # Find and validate audio devices
            self.input_device_id, self.output_device_id = find_audio_devices()
            print(f"Using input device: {self.input_device_id}")
            print(f"Using output device: {self.output_device_id}")
            
            # Get sample rate
            self.sample_rate = get_safe_sample_rate(self.output_device_id)
            print(f"Using sample rate: {self.sample_rate}")
            
            # Connect to server
            self.connect_to_server()
            
            # Start audio threads
            output_thread = threading.Thread(target=self.start_audio_communication, daemon=True)
            output_thread.start()
            
            # Start sending audio
            self.send_audio()
            
        except Exception as e:
            print(f"Error running audio stream: {str(e)}")
        finally:
            self.running = False
            self.sock.close()

if __name__ == "__main__":
    try:
        audio_stream = AudioStream()
        audio_stream.run()
    except KeyboardInterrupt:
        print("\nStopping audio stream...")
    except Exception as e:
        print(f"Fatal error: {str(e)}")