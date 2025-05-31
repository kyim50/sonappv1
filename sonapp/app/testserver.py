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

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
RIOT_API_KEY = os.getenv('RIOT_API_KEY')
VC_SERVER_HOST = os.getenv('VC_SERVER_HOST')
VC_SERVER_PORT = int(os.getenv('VC_SERVER_PORT'))

class LoLClientMonitor:
    def __init__(self):
        self.lcu_port = None
        self.lcu_token = None
        self.lcu_headers = None
        self.current_summoner = None
        self.last_game_state = None
        self.in_champ_select = False
        self.in_game = False
        self.voice_thread = None
        self.voice_socket = None

    def find_lcu_credentials(self):
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

        possible_names = ['LeagueClientUx.exe', 'LeagueClient.exe', 'RiotClientUx.exe', 'RiotClientServices.exe']

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] in possible_names:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    port_match = re.search(r'--app-port=(\d+)', cmdline)
                    if port_match:
                        self.lcu_port = port_match.group(1)
                    token_match = re.search(r'--remoting-auth-token=([^"]+)', cmdline)
                    if token_match:
                        self.lcu_token = token_match.group(1).strip('"')
                    if self.lcu_port and self.lcu_token:
                        if not hasattr(self, '_credentials_found'):
                            print(f"✓ Found LCU credentials from {proc.info['name']} (Port: {self.lcu_port})")
                            print(f"🔑 Token length: {len(self.lcu_token)} chars")
                            self._credentials_found = True
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
        if not self.lcu_port or not self.lcu_headers:
            return None
        url = f"https://127.0.0.1:{self.lcu_port}{endpoint}"
        try:
            response = requests.get(url, headers=self.lcu_headers, verify=False, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def get_current_summoner(self):
        data = self.lcu_request('/lol-summoner/v1/current-summoner')
        if data:
            self.current_summoner = data
            print(f"✓ Detected account: {data['displayName']} (Level {data['summonerLevel']})")
            return True
        return False

    def join_voice_channel(self, channel_name):
        def voice_loop():
            try:
                self.voice_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.voice_socket.connect((VC_SERVER_HOST, VC_SERVER_PORT))
                header = json.dumps({"channel": channel_name})
                self.voice_socket.sendall(header.encode().ljust(512))
                while True:
                    mixed = self.voice_socket.recv(4096)
                    if not mixed:
                        break
            except Exception as e:
                print(f"[VC] Error: {e}")
            finally:
                if self.voice_socket:
                    self.voice_socket.close()
                    self.voice_socket = None
                    print("[VC] Disconnected")

        if self.voice_thread and self.voice_thread.is_alive():
            return
        print(f"[VC] Joining voice channel: {channel_name}")
        self.voice_thread = threading.Thread(target=voice_loop, daemon=True)
        self.voice_thread.start()

    def leave_voice_channel(self):
        if self.voice_socket:
            try:
                self.voice_socket.close()
            except:
                pass
            self.voice_socket = None
        print("[VC] Left voice channel")

    def check_champion_select(self):
        champ_select = self.lcu_request('/lol-champ-select/v1/session')
        if champ_select and not self.in_champ_select:
            self.in_champ_select = True
            print("\n🎯 CHAMPION SELECT DETECTED\n" + "=" * 50)
            my_team = champ_select.get('myTeam', [])
            for player in my_team:
                if player.get('summonerId') == self.current_summoner.get('summonerId'):
                    team_id = 'team100' if player.get('cellId', 0) < 5 else 'team200'
                    self.join_voice_channel(f"champselect_{team_id}_{self.current_summoner['displayName']}")
        elif not champ_select and self.in_champ_select:
            self.in_champ_select = False
            self.leave_voice_channel()
            print("❌ Champion select ended")

    def check_in_game(self):
        game_session = self.lcu_request('/lol-gameflow/v1/session')
        if game_session and game_session.get('phase') == 'InProgress':
            if not self.in_game:
                self.in_game = True
                print("\n🎮 IN-GAME DETECTED\n" + "=" * 50)
                active_game = self.lcu_request('/lol-spectator/v1/current-game')
                if active_game:
                    summoner_name = self.current_summoner.get('displayName')
                    participants = active_game.get('participants', [])
                    for p in participants:
                        if p.get('summonerName') == summoner_name:
                            team_id = p.get('teamId')
                            game_id = str(active_game.get('gameId'))
                            self.join_voice_channel(f"game_{game_id}_team{team_id}")
                            break
        elif not (game_session and game_session.get('phase') == 'InProgress') and self.in_game:
            self.in_game = False
            self.leave_voice_channel()
            print("❌ Game ended")

    def monitor(self):
        print("🔍 Looking for League of Legends client...")
        while True:
            if not self.find_lcu_credentials():
                if self.current_summoner:
                    print("❌ League client closed")
                    self.current_summoner = None
                    self.in_champ_select = False
                    self.in_game = False
                    self.leave_voice_channel()
                time.sleep(3)
                continue
            if not self.current_summoner:
                if self.get_current_summoner():
                    print("✓ Connected to League client!")
                else:
                    time.sleep(2)
                    continue
            try:
                self.check_champion_select()
                self.check_in_game()
            except Exception as e:
                print(f"Error checking game state: {e}")
            time.sleep(1)

if __name__ == "__main__":
    if not RIOT_API_KEY:
        print("⚠️  Warning: RIOT_API_KEY environment variable not set")
        print("   (The script will still work for basic client detection)")

    monitor = LoLClientMonitor()
    try:
        monitor.monitor()
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
        monitor.leave_voice_channel()
