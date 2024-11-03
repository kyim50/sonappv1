import requests
import json

# Riot API Details
RIOT_API_KEY = "YOUR_RIOT_API_KEY"  # Replace with your Riot API key
REGION = "na1"  # Set your Riot region

def get_game_state(summoner_id):
    """
    Check if the specified summoner is in a game.
    
    Args:
        summoner_id (str): Riot summoner ID of the player.

    Returns:
        dict: Game information if in a game, None otherwise.
    """
    url = f"https://{REGION}.api.riotgames.com/lol/spectator/v4/active-games/by-summoner/{summoner_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()  # Returns game data if in a game
        elif response.status_code == 404:
            return None  # Summoner is not currently in a game
        else:
            print(f"Error fetching game state: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error in get_game_state: {e}")
        return None

def get_team_members_with_app(game_data, app_users):
    """
    Identify which teammates are also running the app based on the current game data.
    
    Args:
        game_data (dict): JSON data of the current game from Riot's API.
        app_users (list): List of players known to have the app running.
    
    Returns:
        list: List of summoner names of team members with the app.
    """
    if not game_data:
        return []

    summoner_names_with_app = []
    for participant in game_data['participants']:
        summoner_name = participant['summonerName']
        team_id = participant['teamId']

        # Check if this summoner is running the app
        if summoner_name in app_users:
            summoner_names_with_app.append({
                "summonerName": summoner_name,
                "teamId": team_id
            })

    # Filter by the user’s team only
    user_team_id = next(
        (participant['teamId'] for participant in game_data['participants'] if participant['summonerName'] in app_users),
        None
    )
    if user_team_id:
        return [member for member in summoner_names_with_app if member["teamId"] == user_team_id]
    return []

def fetch_app_users():
    """
    Mock function or placeholder for fetching a list of users who have the app running.
    
    Returns:
        list: List of summoner names of players running the app.
    """
    # This would likely query a central server or use a peer-to-peer discovery mechanism
    # For now, we return a static list for testing
    return ["Summoner1", "Summoner2", "Summoner3"]

# Example usage
if __name__ == "__main__":
    # Replace with an actual summoner ID for testing
    test_summoner_id = "SOME_SUMMONER_ID"
    game_data = get_game_state(test_summoner_id)

    if game_data:
        app_users = fetch_app_users()  # List of app users, normally fetched dynamically
        teammates_with_app = get_team_members_with_app(game_data, app_users)
        print("Teammates with the app running:", teammates_with_app)
    else:
        print("User is not currently in a game.")
