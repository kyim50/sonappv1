import sounddevice as sd
import socket
import threading
import numpy as np
import time
import json

class AudioClient:
    def __init__(self, channels=1, buffer_size=1024, discovery_port=65431):
        self.channels = channels
        self.buffer_size = buffer_size
        self.discovery_port = discovery_port
        self.running = True
        
        # Initialize socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
    def discover_server(self):
        """Discover the audio server on the network"""
        print("Searching for audio server...")
        
        # Create UDP socket for discovery
        discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        discovery_socket.settimeout(1)  # Set timeout for receiving response
        
        # Try different broadcast addresses
        broadcast_addresses = [
            '255.255.255.255',  # Global broadcast
            '192.168.1.255',    # Common local network
            '192.168.0.255',    # Alternative local network
            '10.0.0.255'        # Another common network
        ]
        
        for _ in range(5):  # Try 5 times
            for broadcast_addr in broadcast_addresses:
                try:
                    # Send discovery request
                    discovery_socket.sendto(b'', (broadcast_addr, self.discovery_port))
                    
                    # Wait for response
                    data, _ = discovery_socket.recvfrom(1024)
                    server_info = json.loads(data.decode())
                    
                    discovery_socket.close()
                    return server_info['host'], server_info['port']
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Discovery error on {broadcast_addr}: {e}")
                    continue
        
        discovery_socket.close()
        raise RuntimeError("Could not find audio server")

    def setup_audio_devices(self):
        """Set up audio input and output devices"""
        devices = sd.query_devices()
        
        # Find suitable input device
        input_device = None
        for device in devices:
            if device['max_input_channels'] > 0:
                input_device = device
                break
        
        # Find suitable output device
        output_device = None
        for device in devices:
            if device['max_output_channels'] > 0:
                output_device = device
                break
                
        if not input_device or not output_device:
            raise RuntimeError("Could not find suitable audio devices")
            
        self.sample_rate = int(min(input_device['default_samplerate'],
                                 output_device['default_samplerate'],
                                 48000))
        
        return devices.index(input_device), devices.index(output_device)

    def audio_output_callback(self, outdata, frames, time, status):
        """Handle audio output"""
        if status:
            print(f"Output status: {status}")
        
        try:
            data = self.sock.recv(self.buffer_size * 4)
            if not data:
                raise RuntimeError("Server connection closed")
            
            audio_array = np.frombuffer(data, dtype=np.float32)
            outdata[:] = audio_array.reshape(-1, self.channels)
            
        except Exception as e:
            print(f"Output error: {e}")
            outdata.fill(0)

    def audio_input_callback(self, indata, frames, time, status):
        """Handle audio input"""
        if status:
            print(f"Input status: {status}")
            
        try:
            audio_data = indata.tobytes()
            self.sock.sendall(audio_data)
        except Exception as e:
            print(f"Input error: {e}")

    def connect(self):
        """Connect to server with retry logic"""
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Discover server
                host, port = self.discover_server()
                print(f"Found server at {host}:{port}")
                
                # Connect to server
                self.sock.connect((host, port))
                print(f"Connected to server at {host}:{port}")
                return True
            except Exception as e:
                retry_count += 1
                print(f"Connection attempt {retry_count}/{max_retries} failed: {e}")
                time.sleep(1)
        
        raise RuntimeError("Failed to connect to server")

    def run(self):
        """Run the audio client"""
        try:
            # Set up audio devices
            input_device_id, output_device_id = self.setup_audio_devices()
            print(f"Using input device {input_device_id} and output device {output_device_id}")
            print(f"Sample rate: {self.sample_rate}")
            
            # Connect to server
            self.connect()
            
            # Start audio streams
            with sd.InputStream(device=input_device_id,
                              channels=self.channels,
                              callback=self.audio_input_callback,
                              samplerate=self.sample_rate,
                              blocksize=self.buffer_size), \
                 sd.OutputStream(device=output_device_id,
                               channels=self.channels,
                               callback=self.audio_output_callback,
                               samplerate=self.sample_rate,
                               blocksize=self.buffer_size):
                
                print("Audio streams started")
                while self.running:
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the client and clean up"""
        self.running = False
        self.sock.close()
        print("Client stopped")

if __name__ == "__main__":
    client = AudioClient()
    try:
        client.run()
    except KeyboardInterrupt:
        client.stop()

    #test