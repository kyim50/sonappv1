# app/riot_api.py
import requests

RIOT_API_KEY = 'YOUR_RIOT_API_KEY'  # Replace with your actual API key
BASE_URL = 'https://na1.api.riotgames.com'

def get_summoner_by_name(summoner_name):
    """Fetch summoner details by name."""
    url = f"{BASE_URL}/lol/summoner/v4/summoners/by-name/{summoner_name}"
    headers = {'X-Riot-Token': RIOT_API_KEY}
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else None

def get_current_game(summoner_id):
    """Fetch current game details."""
    url = f"{BASE_URL}/lol/spectator/v4/active-games/by-summoner/{summoner_id}"
    headers = {'X-Riot-Token': RIOT_API_KEY}
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else None
