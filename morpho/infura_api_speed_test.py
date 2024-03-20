import json
import os
import time
from web3 import Web3

web3 = Web3(Web3.HTTPProvider(os.environ.get("WEB3_HTTP_PROVIDER")))
if not web3.is_connected():
    raise Exception("Issue to connect to Web3")

# Begin collateral token processing
collateral_token_start_time = time.time()

collateralToken = (
    "0x2260FAC5E5542A773AA44FBCFEDF7C193BC2C599"  # Ensure it's a string for comparison
)
if collateralToken != "0x0000000000000000000000000000000000000000":
    collateralTokenContract = web3.eth.contract(
        address=web3.to_checksum_address(collateralToken),
        abi=json.load(open("abis/erc20.json")),
    )

    # Decimals
    decimals_start_time = time.time()
    collateralTokenDecimals = collateralTokenContract.functions.decimals().call()
    decimals_end_time = time.time()
    print(
        f"Fetching collateral token decimals took {decimals_end_time - decimals_start_time:.2f} seconds"
    )

    # Factor
    factor_start_time = time.time()
    collateralTokenFactor = pow(10, collateralTokenDecimals)
    factor_end_time = time.time()
    print(
        f"Calculating collateral token factor took {factor_end_time - factor_start_time:.2f} seconds"
    )

    # Symbol
    symbol_start_time = time.time()
    collateralTokenSymbol = collateralTokenContract.functions.symbol().call()
    symbol_end_time = time.time()
    print(
        f"Fetching collateral token symbol took {symbol_end_time - symbol_start_time:.2f} seconds"
    )

collateral_token_end_time = time.time()
print(
    f"Total collateral token processing took {collateral_token_end_time - collateral_token_start_time:.2f} seconds"
)
