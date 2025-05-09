import json
import pandas as pd
from config import DATA_PATH, REQUEST_FILE, TRAVEL_MATRIX_FILE


def load_json_file(filename):
    """Load a JSON file from the configured data path."""
    with open(DATA_PATH + filename) as f:
        return json.load(f)
    

def load_all_data():
    """Load request data and travel matrix."""
    data = load_json_file(REQUEST_FILE)
    travel_matrix = load_json_file(TRAVEL_MATRIX_FILE)
    return data, travel_matrix


