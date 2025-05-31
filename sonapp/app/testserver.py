import requests
import json
import time
import base64
import psutil
import re
import os
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv
load_dotenv()
# Disable SSL warnings since LCU uses self-signed certificates
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Your Riot API key
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

class LoLClientMonitor:
    def __init__(self):
        self.lcu_port = None
        self.lcu_token = None
        self.lcu_headers = None
        self.current_summoner = None
        self.last_game_state = None
        self.in_champ_select = False
        self.in_game = False
        
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
                        
        elif not (game_session and game_session.get('phase') == 'InProgress') and self.in_game:
            self.in_game = False
            print("❌ Game ended")
    
    def monitor(self):
        """Main monitoring loop"""
        print("🔍 Looking for League of Legends client...")
        
        while True:
            # Check if client is running
            if not self.find_lcu_credentials():
                if self.current_summoner:
                    print("❌ League client closed")
                    self.current_summoner = None
                    self.in_champ_select = False
                    self.in_game = False
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

if __name__ == "__main__":
    if not RIOT_API_KEY:
        print("⚠️  Warning: RIOT_API_KEY environment variable not set")
        print("   (The script will still work for basic client detection)")
    
    monitor = LoLClientMonitor()
    try:
        monitor.monitor()
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")