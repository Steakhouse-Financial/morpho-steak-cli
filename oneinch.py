
from dotenv import load_dotenv
from requests.models import PreparedRequest
import requests
import os





#response = requests.get('https://api.1inch.dev/swap/v5.2/1/tokens', headers= headers)
#print(response.content)


def swapData(fromToken, toToken, amount, fromWallet):
    apiUrl = "https://api.1inch.dev/swap/v5.2/1/swap"
    
    headers = { 
        "accept":"application/json",
        "Authorization": "Bearer " + os.environ.get('1INCH_KEY')
        }
    
    print(str(amount))

    params = {
        "src":fromToken,
        "dst": toToken,
        "amount": str(amount),
        "from": fromWallet,
        "slippage": 1,
        "disableEstimate": "true",
        "allowPartialFill": "false",
        "includeTokensInfo": "true",
        "compatibility": "true",
    }
    response = requests.get(apiUrl, headers=headers, params=params)

    print(response.json())
    return response

