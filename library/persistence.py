import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PERSISTENCE_FILE = os.path.join(DATA_DIR, "strip_state.json")

def load_strip_state():
    """Load the persisted strip state and color from disk.

    Creates the data directory and a default state file if none exists.

    Returns:
        dict: Mapping with "state" (str) and "color" (str RGB tuple) keys.
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if os.path.exists(PERSISTENCE_FILE):
        with open(PERSISTENCE_FILE, "r") as f:
            return json.load(f)
    # Default values if file does not exist
    default_data = {"state": "off", "color": '(0, 0, 0)'}
    with open(PERSISTENCE_FILE, "w") as f:
        json.dump(default_data, f)
    return default_data

def save_strip_state(state, color):
    """Persist the given strip state and color to disk as JSON.

    Args:
        state (str): On/off state to store.
        color (str): RGB color (stringified tuple) to store.
    """
    with open(PERSISTENCE_FILE, "w") as f:
        json.dump({"state": state, "color": color}, f)
