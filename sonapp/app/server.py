import socket
import threading
import numpy as np
from collections import deque
import time
import json
import netifaces
import wave
import os

class AudioServer:
    def __init__(self, channels=1, buffer_size=1024, discovery_port=65431):
        self.channels = channels
        self.buffer_size = buffer_size
        self.discovery_port = discovery_port
        self.stream_port = 65432
        self.clients = {}
        self.running = True
        
        # Add audio level monitoring
        self.audio_levels = {}
        
        self.host = self.get_local_ip()
        print(f"\n=== Audio Server ===")
        print(f"Server IP address: {self.host}")
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Start status display thread
        self.status_thread = threading.Thread(target=self.display_status, daemon=True)
        self.status_thread.start()

    def get_local_ip(self):
        try:
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        if not ip.startswith('127.'):
                            return ip
            
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(('8.8.8.8', 80))
                return s.getsockname()[0]
        except Exception as e:
            print(f"Error getting IP address: {e}")
            return '127.0.0.1'

    def calculate_audio_level(self, audio_data):
        """Calculate RMS audio level in dB"""
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            rms = np.sqrt(np.mean(np.square(audio_array)))
            db = 20 * np.log10(rms) if rms > 0 else -100
            return max(-100, db)  # Limit minimum to -100 dB
        except:
            return -100

    def display_status(self):
        """Display server status and audio levels"""
        while self.running:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\n=== Audio Server Status ===")
            print(f"Server IP: {self.host}:{self.stream_port}")
            print(f"Connected clients: {len(self.clients)}")
            print("\nAudio Levels:")
            print("-" * 50)
            
            for client_id, client_data in self.clients.items():
                address = client_data['address']
                level = self.audio_levels.get(client_id, -100)
                bars = '█' * int((level + 100) // 5)  # Convert dB to visual bars
                print(f"{address[0]}:{address[1]}")
                print(f"Level: {bars} {level:.1f} dB")
                print("-" * 50)
            
            time.sleep(0.1)

    def handle_discovery(self):
        self.discovery_socket.bind(('', self.discovery_port))
        print(f"Discovery service running on port {self.discovery_port}")
        
        while self.running:
            try:
                _, client_address = self.discovery_socket.recvfrom(1024)
                server_info = {
                    'host': self.host,
                    'port': self.stream_port
                }
                print(f"\nDiscovery request from {client_address[0]}")
                self.discovery_socket.sendto(json.dumps(server_info).encode(), client_address)
            except Exception as e:
                if self.running:
                    print(f"Discovery error: {e}")

    def mix_audio(self, current_client_id):
        mixed = np.zeros(self.buffer_size, dtype=np.float32)
        active_clients = 0
        
        for client_id, client_data in self.clients.items():
            if client_id != current_client_id and client_data['buffer']:
                try:
                    audio_data = client_data['buffer'].popleft()
                    audio_array = np.frombuffer(audio_data, dtype=np.float32)
                    if len(audio_array) == self.buffer_size:
                        mixed += audio_array
                        active_clients += 1
                except IndexError:
                    continue
        
        if active_clients > 0:
            mixed /= active_clients
            mixed = np.clip(mixed, -1.0, 1.0)
            
        return mixed.tobytes()

    def handle_client(self, client_socket, client_address):
        client_id = id(client_socket)
        self.clients[client_id] = {
            'socket': client_socket,
            'address': client_address,
            'buffer': deque(maxlen=5)
        }
        
        print(f"\nNew client connected: {client_address}")
        
        try:
            while self.running:
                data = client_socket.recv(self.buffer_size * 4)
                if not data:
                    break
                
                # Update audio level for this client
                self.audio_levels[client_id] = self.calculate_audio_level(data)
                
                self.clients[client_id]['buffer'].append(data)
                mixed_audio = self.mix_audio(client_id)
                client_socket.sendall(mixed_audio)
                
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
        finally:
            print(f"\nClient disconnected: {client_address}")
            if client_id in self.audio_levels:
                del self.audio_levels[client_id]
            del self.clients[client_id]
            client_socket.close()

    def start(self):
        try:
            discovery_thread = threading.Thread(target=self.handle_discovery, daemon=True)
            discovery_thread.start()
            
            self.server_socket.bind((self.host, self.stream_port))
            self.server_socket.listen(5)
            print(f"Server started on {self.host}:{self.stream_port}")
            
            while self.running:
                client_socket, client_address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        self.discovery_socket.close()
        for client_id, client_data in list(self.clients.items()):
            client_data['socket'].close()
        self.server_socket.close()
        print("\nServer stopped")

if __name__ == "__main__":
    server = AudioServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()