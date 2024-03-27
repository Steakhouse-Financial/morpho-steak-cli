import json

abis = dict()

BASE_DIR = "abis/"

def getABI(name):
    return json.load(open('abis/erc20.json'))