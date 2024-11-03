# app/audio_handler.py
import sounddevice as sd
import numpy as np

SAMPLE_RATE = 44100
CHANNELS = 1

def start_audio_stream(callback):
    """Start the audio stream with the given callback function."""
    return sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback)

def play_audio(indata):
    """Play the recorded audio."""
    sd.play(indata, SAMPLE_RATE)

def stop_audio_stream(stream):
    """Stop the audio stream."""
    stream.stop()
    stream.close()
