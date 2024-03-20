import json
import os

current_dir = os.path.dirname(os.path.abspath(__file__))

cache_file_path = os.path.join(current_dir, "..", "data", "token_cache.json")


def load_cache():
    try:
        with open(cache_file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    with open(cache_file_path, "w") as file:
        json.dump(cache, file)


def get_token_details(address):
    cache = load_cache()
    return cache.get(address)


def cache_token_details(address, details):
    cache = load_cache()
    cache[address] = details
    save_cache(cache)
