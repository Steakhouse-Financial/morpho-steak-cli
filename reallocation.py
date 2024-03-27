# Testing script for the reallocation stuff
from morpho import MetaMorpho, MorphoMarket, MarketRewards, rewards_for_market, Position
from morpho import AllocationItem, Allocation, ReallocationStrategy
from web3 import Web3
import os
from dotenv import load_dotenv

from morpho.reallocation_strategy import reallocation_params
from morpho.strategy_equal_yield import StrategyEqualYield


def is_active_market(vault: MetaMorpho, market: MorphoMarket) -> bool:
    """Return true is the market is active (some meaningfule exposure)"""
    # return market.position(vault.address).supplyAssets > 1
    return market.marketData().totalSupplyAssets > 100


def market_to_allocation_item(
    vault: MetaMorpho, market: MorphoMarket
) -> AllocationItem:
    """Convert a market to an AllocationItem"""
    rewards = rewards_for_market(market.id)
    position = market.position(vault.address)
    data = market.marketData()
    return AllocationItem(
        market,
        rewards,
        position.supplyAssets,
        data.totalSupplyAssets,
        data.totalBorrowAssets,
        data.borrowRateAtTarget,
    )


def vault_to_allocation(vault: MetaMorpho) -> Allocation:
    """Take a MetaMorpho vault and return an Allocation object"""
    # Filter to keep only market where there is an allocation
    items = [
        market_to_allocation_item(vault, m)
        for m in vault.markets
        if is_active_market(vault, m)
    ]
    return Allocation(items)


def main():
    load_dotenv()
    web3 = Web3(Web3.HTTPProvider(os.environ.get("WEB3_HTTP_PROVIDER")))
    if not web3.is_connected():
        raise Exception("Issue to connect to Web3")
    if os.environ.get("META_MORPHO") == "":
        raise Exception("Need a META_MORPHO env var")

    vault = MetaMorpho(web3, os.environ.get("META_MORPHO"))
    print(os.environ.get("META_MORPHO"))

    allocation = vault_to_allocation(vault)
    print(allocation)
    print("\n")

    strategy = StrategyEqualYield()

    winner = strategy.reallocate(allocation)
    print("Reallocation\n")
    print(winner)
    print("\n")

    print("Params\n")
    print(reallocation_params(allocation, winner))


if __name__ == "__main__":
    main()
