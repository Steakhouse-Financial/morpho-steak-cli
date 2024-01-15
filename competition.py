import os
import json
from web3 import Web3

def aaveV3Rates(web3, token, nbBlocks = 50):
    address = os.environ.get('AAVE_V3_POOL')
    contract = web3.eth.contract(address=web3.toChecksumAddress(address), abi=json.load(open('abis/aave_v3_pool.json')))
    currentBlock = web3.eth.get_block_number()
    logs = contract.events.ReserveDataUpdated().createFilter(fromBlock=currentBlock - nbBlocks, argument_filters={'reserve':token}).get_all_entries()
    cnt = len(logs)

    if cnt == 0:
        logs = contract.events.ReserveDataUpdated().createFilter(fromBlock=currentBlock - nbBlocks*10, argument_filters={'reserve':token}).get_all_entries()
        cnt = len(logs)


    borrowRate = 0
    supplyRate = 0

    for log in logs:
        #print(log)
        borrowRate += log.args.variableBorrowRate / pow(10, 27)
        supplyRate += log.args.liquidityRate / pow(10, 27)

    borrowRate = borrowRate / cnt
    supplyRate = supplyRate / cnt
    return (supplyRate, borrowRate, cnt)


def sparkRates(web3, token = "0x6b175474e89094c44da98b954eedeac495271d0f", nbBlocks = 1000):
    address = os.environ.get('SPARK_POOL')
    contract = web3.eth.contract(address=web3.toChecksumAddress(address), abi=json.load(open('abis/aave_v3_pool.json')))
    currentBlock = web3.eth.get_block_number()
    logs = contract.events.ReserveDataUpdated().createFilter(fromBlock=currentBlock - nbBlocks, argument_filters={'reserve':token}).get_all_entries()
    cnt = len(logs)

    if cnt == 0:
        logs = contract.events.ReserveDataUpdated().createFilter(fromBlock=currentBlock - nbBlocks*10, argument_filters={'reserve':token}).get_all_entries()
        cnt = len(logs)


    borrowRate = 0
    supplyRate = 0

    for log in logs:
        #print(log)
        borrowRate += log.args.variableBorrowRate / pow(10, 27)
        supplyRate += log.args.liquidityRate / pow(10, 27)

    borrowRate = borrowRate / cnt
    supplyRate = supplyRate / cnt
    return (supplyRate, borrowRate, cnt)