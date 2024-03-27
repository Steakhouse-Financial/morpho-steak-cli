from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import datetime
import os

from utils.cache import (
    cache_morpho_details,
    cache_token_details,
    get_morpho_details,
    get_token_details,
)

from .morphoblue import MorphoBlue


class MetaMorpho:
    def __init__(self, web3, address):
        self.abi = json.load(open("abis/metamorpho.json"))
        self.address = web3.to_checksum_address(address)
        self.contract = web3.eth.contract(address=self.address, abi=self.abi)

        cached_details_morpho = get_morpho_details(self.address)

        # todo: ensure these details will not changes
        if not cached_details_morpho:
            # MORPHO() call
            morpho_address = self.contract.functions.MORPHO().call()
            self.symbol = self.contract.functions.symbol().call()
            self.name = self.contract.functions.name().call()
            self.asset = self.contract.functions.asset().call()

            # Cache the details into the morpho cache json
            cache_morpho_details(
                self.address,
                {
                    "morpho_address": morpho_address,
                    "symbol": self.symbol,
                    "name": self.name,
                    "asset": self.asset,
                },
            )

        else:
            # Use the cached details
            morpho_address = cached_details_morpho["morphoAddress"]
            self.symbol = cached_details_morpho["symbol"]
            self.name = cached_details_morpho["name"]
            self.asset = cached_details_morpho["asset"]

        # todo: ensure these details will not changes
        cached_details_tokens = get_token_details(self.asset)
        if not cached_details_tokens:
            # Fetch the details because they're not in the cache
            self.asset_contract = web3.eth.contract(
                address=self.asset, abi=json.load(open("abis/erc20.json"))
            )
            self.asset_decimals = self.asset_contract.functions.decimals().call()
            self.asset_symbol = self.asset_contract.functions.symbol().call()
            self.asset_factor = pow(10, self.asset_decimals)
            # Cache these details for future use
            cache_token_details(
                self.asset,
                {
                    "decimals": self.asset_decimals,
                    "symbol": self.asset_symbol,
                    "factor": pow(10, self.asset_decimals),
                },
            )
        else:
            # Use the cached details
            self.asset_decimals = cached_details_tokens["decimals"]
            self.asset_symbol = cached_details_tokens["symbol"]
            self.asset_factor = cached_details_tokens["factor"]

        self.blue = MorphoBlue(web3, morpho_address, "")
        self.init_markets()

    def fetch_market_data(self, market):
        position = market.position(self.address)
        market_data = market.market_data()
        return (market, position, market_data)

    def total_assets(self):
        return self.contract.functions.totalAssets().call() / pow(
            10, self.asset_decimals
        )

    # separate to allow for a thread call
    def fetch_market(self, index):
        """Fetch and add a single market by index."""
        market = self.blue.add_market(
            self.contract.functions.withdrawQueue(index).call()
        )
        return market

    def init_markets(self):
        self.markets = []
        nb = self.contract.functions.withdrawQueueLength().call()

        # use a thread executor to fetch all markets in parallel
        with ThreadPoolExecutor(
            max_workers=os.environ.get("MAX_WORKERS", 10)
        ) as executor:
            future_to_index = {
                executor.submit(self.fetch_market, i): i for i in range(nb)
            }
            # as futures complete, add markets to the self.markets list
            for future in as_completed(future_to_index):
                market = future.result()
                self.markets.append(market)

    def get_market_by_collateral(self, collateral):
        for m in self.markets:
            if collateral == m.collateral_token_symbol:
                return m
        print(f"Market with collateral {collateral} doesn't exist for the MetaMorpho")

    def get_idle_market(self):
        return list(filter(lambda x: x.is_idle_market(), self.markets))[0]

    def has_idle_market(self):
        return len(list(filter(lambda x: x.is_idle_market(), self.markets))) > 0

    def get_borrow_markets(self):
        return filter(lambda x: not x.is_idle_market(), self.markets)

    def summary(self):
        total_assets = self.total_assets()
        now = datetime.datetime.now()
        print(
            f"{self.symbol} - {self.name} - Assets: {total_assets:,.2f} - {now:%H:%M:%S}"
        )
        vault_rate = 0.0
        liquidity = 0.0

        # Get data in parallel
        with ThreadPoolExecutor(
            max_workers=os.environ.get("MAX_WORKERS", 10)
        ) as executor:
            futures = [
                executor.submit(self.fetch_market_data, m)
                for m in self.markets
                if not m.is_idle_market()
            ]
            for future in as_completed(futures):
                try:
                    market, position, market_data = future.result()
                    vault_rate += market_data.supply_rate * position.supply_assets
                    share = (
                        position.supply_assets / total_assets * 100.0
                        if total_assets
                        else 0
                    )
                    metaRepresent = (
                        position.supply_assets / market_data.total_supply_assets * 100.0
                        if market_data.total_supply_assets
                        else 0
                    )
                    liquidity += (
                        market_data.total_supply_assets
                        - market_data.total_borrow_assets
                    )
                    print(
                        f"{market.name()} - rates: {market_data.supply_rate*100.0:.2f}%/{market_data.borrow_rate*100.0:.2f}%[{market_data.borrow_rate_at_target*100.0:.2f}%] "
                        f"exposure: {position.supply_assets:,.0f} ({share:.1f}%), util: {market_data.utilization*100.0:.1f}%, vault %: {metaRepresent:.1f}% "
                    )
                except Exception as exc:
                    print(f"Market data fetch generated an exception: {exc}")

        if self.has_idle_market():
            m = self.get_idle_market()
            position = m.position(self.address)
            market_data = m.market_data()
            vault_rate += market_data.supply_rate * position.supply_assets
            share = position.supply_assets / total_assets * 100.0 if total_assets else 0
            metaRepresent = (
                position.supply_assets / market_data.total_supply_assets * 100.0
                if market_data.total_supply_assets
                else 0
            )
            liquidity += (
                market_data.total_supply_assets - market_data.total_borrow_assets
            )
            print(
                f"{m.name()} - "
                + f"exposure: {position.supply_assets:,.0f} ({share:.1f}%), vault %: {metaRepresent:.1f}%"
            )

        if total_assets > 0:
            vault_rate = vault_rate / total_assets
        else:
            vault_rate = 0.0
        print(
            f"{self.symbol} rate {vault_rate*100.0:.2f}%, total liquidity {liquidity:,.0f}"
        )

    def rate(self):
        total_assets = self.total_assets()
        vault_rate = 0.0
        for m in self.get_borrow_markets():
            position = m.position(self.address)
            market_data = m.market_data()
            vault_rate += market_data.supply_rate * position.supply_assets

        vault_rate = vault_rate / total_assets
        return vault_rate
