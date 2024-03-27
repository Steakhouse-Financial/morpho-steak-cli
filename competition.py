import os
import json


def aave_v3_rates(web3, token, nbBlocks=50):
    address = os.environ.get("AAVE_V3_POOL")
    contract = web3.eth.contract(
        address=web3.to_checksum_address(address),
        abi=json.load(open("abis/aave_v3_pool.json")),
    )
    currentBlock = web3.eth.get_block_number()
    logs = (
        contract.events.ReserveDataUpdated()
        .create_filter(
            fromBlock=currentBlock - nbBlocks, argument_filters={"reserve": token}
        )
        .get_all_entries()
    )
    cnt = len(logs)

    if cnt == 0:
        logs = (
            contract.events.ReserveDataUpdated()
            .create_filter(
                fromBlock=currentBlock - nbBlocks * 10,
                argument_filters={"reserve": token},
            )
            .get_all_entries()
        )
        cnt = len(logs)
        if cnt == 0:
            print(f"Error: No logs found for {token}")
            return (0, 0, 0)

    borrow_rate = 0
    supply_rate = 0

    for log in logs:
        borrow_rate += log.args.variableBorrowRate / pow(10, 27)
        supply_rate += log.args.liquidityRate / pow(10, 27)

    borrow_rate = borrow_rate / cnt
    supply_rate = supply_rate / cnt
    return (supply_rate, borrow_rate, cnt)


def spark_rates(
    web3, token="0x6b175474e89094c44da98b954eedeac495271d0f", nbBlocks=1000
):
    address = os.environ.get("SPARK_POOL")
    contract = web3.eth.contract(
        address=web3.to_checksum_address(address),
        abi=json.load(open("abis/aave_v3_pool.json")),
    )
    currentBlock = web3.eth.get_block_number()
    logs = (
        contract.events.ReserveDataUpdated()
        .create_filter(
            fromBlock=currentBlock - nbBlocks, argument_filters={"reserve": token}
        )
        .get_all_entries()
    )
    cnt = len(logs)

    if cnt == 0:
        logs = (
            contract.events.ReserveDataUpdated()
            .create_filter(
                fromBlock=currentBlock - nbBlocks * 10,
                argument_filters={"reserve": token},
            )
            .get_all_entries()
        )
        cnt = len(logs)

    if cnt == 0:
        print(f"Error: No logs found for {token}")
        return (0, 0, 0)

    borrow_rate = 0
    supply_rate = 0

    for log in logs:
        # print(log)
        borrow_rate += log.args.variableBorrowRate / pow(10, 27)
        supply_rate += log.args.liquidityRate / pow(10, 27)

    borrow_rate = borrow_rate / cnt
    supply_rate = supply_rate / cnt
    return (supply_rate, borrow_rate, cnt)
