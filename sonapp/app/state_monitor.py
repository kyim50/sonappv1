# app/state_monitor.py
import time
import riot_api
import voice_channel
import audio_handler  # Import the audio handler

def start_monitoring():
    """Monitor the League of Legends client state."""
    summoner_name = "YourSummonerName"  # Replace with actual summoner name
    summoner = riot_api.get_summoner_by_name(summoner_name)

    if summoner:
        audio_handler.start_audio_communication()  # Start audio communication

        while True:
            current_game = riot_api.get_current_game(summoner['id'])
            if current_game:
                voice_channel.create_voice_channel(current_game['gameId'])
            else:
                voice_channel.close_voice_channel(summoner['id'])

            time.sleep(10)  # Poll every 10 seconds
