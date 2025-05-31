import socket
import threading
import numpy as np
from collections import deque, defaultdict
import time
import json
import netifaces
import os

class CentralAudioServer:
    def __init__(self, buffer_size=1024, discovery_port=65431):
        self.buffer_size = buffer_size
        self.discovery_port = discovery_port
        self.stream_port = 65432
        self.running = True

        self.clients = {}  # client_id -> client_data
        self.channels = defaultdict(dict)  # channel_key -> {client_id: client_data}
        self.audio_levels = {}

        self.host = self.get_local_ip()
        print(f"\n=== Central Audio Server ===")
        print(f"Server IP address: {self.host}")

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        threading.Thread(target=self.display_status, daemon=True).start()
        threading.Thread(target=self.handle_discovery, daemon=True).start()

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
        except:
            return '127.0.0.1'

    def calculate_audio_level(self, audio_data):
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            rms = np.sqrt(np.mean(np.square(audio_array)))
            db = 20 * np.log10(rms) if rms > 0 else -100
            return max(-100, db)
        except:
            return -100

    def display_status(self):
        while self.running:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\n=== Central Audio Server Status ===")
            print(f"Server IP: {self.host}:{self.stream_port}")
            print(f"Channels: {len(self.channels)}")

            for channel, members in self.channels.items():
                print(f"\nChannel: {channel} ({len(members)} clients)")
                print("-" * 50)
                for client_id, client_data in members.items():
                    address = client_data['address']
                    level = self.audio_levels.get(client_id, -100)
                    bars = '█' * int((level + 100) // 5)
                    print(f"{address[0]}:{address[1]} | Level: {bars} {level:.1f} dB")
            time.sleep(0.5)

    def handle_discovery(self):
        self.discovery_socket.bind(('', self.discovery_port))
        print(f"Discovery service running on port {self.discovery_port}")

        while self.running:
            try:
                _, client_address = self.discovery_socket.recvfrom(1024)
                info = {'host': self.host, 'port': self.stream_port}
                self.discovery_socket.sendto(json.dumps(info).encode(), client_address)
            except:
                pass

    def mix_audio(self, channel_key, current_client_id):
        mixed = np.zeros(self.buffer_size, dtype=np.float32)
        active_clients = 0
        for cid, cdata in self.channels[channel_key].items():
            if cid != current_client_id and cdata['buffer']:
                try:
                    audio_data = cdata['buffer'].popleft()
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
        try:
            header = client_socket.recv(512).decode()
            info = json.loads(header)
            channel_key = info.get('channel')
            if not channel_key:
                print("Rejected client with no channel info")
                client_socket.close()
                return
        except:
            print("Failed to parse client header")
            client_socket.close()
            return

        client_id = id(client_socket)
        client_data = {
            'socket': client_socket,
            'address': client_address,
            'buffer': deque(maxlen=5),
            'channel': channel_key
        }

        self.clients[client_id] = client_data
        self.channels[channel_key][client_id] = client_data

        print(f"[+] {client_address} joined channel: {channel_key}")

        try:
            while self.running:
                data = client_socket.recv(self.buffer_size * 4)
                if not data:
                    break

                self.audio_levels[client_id] = self.calculate_audio_level(data)
                client_data['buffer'].append(data)
                mixed = self.mix_audio(channel_key, client_id)
                client_socket.sendall(mixed)
        except Exception as e:
            print(f"Client error {client_address}: {e}")
        finally:
            print(f"[-] {client_address} left channel: {channel_key}")
            del self.channels[channel_key][client_id]
            if not self.channels[channel_key]:
                del self.channels[channel_key]
            if client_id in self.audio_levels:
                del self.audio_levels[client_id]
            del self.clients[client_id]
            client_socket.close()

    def start(self):
        self.server_socket.bind((self.host, self.stream_port))
        self.server_socket.listen(10)
        print(f"Central server started on {self.host}:{self.stream_port}")
        while self.running:
            try:
                sock, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(sock, addr), daemon=True).start()
            except Exception as e:
                print(f"Accept error: {e}")

    def stop(self):
        self.running = False
        self.discovery_socket.close()
        self.server_socket.close()
        print("Server shut down")

if __name__ == "__main__":
    server = CentralAudioServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
