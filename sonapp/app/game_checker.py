import requests

# Constants for the Live Client API
API_URL = "http://127.0.0.1:2999/liveclientdata/"
GAME_STATE_ENDPOINT = "activegame"  # Endpoint to check for active game

def get_game_state():
    """Check if the user is in a League of Legends game."""
    try:
        response = requests.get(f"{API_URL}{GAME_STATE_ENDPOINT}")
        if response.status_code == 200:
            game_data = response.json()
            # Check if game data exists
            if game_data:
                return "In Game"
            else:
                return "Not In Game"
        else:
            return "Error fetching game state"
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Live Client API: {e}"

if __name__ == "__main__":
    # For testing purposes
    state = get_game_state()
    print(f"Game State: {state}")
