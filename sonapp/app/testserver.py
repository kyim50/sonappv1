import requests
import json
import time
import base64
import psutil
import re
import os
import socket
import threading
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv
load_dotenv()
# Disable SSL warnings since LCU uses self-signed certificates
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Your Riot API key
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

class LoLMatchDiscovery:
    def __init__(self):
        self.lcu_port = None
        self.lcu_token = None
        self.lcu_headers = None
        self.current_summoner = None
        self.last_game_state = None
        self.in_champ_select = False
        self.in_game = False
        self.current_match_id = None
        self.match_participants = []
        
        # Network discovery settings
        self.discovery_port = 65433
        self.peer_port = 65434
        self.peers_in_match = {}
        self.running = True
        
        # Start network discovery
        self.start_network_discovery()
        
    def start_network_discovery(self):
        """Start UDP discovery and TCP peer communication"""
        # UDP Discovery thread
        discovery_thread = threading.Thread(target=self.handle_discovery, daemon=True)
        discovery_thread.start()
        
        # TCP Peer server thread
        peer_server_thread = threading.Thread(target=self.start_peer_server, daemon=True)
        peer_server_thread.start()
        
    def handle_discovery(self):
        """Handle UDP broadcast discovery"""
        discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        discovery_socket.bind(('', self.discovery_port))
        
        print(f"🌐 Discovery service started on port {self.discovery_port}")
        
        while self.running:
            try:
                data, addr = discovery_socket.recvfrom(1024)
                message = json.loads(data.decode())
                
                if message.get('type') == 'match_discovery':
                    # Someone is looking for peers in their match
                    if (self.current_match_id and 
                        message.get('match_id') == self.current_match_id and
                        message.get('summoner_name') != self.current_summoner.get('displayName')):
                        
                        # We're in the same match! Respond
                        response = {
                            'type': 'match_response',
                            'summoner_name': self.current_summoner.get('displayName'),
                            'match_id': self.current_match_id,
                            'peer_port': self.peer_port
                        }
                        
                        discovery_socket.sendto(json.dumps(response).encode(), addr)
                        print(f"🎯 MATCH PEER FOUND: {message.get('summoner_name')} at {addr[0]}")
                        
                        # Add to peers list
                        self.peers_in_match[addr[0]] = {
                            'summoner_name': message.get('summoner_name'),
                            'address': addr[0],
                            'connected': False
                        }
                        
                        # Try to connect to them
                        threading.Thread(target=self.connect_to_peer, args=(addr[0],), daemon=True).start()
                        
                elif message.get('type') == 'match_response':
                    # Someone responded to our discovery
                    if message.get('match_id') == self.current_match_id:
                        print(f"🎯 PEER RESPONDED: {message.get('summoner_name')} at {addr[0]}")
                        
                        self.peers_in_match[addr[0]] = {
                            'summoner_name': message.get('summoner_name'),
                            'address': addr[0],
                            'connected': False
                        }
                        
                        # Try to connect to them
                        threading.Thread(target=self.connect_to_peer, args=(addr[0],), daemon=True).start()
                        
            except Exception as e:
                if self.running:
                    print(f"Discovery error: {e}")
                    
    def broadcast_match_discovery(self):
        """Broadcast that we're looking for peers in our current match"""
        if not self.current_match_id or not self.current_summoner:
            return
            
        discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        message = {
            'type': 'match_discovery',
            'summoner_name': self.current_summoner.get('displayName'),
            'match_id': self.current_match_id
        }
        
        try:
            discovery_socket.sendto(json.dumps(message).encode(), ('<broadcast>', self.discovery_port))
            print(f"📡 Broadcasting match discovery for: {self.current_match_id}")
        except Exception as e:
            print(f"Broadcast error: {e}")
        finally:
            discovery_socket.close()
            
    def start_peer_server(self):
        """Start TCP server for peer communication"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', self.peer_port))
        server_socket.listen(5)
        
        print(f"💬 Peer chat server started on port {self.peer_port}")
        
        while self.running:
            try:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=self.handle_peer_connection, args=(client_socket, addr), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"Peer server error: {e}")
                    
    def handle_peer_connection(self, client_socket, addr):
        """Handle incoming peer connection"""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                    
                message = json.loads(data.decode())
                if message.get('type') == 'chat':
                    print(f"💬 [{message.get('summoner_name')}]: {message.get('text')}")
                    
        except Exception as e:
            print(f"Peer connection error: {e}")
        finally:
            client_socket.close()
            
    def connect_to_peer(self, peer_ip):
        """Connect to a discovered peer"""
        try:
            time.sleep(1)  # Small delay to avoid connection conflicts
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect((peer_ip, self.peer_port))
            
            if peer_ip in self.peers_in_match:
                self.peers_in_match[peer_ip]['connected'] = True
                self.peers_in_match[peer_ip]['socket'] = peer_socket
                
                # Send a greeting message
                greeting = {
                    'type': 'chat',
                    'summoner_name': self.current_summoner.get('displayName'),
                    'text': f"🎮 Connected! We're in the same League match!"
                }
                peer_socket.send(json.dumps(greeting).encode())
                print(f"✅ Connected to peer: {self.peers_in_match[peer_ip]['summoner_name']}")
                
                # Keep connection alive and handle messages
                self.handle_peer_connection(peer_socket, (peer_ip, self.peer_port))
                
        except Exception as e:
            print(f"Failed to connect to peer {peer_ip}: {e}")
            
    def send_message_to_peers(self, text):
        """Send a message to all connected peers"""
        message = {
            'type': 'chat',
            'summoner_name': self.current_summoner.get('displayName'),
            'text': text
        }
        
        for peer_ip, peer_data in self.peers_in_match.items():
            if peer_data.get('connected') and 'socket' in peer_data:
                try:
                    peer_data['socket'].send(json.dumps(message).encode())
                except Exception as e:
                    print(f"Failed to send message to {peer_data['summoner_name']}: {e}")
                    peer_data['connected'] = False

    def find_lcu_credentials(self):
        """Find League Client process and extract API credentials"""
        # Debug: Print all League-related processes (only once)
        if not hasattr(self, '_debug_printed'):
            league_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and ('league' in proc.info['name'].lower() or 'riot' in proc.info['name'].lower()):
                        league_processes.append(proc.info['name'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if league_processes:
                print(f"🔍 Found League processes: {list(set(league_processes))}")
            self._debug_printed = True
        
        # Try multiple possible process names
        possible_names = ['LeagueClientUx.exe', 'LeagueClient.exe', 'RiotClientUx.exe', 'RiotClientServices.exe']
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] in possible_names:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    
                    # Extract port
                    port_match = re.search(r'--app-port=(\d+)', cmdline)
                    if port_match:
                        self.lcu_port = port_match.group(1)
                    
                    # Extract auth token (try multiple patterns)
                    token_match = re.search(r'--remoting-auth-token=([^\s"]+)', cmdline)
                    if not token_match:
                        token_match = re.search(r'--remoting-auth-token="([^"]+)"', cmdline)
                    if not token_match:
                        token_match = re.search(r'--remoting-auth-token=(\S+)', cmdline)
                    
                    if token_match:
                        self.lcu_token = token_match.group(1).strip('"')
                    
                    if self.lcu_port and self.lcu_token:
                        if not hasattr(self, '_credentials_found'):
                            print(f"✓ Found LCU credentials from {proc.info['name']} (Port: {self.lcu_port})")
                            print(f"🔑 Token length: {len(self.lcu_token)} chars")
                            self._credentials_found = True
                        # Create auth header
                        auth_string = f"riot:{self.lcu_token}"
                        auth_bytes = base64.b64encode(auth_string.encode()).decode()
                        self.lcu_headers = {
                            'Authorization': f'Basic {auth_bytes}',
                            'Content-Type': 'application/json'
                        }
                        return True
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def lcu_request(self, endpoint):
        """Make request to League Client API"""
        if not self.lcu_port or not self.lcu_headers:
            return None
            
        url = f"https://127.0.0.1:{self.lcu_port}{endpoint}"
        try:
            response = requests.get(url, headers=self.lcu_headers, verify=False, timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                if not hasattr(self, '_debug_request_printed'):
                    print(f"❌ LCU request failed: {response.status_code} for {endpoint}")
                    self._debug_request_printed = True
        except Exception as e:
            if not hasattr(self, '_debug_exception_printed'):
                print(f"❌ LCU request exception: {e}")
                self._debug_exception_printed = True
        return None
    
    def get_current_summoner(self):
        """Get current summoner info"""
        data = self.lcu_request('/lol-summoner/v1/current-summoner')
        if data:
            self.current_summoner = data
            print(f"✓ Detected account: {data['displayName']} (Level {data['summonerLevel']})")
            return True
        else:
            print("❌ Failed to get current summoner - checking if logged in...")
            return False
    
    def check_champion_select(self):
        """Check if in champion select and get participants"""
        champ_select = self.lcu_request('/lol-champ-select/v1/session')
        
        if champ_select and not self.in_champ_select:
            self.in_champ_select = True
            print("\n🎯 CHAMPION SELECT DETECTED")
            print("=" * 50)
            
            # Get team info
            my_team = champ_select.get('myTeam', [])
            their_team = champ_select.get('theirTeam', [])
            
            # Create a match ID based on all participant IDs
            all_participants = []
            for player in my_team + their_team:
                if player.get('summonerId'):
                    all_participants.append(str(player['summonerId']))
            
            if all_participants:
                # Create unique match ID from sorted participant list
                self.current_match_id = hash(tuple(sorted(all_participants)))
                print(f"🆔 Match ID: {self.current_match_id}")
                
                # Start looking for peers
                threading.Thread(target=self.broadcast_match_discovery, daemon=True).start()
            
            print("YOUR TEAM:")
            for player in my_team:
                summoner_id = player.get('summonerId')
                if summoner_id:
                    summoner_info = self.lcu_request(f'/lol-summoner/v1/summoners/{summoner_id}')
                    if summoner_info:
                        name = summoner_info.get('displayName', 'Unknown')
                        level = summoner_info.get('summonerLevel', '?')
                        print(f"  • {name} (Level {level})")
            
            print("\nENEMY TEAM:")
            for player in their_team:
                summoner_id = player.get('summonerId')
                if summoner_id:
                    summoner_info = self.lcu_request(f'/lol-summoner/v1/summoners/{summoner_id}')
                    if summoner_info:
                        name = summoner_info.get('displayName', 'Unknown')
                        level = summoner_info.get('summonerLevel', '?')
                        print(f"  • {name} (Level {level})")
                        
        elif not champ_select and self.in_champ_select:
            self.in_champ_select = False
            self.current_match_id = None
            self.peers_in_match.clear()
            print("❌ Champion select ended")
    
    def check_in_game(self):
        """Check if in game and get match participants"""
        game_session = self.lcu_request('/lol-gameflow/v1/session')
        
        if game_session and game_session.get('phase') == 'InProgress':
            if not self.in_game:
                self.in_game = True
                print("\n🎮 IN-GAME DETECTED")
                print("=" * 50)
                
                # Get active game data
                active_game = self.lcu_request('/lol-spectator/v1/current-game')
                if active_game:
                    participants = active_game.get('participants', [])
                    
                    # Update match ID with actual game data if available
                    if participants and not self.current_match_id:
                        participant_names = [p.get('summonerName', '') for p in participants]
                        self.current_match_id = hash(tuple(sorted(participant_names)))
                        threading.Thread(target=self.broadcast_match_discovery, daemon=True).start()
                    
                    # Separate teams
                    team1 = [p for p in participants if p.get('teamId') == 100]
                    team2 = [p for p in participants if p.get('teamId') == 200]
                    
                    print("TEAM 1 (Blue Side):")
                    for player in team1:
                        name = player.get('summonerName', 'Unknown')
                        champion = player.get('championId', '?')
                        print(f"  • {name} (Champion ID: {champion})")
                    
                    print("\nTEAM 2 (Red Side):")
                    for player in team2:
                        name = player.get('summonerName', 'Unknown')
                        champion = player.get('championId', '?')
                        print(f"  • {name} (Champion ID: {champion})")
                        
                    if self.peers_in_match:
                        print(f"\n🌐 CONNECTED PEERS IN THIS MATCH: {len(self.peers_in_match)}")
                        for peer_ip, peer_data in self.peers_in_match.items():
                            status = "✅ Connected" if peer_data['connected'] else "⏳ Connecting..."
                            print(f"  • {peer_data['summoner_name']} ({peer_ip}) - {status}")
                        
                        print("\n💬 Type messages to send to connected peers:")
                        
        elif not (game_session and game_session.get('phase') == 'InProgress') and self.in_game:
            self.in_game = False
            self.current_match_id = None
            self.peers_in_match.clear()
            print("❌ Game ended")
    
    def monitor(self):
        """Main monitoring loop"""
        print("🔍 Looking for League of Legends client...")
        print("💡 This script will find other players running the same script in your match!")
        
        # Start input thread for chat
        input_thread = threading.Thread(target=self.handle_chat_input, daemon=True)
        input_thread.start()
        
        while True:
            # Check if client is running
            if not self.find_lcu_credentials():
                if self.current_summoner:
                    print("❌ League client closed")
                    self.current_summoner = None
                    self.in_champ_select = False
                    self.in_game = False
                    self.current_match_id = None
                    self.peers_in_match.clear()
                time.sleep(3)
                continue
            
            # Get current summoner if we don't have it
            if not self.current_summoner:
                if self.get_current_summoner():
                    print("✓ Connected to League client!")
                else:
                    time.sleep(2)
                    continue
            
            # Check game states
            try:
                self.check_champion_select()
                self.check_in_game()
            except Exception as e:
                print(f"Error checking game state: {e}")
            
            time.sleep(1)
    
    def handle_chat_input(self):
        """Handle chat input in a separate thread"""
        while self.running:
            try:
                message = input()
                if message.strip() and self.peers_in_match:
                    self.send_message_to_peers(message)
            except:
                pass

if __name__ == "__main__":
    if not RIOT_API_KEY:
        print("⚠️  Warning: RIOT_API_KEY environment variable not set")
        print("   (The script will still work for basic client detection)")
    
    monitor = LoLMatchDiscovery()
    try:
        monitor.monitor()
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
        monitor.running = False