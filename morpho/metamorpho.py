from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import datetime
import os
import time

from utils.cache import (
    cache_morpho_details,
    cache_token_details,
    get_morpho_details,
    get_token_details,
)

from .morphomarket import MorphoMarket, Position
from .morphoblue import MorphoBlue


class MetaMorpho:
    def __init__(self, web3, address):

        self.abi = json.load(open("abis/metamorpho.json"))
        self.address = web3.to_checksum_address(address)
        self.contract = web3.eth.contract(address=self.address, abi=self.abi)

        cached_details_morpho = get_morpho_details(self.address)

        if not cached_details_morpho:
            # MORPHO() call
            morphoAddress = self.contract.functions.MORPHO().call()
            self.symbol = self.contract.functions.symbol().call()
            self.name = self.contract.functions.name().call()
            self.asset = self.contract.functions.asset().call()

            # Cache the details into the morpho cache json
            cache_morpho_details(
                self.address,
                {
                    "morphoAddress": morphoAddress,
                    "symbol": self.symbol,
                    "name": self.name,
                    "asset": self.asset,
                },
            )

        else:
            # Use the cached details
            morphoAddress = cached_details_morpho["morphoAddress"]
            self.symbol = cached_details_morpho["symbol"]
            self.name = cached_details_morpho["name"]
            self.asset = cached_details_morpho["asset"]

        cached_details = get_token_details(self.asset)
        if not cached_details:
            # Fetch the details because they're not in the cache
            self.assetContract = web3.eth.contract(
                address=self.asset, abi=json.load(open("abis/erc20.json"))
            )
            self.assetDecimals = self.assetContract.functions.decimals().call()
            self.assetSymbol = self.assetContract.functions.symbol().call()
            self.assetFactor = pow(10, self.assetDecimals)
            # Cache these details for future use
            cache_token_details(
                self.asset,
                {
                    "decimals": self.assetDecimals,
                    "symbol": self.assetSymbol,
                    "factor": pow(10, self.assetDecimals),
                },
            )
        else:
            # Use the cached details
            self.assetDecimals = cached_details["decimals"]
            self.assetSymbol = cached_details["symbol"]

        self.blue = MorphoBlue(web3, morphoAddress, "")
        self.initMarkets()

    def fetch_market_data(self, market):
        position = market.position(self.address)
        marketData = market.marketData()
        return (market, position, marketData)

    def totalAssets(self):
        return self.contract.functions.totalAssets().call() / pow(
            10, self.assetDecimals
        )

    # separate to allow for a thread call
    def fetch_market(self, index):
        """Fetch and add a single market by index."""
        market = self.blue.addMarket(
            self.contract.functions.withdrawQueue(index).call()
        )
        return market

    def initMarkets(self):
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

    def getMarketByCollateral(self, collateral):
        for m in self.markets:
            if collateral == m.collateralTokenSymbol:
                return m
        print(f"Market with collateral {collateral} doesn't exist for the MetaMorpho")

    def getIdleMarket(self):
        return list(filter(lambda x: x.isIdleMarket(), self.markets))[0]

    def hasIdleMarket(self):
        return len(list(filter(lambda x: x.isIdleMarket(), self.markets))) > 0

    def getBorrowMarkets(self):
        return filter(lambda x: not x.isIdleMarket(), self.markets)

    def summary(self):
        totalAssets = self.totalAssets()
        now = datetime.datetime.now()
        print(
            f"{self.symbol} - {self.name} - Assets: {totalAssets:,.2f} - {now:%H:%M:%S}"
        )
        vaultRate = 0.0
        liquidity = 0.0

        # Get data in parallel
        with ThreadPoolExecutor(
            max_workers=os.environ.get("MAX_WORKERS", 10)
        ) as executor:
            futures = [
                executor.submit(self.fetch_market_data, m)
                for m in self.markets
                if not m.isIdleMarket()
            ]
            for future in as_completed(futures):
                try:
                    market, position, marketData = future.result()
                    vaultRate += marketData.supplyRate * position.supplyAssets
                    share = (
                        position.supplyAssets / totalAssets * 100.0
                        if totalAssets
                        else 0
                    )
                    metaRepresent = (
                        position.supplyAssets / marketData.totalSupplyAssets * 100.0
                        if marketData.totalSupplyAssets
                        else 0
                    )
                    liquidity += (
                        marketData.totalSupplyAssets - marketData.totalBorrowAssets
                    )
                    print(
                        f"{market.name()} - rates: {marketData.supplyRate*100.0:.2f}%/{marketData.borrowRate*100.0:.2f}%[{marketData.borrowRateAtTarget*100.0:.2f}%] "
                        f"exposure: {position.supplyAssets:,.0f} ({share:.1f}%), util: {marketData.utilization*100.0:.1f}%, vault %: {metaRepresent:.1f}% "
                    )
                except Exception as exc:
                    print(f"Market data fetch generated an exception: {exc}")

        if self.hasIdleMarket():
            m = self.getIdleMarket()
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets
            share = position.supplyAssets / totalAssets * 100.0 if totalAssets else 0
            metaRepresent = (
                position.supplyAssets / marketData.totalSupplyAssets * 100.0
                if marketData.totalSupplyAssets
                else 0
            )
            liquidity += marketData.totalSupplyAssets - marketData.totalBorrowAssets
            print(
                f"{m.name()} - "
                + f"exposure: {position.supplyAssets:,.0f} ({share:.1f}%), vault %: {metaRepresent:.1f}%"
            )

        if totalAssets > 0:
            vaultRate = vaultRate / totalAssets
        else:
            vaultRate = 0.0
        print(
            f"{self.symbol} rate {vaultRate*100.0:.2f}%, total liquidity {liquidity:,.0f}"
        )

    def rate(self):
        totalAssets = self.totalAssets()
        vaultRate = 0.0
        for m in self.getBorrowMarkets():
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets

        vaultRate = vaultRate / totalAssets
        return vaultRate
