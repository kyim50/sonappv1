# app/ptt_manager.py
import keyboard

is_ptt_active = False

def toggle_ptt():
    """Toggle Push-to-Talk status."""
    global is_ptt_active
    is_ptt_active = not is_ptt_active
    print("PTT is now", "Active" if is_ptt_active else "Inactive")

def setup_ptt_key():
    """Set up the key for Push-to-Talk."""
    keyboard.add_hotkey('ctrl', toggle_ptt)
