from web3 import Web3
from dotenv import load_dotenv
from morpho import MorphoBlue, MetaMorpho
import os
import time


load_dotenv()


def main():
    print("Starting MetaMorpho")
    start_time = time.time()
    print("Start Time: ", start_time)
    # Connect to web3
    web3 = Web3(Web3.HTTPProvider(os.environ.get("WEB3_HTTP_PROVIDER")))
    if not web3.isConnected():
        raise Exception("Issue to connect to Web3")

    # init morpho
    # morpho = MorphoBlue(web3, os.environ.get('MORPHO_BLUE'), os.environ.get('MORPHO_BLUE_MARKETS'))
    vault = MetaMorpho(web3, os.environ.get("META_MORPHO"))
    vault.summary()
    print("End Time: ", time.time())
    print("Total Time: ", time.time() - start_time)


if __name__ == "__main__":
    main()
