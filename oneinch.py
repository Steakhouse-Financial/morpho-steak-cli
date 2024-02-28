
from dotenv import load_dotenv
from requests.models import PreparedRequest
import requests
import os




from dotenv import load_dotenv

# load_dotenv()
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
        "amount": f"{amount:.0f}",
        "from": fromWallet,
        "slippage": 1,
        "disableEstimate": "true",
        "allowPartialFill": "false",
        "includeTokensInfo": "true",
        "compatibility": "true",
    }
    print(params)
    response = requests.get(apiUrl, headers=headers, params=params)

    print(response.json())
    return response

# swapData("0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0","0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 10*pow(10, 18), "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")