import socket
import threading
import numpy as np
from collections import deque
import time
import json
import netifaces

class AudioServer:
    def __init__(self, channels=1, buffer_size=1024, discovery_port=65431):
        self.channels = channels
        self.buffer_size = buffer_size
        self.discovery_port = discovery_port  # Port for server discovery
        self.stream_port = 65432  # Port for audio streaming
        self.clients = {}  # Dictionary to store client connections and their buffers
        self.running = True
        
        # Get server IP address
        self.host = self.get_local_ip()
        print(f"Server IP address: {self.host}")
        
        # Create server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Create discovery socket
        self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def get_local_ip(self):
        """Get the local IP address of the machine"""
        try:
            # Try to get IP address from common interfaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        # Ignore localhost
                        if not ip.startswith('127.'):
                            return ip
            
            # Fallback to socket method if no suitable interface found
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(('8.8.8.8', 80))
                return s.getsockname()[0]
        except Exception as e:
            print(f"Error getting IP address: {e}")
            return '127.0.0.1'  # Fallback to localhost if all methods fail

    def handle_discovery(self):
        """Handle server discovery requests"""
        self.discovery_socket.bind(('', self.discovery_port))
        print(f"Discovery service running on port {self.discovery_port}")
        
        while self.running:
            try:
                _, client_address = self.discovery_socket.recvfrom(1024)
                # Send server information to client
                server_info = {
                    'host': self.host,
                    'port': self.stream_port
                }
                self.discovery_socket.sendto(json.dumps(server_info).encode(), client_address)
            except Exception as e:
                if self.running:  # Only print error if we're still meant to be running
                    print(f"Discovery error: {e}")

    def mix_audio(self, current_client_id):
        """Mix audio from all clients except the current one"""
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
        """Handle individual client connections"""
        client_id = id(client_socket)
        self.clients[client_id] = {
            'socket': client_socket,
            'address': client_address,
            'buffer': deque(maxlen=5)
        }
        
        print(f"New client connected: {client_address}")
        
        try:
            while self.running:
                data = client_socket.recv(self.buffer_size * 4)
                if not data:
                    break
                
                self.clients[client_id]['buffer'].append(data)
                mixed_audio = self.mix_audio(client_id)
                client_socket.sendall(mixed_audio)
                
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
        finally:
            print(f"Client disconnected: {client_address}")
            del self.clients[client_id]
            client_socket.close()

    def start(self):
        """Start the audio server"""
        try:
            # Start discovery service
            discovery_thread = threading.Thread(target=self.handle_discovery, daemon=True)
            discovery_thread.start()
            
            # Start audio streaming service
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
        """Stop the server and clean up"""
        self.running = False
        self.discovery_socket.close()
        for client_id, client_data in list(self.clients.items()):
            client_data['socket'].close()
        self.server_socket.close()
        print("Server stopped")

if __name__ == "__main__":
    server = AudioServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()