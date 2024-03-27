from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from morpho.utils import POW_10_18
from morpho.utils import rateToTargetRate
from dataclasses import dataclass
import time

from utils.cache import cache_token_details, get_token_details


@dataclass
class Position:
    address: str
    supplyShares: float
    supplyAssets: float
    borrowShares: float
    borrowAssets: float
    collateral: float
    collateralValue: float
    collateralPrice: float
    ltv: float
    healthRatio: float


@dataclass
class MaketData:
    totalSupplyAssets: float
    totalSupplyShares: float
    totalBorrowAssets: float
    totalBorrowShares: float
    fee: float
    utilization: float
    supplyRate: float
    borrowRate: float
    borrowRateAtTarget: float


class MorphoMarket:
    def __init__(self, web3, blue, id):
        self.web3 = web3
        self.blue = blue
        self.id = id
        params = blue.marketParams(id)
        self.params = params

        if params.irm != "0x0000000000000000000000000000000000000000":
            self.irmContract = web3.eth.contract(
                address=web3.to_checksum_address(params.irm),
                abi=json.load(open("abis/irm.json")),
            )

        if params.oracle != "0x0000000000000000000000000000000000000000":
            self.oracleContract = web3.eth.contract(
                address=web3.to_checksum_address(params.oracle),
                abi=json.load(open("abis/oracle.json")),
            )
        self.lastOracleUpdate = 0
        self.lltv = self.params.lltv / POW_10_18

        # Get some data from erc20
        self.collateralToken = params.collateralToken
        cached_details_collateral = get_token_details(self.collateralToken)
        if (
            self.collateralToken != "0x0000000000000000000000000000000000000000"
            and not cached_details_collateral
        ):
            self.collateralTokenContract = web3.eth.contract(
                address=web3.to_checksum_address(params.collateralToken),
                abi=json.load(open("abis/erc20.json")),
            )
            self.collateralTokenDecimals = (
                self.collateralTokenContract.functions.decimals().call()
            )
            self.collateralTokenFactor = pow(10, self.collateralTokenDecimals)
            self.collateralTokenSymbol = (
                self.collateralTokenContract.functions.symbol().call()
            )
            # Cache the new token details
            cache_token_details(
                self.collateralToken,
                {
                    "decimals": self.collateralTokenDecimals,
                    "factor": self.collateralTokenFactor,
                    "symbol": self.collateralTokenSymbol,
                },
            )
        elif cached_details_collateral:
            self.collateralTokenDecimals = cached_details_collateral["decimals"]
            self.collateralTokenFactor = cached_details_collateral["factor"]
            self.collateralTokenSymbol = cached_details_collateral["symbol"]
        else:
            self.collateralTokenSymbol = "Idle"

        self.loanToken = params.loanToken
        cached_details_loan = get_token_details(self.loanToken)
        if not cached_details_loan:
            self.loanTokenContract = web3.eth.contract(
                address=web3.to_checksum_address(params.loanToken),
                abi=json.load(open("abis/erc20.json")),
            )
            self.loanTokenDecimals = self.loanTokenContract.functions.decimals().call()
            self.loanTokenSymbol = self.loanTokenContract.functions.symbol().call()
            self.loanTokenFactor = pow(10, self.loanTokenDecimals)

            cache_token_details(
                self.loanToken,
                {
                    "decimals": self.loanTokenDecimals,
                    "factor": self.loanTokenFactor,
                    "symbol": self.loanTokenSymbol,
                },
            )
        else:
            self.loanTokenDecimals = cached_details_loan["decimals"]
            self.loanTokenSymbol = cached_details_loan["symbol"]
            self.loanTokenFactor = cached_details_loan["factor"]

        # Cache elements

        self.lastRate = 0
        self.lastRateUpdate = 0
        self.lastMarketData = None
        self.lastMarketDataUpdate = 0

    def isIdleMarket(self):
        return self.collateralToken == "0x0000000000000000000000000000000000000000"

    def name(self):
        return "{0}[{1}]".format(self.loanTokenSymbol, self.collateralTokenSymbol)

    def borrowRate(self):
        return self.marketData().borrowRate

    def rateAtTarget(self):
        return self.marketData().borrowRateAtTarget

    def _marketData(self):
        if time.time() < self.lastMarketDataUpdate + 5:
            return self.lastMarketData
        self.lastMarketData = self.blue.marketData(self.id)
        self.lastMarketDataUpdate = time.time()
        return self.lastMarketData

    def marketParams(self):
        return self.params

    def marketData(self):
        (
            totalSupplyAssets,
            totalSupplyShares,
            totalBorrowAssets,
            totalBorrowShares,
            fee,
            utilization,
            supplyRate,
            borrowRate,
        ) = self._marketData()

        if self.isIdleMarket():
            return MaketData(
                totalSupplyAssets / self.loanTokenFactor,
                totalSupplyShares / POW_10_18,
                totalBorrowAssets / self.loanTokenFactor,
                totalBorrowShares / POW_10_18,
                fee,
                0,
                0,
                0,
                0,
            )

        borrowRate = borrowRate / POW_10_18
        rateAtTarget = rateToTargetRate(borrowRate, utilization / POW_10_18)
        supplyRate = (
            borrowRate * totalBorrowAssets / totalSupplyAssets
            if totalSupplyAssets
            else 0
        )  # TODO: Don't work with fees

        return MaketData(
            totalSupplyAssets / self.loanTokenFactor,
            totalSupplyShares / POW_10_18,
            totalBorrowAssets / self.loanTokenFactor,
            totalBorrowShares / POW_10_18,
            fee,
            totalBorrowAssets / totalSupplyAssets if totalSupplyAssets else 0,
            supplyRate,
            borrowRate,
            rateAtTarget,
        )

    def position(self, address):
        (
            suppliedShares,
            suppliedAssets,
            borrowedShares,
            borrowedAssets,
            collateral,
            collateralValue,
            ltv,
            healthRatio,
        ) = self.blue.reader.functions.getPosition(
            self.id, self.web3.to_checksum_address(address)
        ).call()

        if self.isIdleMarket():
            return Position(
                address,
                suppliedShares / POW_10_18,
                suppliedAssets / self.loanTokenFactor,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )

        return Position(
            address,
            suppliedShares / POW_10_18,
            suppliedAssets / self.loanTokenFactor,
            borrowedShares / POW_10_18,
            borrowedAssets / self.loanTokenFactor,
            collateral / self.collateralTokenFactor,
            collateralValue / self.loanTokenFactor,
            (
                (collateralValue / self.loanTokenFactor)
                / (collateral / self.collateralTokenFactor)
                if collateral > 0
                else 0
            ),
            ltv / POW_10_18,
            healthRatio / POW_10_18,
        )

    def collateralPrice(self):
        # todo: this oracle pricing is giving old and wrong results
        lastUpdate = getattr(self, "lastOracleUpdate", None)
        if lastUpdate is None or time.time() > lastUpdate + 5:
            self.lastOracleUpdate = time.time()
            self.oraclePrice = self.oracleContract.functions.price().call() / (
                # Look at this for the decimals
                self.loanTokenFactor * self.collateralTokenFactor
            )
        return self.oraclePrice

    def borrowers(self):
        def fetch_position(borrower):
            return self.position(borrower)

        borrowers = []
        with ThreadPoolExecutor(
            max_workers=os.environ.get("MAX_WORKERS", 10)
        ) as executor:
            # Create a future for each borrower
            future_to_borrower = {
                executor.submit(fetch_position, b): b
                for b in self.blue.borrowers(self.id)
            }

            for future in as_completed(future_to_borrower):
                try:
                    borrower_position = future.result()
                    borrowers.append(borrower_position)
                except Exception as exc:
                    print(f"An error occurred: {exc}")

        # Sort the borrowers by LTV in reverse order
        return sorted(borrowers, key=lambda p: p.ltv, reverse=True)
