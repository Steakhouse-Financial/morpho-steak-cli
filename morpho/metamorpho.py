from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import datetime
import time

from utils.cache import cache_token_details, get_token_details

from .morphomarket import MorphoMarket, Position
from .morphoblue import MorphoBlue


class MetaMorpho:
    def __init__(self, web3, address):
        # Start of the initialization process
        init_start_time = time.time()
        # All the below are super fast
        self.abi = json.load(open("abis/metamorpho.json"))
        self.address = web3.to_checksum_address(address)
        self.contract = web3.eth.contract(address=self.address, abi=self.abi)
        print(f"Initialized MetaMorpho contract at {self.address}")
        print(f"Contract = {self.contract}")

        # MORPHO() call
        morpho_call_start_time = time.time()
        morphoAddress = self.contract.functions.MORPHO().call()
        morpho_call_end_time = time.time()
        print(
            f"MORPHO() call took {morpho_call_end_time - morpho_call_start_time:.2f} seconds, morphoAddress: {morphoAddress}"
        )

        # symbol() call
        symbol_call_start_time = time.time()
        self.symbol = self.contract.functions.symbol().call()
        symbol_call_end_time = time.time()
        print(
            f"symbol() call took {symbol_call_end_time - symbol_call_start_time:.2f} seconds, symbol = {self.symbol}"
        )

        # name() call
        name_call_start_time = time.time()
        self.name = self.contract.functions.name().call()
        name_call_end_time = time.time()
        print(
            f"name() call took {name_call_end_time - name_call_start_time:.2f} seconds, name = {self.name}"
        )

        # asset() call
        asset_call_start_time = time.time()
        self.asset = self.contract.functions.asset().call()
        asset_call_end_time = time.time()
        print(
            f"asset() call took {asset_call_end_time - asset_call_start_time:.2f} seconds, asset = {self.asset}"
        )

        # Final print statement for the entire initialization process
        init_end_time = time.time()
        print(f"MetaMorpho init took {init_end_time - init_start_time:.2f} seconds")
        print(
            f"Initialization completed at {datetime.datetime.fromtimestamp(init_end_time).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        self.token_details_start = time.time()

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

        self.token_details_end = time.time()
        print(
            f"MetaMorpho variable init took {self.token_details_end - self.token_details_start:.2f} seconds"
        ),
        self.morpho_blue_init_start = time.time()
        self.blue = MorphoBlue(web3, morphoAddress, "")
        self.morpho_blue_init = time.time()
        print(
            f"MetaMorpho blue init took {self.morpho_blue_init - self.morpho_blue_init_start:.2f} seconds"
        ),
        self.initMarkets()
        self.morpho_init_markets = time.time()
        print(
            f"MetaMorpho init markets took {self.morpho_init_markets - self.morpho_blue_init:.2f} seconds"
        ),

    def fetch_market_data(self, market):
        start_time = datetime.datetime.now()
        position = market.position(self.address)
        marketData = market.marketData()
        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
        return (market, position, marketData, elapsed_time)

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
        self.nb_start_time = time.time()
        nb = self.contract.functions.withdrawQueueLength().call()
        self.nb_end_time = time.time()
        print(
            f"MetaMorpho get nb took {self.nb_end_time - self.nb_start_time:.2f} seconds"
        ),
        print(f"MetaMorpho has {nb} markets")

        # use a thread executor to fetch all markets in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all market fetch tasks
            future_to_index = {
                executor.submit(self.fetch_market, i): i for i in range(nb)
            }
            # As futures complete, add markets to the self.markets list
            for future in as_completed(future_to_index):
                market = future.result()
                self.markets.append(market)

        print(f"Initialized {len(self.markets)} markets")

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
        start = datetime.datetime.now()
        print(f"Starting at {start:%Y-%m-%d %H:%M:%S}")
        print(
            f"{self.symbol} - {self.name} - Assets: {totalAssets:,.2f} - {start:%H:%M:%S}"
        )
        vaultRate = 0.0
        liquidity = 0.0

        # Get data in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(self.fetch_market_data, m)
                for m in self.markets
                if not m.isIdleMarket()
            ]
            for future in as_completed(futures):
                try:
                    market, position, marketData, elapsed_time = future.result()
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
                        f"{market.name()} - rates: {marketData.supplyRate*100.0:.2f}%/{marketData.borrowRate*100.0:.2f}% "
                        f"exposure: {position.supplyAssets:,.0f} ({share:.1f}%), util: {marketData.utilization*100.0:.1f}%, vault %: {metaRepresent:.1f}% "
                        f"Time taken: {elapsed_time:.2f} seconds"
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

        vaultRate = vaultRate / totalAssets
        print(
            f"{self.symbol} rate {vaultRate*100.0:.2f}%, total liquidity {liquidity:,.0f}"
        )
        end = datetime.datetime.now()
        time_elapsed = end - start
        print(f"Ending at {end:%Y-%m-%d %H:%M:%S}")
        print(f"Time Elapsed: {time_elapsed}")

    def rate(self):
        totalAssets = self.totalAssets()
        vaultRate = 0.0
        for m in self.getBorrowMarkets():
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets

        vaultRate = vaultRate / totalAssets
        return vaultRate
