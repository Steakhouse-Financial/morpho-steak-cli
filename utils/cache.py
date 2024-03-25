import json
import os

current_dir = os.path.dirname(os.path.abspath(__file__))

token_cache_file_path = os.path.join(current_dir, "..", "data", "token_cache.json")
morpho_cache_file_path = os.path.join(current_dir, "..", "data", "morpho_cache.json")


def load_tokens_cache():
    try:
        with open(token_cache_file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_morpho_cache():
    try:
        with open(morpho_cache_file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_token_cache(cache):
    with open(token_cache_file_path, "w") as file:
        json.dump(cache, file)


def save_morpho_cache(cache):
    with open(morpho_cache_file_path, "w") as file:
        json.dump(cache, file)


def get_token_details(address):
    cache = load_tokens_cache()
    return cache.get(address)


def get_morpho_details(address):
    cache = load_morpho_cache()
    return cache.get(address)


def cache_token_details(address, details):
    cache = load_tokens_cache()
    cache[address] = details
    save_token_cache(cache)


def cache_morpho_details(address, details):
    cache = load_morpho_cache()
    cache[address] = details
    save_morpho_cache(cache)
