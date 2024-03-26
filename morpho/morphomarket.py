from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from morpho.utils import POW_10_18
from morpho.utils import rate_to_target_rate
from dataclasses import dataclass
import time

from utils.cache import cache_token_details, get_token_details


@dataclass
class Position:
    address: str
    supply_shares: float
    supply_assets: float
    borrow_shares: float
    borrow_assets: float
    collateral: float
    collateral_value: float
    collateral_price: float
    ltv: float
    health_ratio: float


@dataclass
class MaketData:
    total_supply_assets: float
    total_supply_shares: float
    total_borrow_assets: float
    total_borrow_shares: float
    fee: float
    utilization: float
    supply_rate: float
    borrow_rate: float
    borrow_rate_at_target: float


class MorphoMarket:
    def __init__(self, web3, blue, id):
        self.web3 = web3
        self.blue = blue
        self.id = id
        params = blue.market_params(id)
        self.params = params

        if params.irm != "0x0000000000000000000000000000000000000000":
            self.irm_contract = web3.eth.contract(
                address=web3.to_checksum_address(params.irm),
                abi=json.load(open("abis/irm.json")),
            )

        if params.oracle != "0x0000000000000000000000000000000000000000":
            self.oracle_contract = web3.eth.contract(
                address=web3.to_checksum_address(params.oracle),
                abi=json.load(open("abis/oracle.json")),
            )
        self.last_oracle_update = 0
        self.lltv = self.params.lltv / POW_10_18

        # Get some data from erc20
        self.colateral_token = params.colateral_token
        cached_details_collateral = get_token_details(self.colateral_token)
        if (
            self.colateral_token != "0x0000000000000000000000000000000000000000"
            and not cached_details_collateral
        ):
            self.colateral_token_contract = web3.eth.contract(
                address=web3.to_checksum_address(params.colateral_token),
                abi=json.load(open("abis/erc20.json")),
            )
            self.colateral_token_decimals = (
                self.colateral_token_contract.functions.decimals().call()
            )
            self.colateral_token_factor = pow(10, self.colateral_token_decimals)
            self.collateral_token_symbol = (
                self.colateral_token_contract.functions.symbol().call()
            )
            # Cache the new token details
            cache_token_details(
                self.colateral_token,
                {
                    "decimals": self.colateral_token_decimals,
                    "factor": self.colateral_token_factor,
                    "symbol": self.collateral_token_symbol,
                },
            )
        elif cached_details_collateral:
            self.colateral_token_decimals = cached_details_collateral["decimals"]
            self.colateral_token_factor = cached_details_collateral["factor"]
            self.collateral_token_symbol = cached_details_collateral["symbol"]
        else:
            self.collateral_token_symbol = "Idle"

        self.loan_token = params.loan_token
        cached_details_loan = get_token_details(self.loan_token)
        if not cached_details_loan:
            self.loan_token_contract = web3.eth.contract(
                address=web3.to_checksum_address(params.loanToken),
                abi=json.load(open("abis/erc20.json")),
            )
            self.loan_token_decimals = (
                self.loan_token_contract.functions.decimals().call()
            )
            self.loan_token_symbol = self.loan_token_contract.functions.symbol().call()
            self.loan_token_factor = pow(10, self.loan_token_decimals)

            cache_token_details(
                self.loan_token,
                {
                    "decimals": self.loan_token_decimals,
                    "factor": self.loan_token_factor,
                    "symbol": self.loan_token_symbol,
                },
            )
        else:
            self.loan_token_decimals = cached_details_loan["decimals"]
            self.loan_token_symbol = cached_details_loan["symbol"]
            self.loan_token_factor = cached_details_loan["factor"]

        # Cache elements

        self.last_rate = 0
        self.last_rate_update = 0
        self.last_market_data = None
        self.last_market_data_update = 0

    def is_idle_market(self):
        return self.colateral_token == "0x0000000000000000000000000000000000000000"

    def name(self):
        return "{0}[{1}]".format(self.loan_token_symbol, self.collateral_token_symbol)

    def borrow_rate(self):
        return self.market_data().borrow_rate

    def rate_at_target(self):
        return self.market_data().borrow_rate_at_target

    def _market_data(self):
        if time.time() < self.last_market_data_update + 5:
            return self.last_market_data
        self.last_market_data = self.blue.market_data(self.id)
        self.last_market_data_update = time.time()
        return self.last_market_data

    def market_params(self):
        return self.params

    def market_data(self):
        (
            total_supply_assets,
            total_supply_shares,
            total_borrow_assets,
            total_borrow_shares,
            fee,
            utilization,
            supply_rate,
            borrow_rate,
        ) = self._market_data()

        if self.is_idle_market():
            return MaketData(
                total_supply_assets / self.loan_token_factor,
                total_supply_shares / POW_10_18,
                total_borrow_assets / self.loan_token_factor,
                total_borrow_shares / POW_10_18,
                fee,
                0,
                0,
                0,
                0,
            )

        borrow_rate = borrow_rate / POW_10_18
        rate_at_target = rate_to_target_rate(borrow_rate, utilization / POW_10_18)
        supply_rate = (
            borrow_rate * total_borrow_assets / total_supply_assets
            if total_supply_assets
            else 0
        )  # TODO: Doesn't work with fees

        return MaketData(
            total_supply_assets / self.loan_token_factor,
            total_supply_shares / POW_10_18,
            total_borrow_assets / self.loan_token_factor,
            total_borrow_shares / POW_10_18,
            fee,
            total_borrow_assets / total_supply_assets if total_supply_assets else 0,
            supply_rate,
            borrow_rate,
            rate_at_target,
        )

    def position(self, address):
        (
            supplied_shares,
            supplied_assets,
            borrowed_shares,
            borrowed_assets,
            collateral,
            collateral_value,
            ltv,
            health_ratio,
        ) = self.blue.reader.functions.getPosition(
            self.id, self.web3.to_checksum_address(address)
        ).call()

        if self.is_idle_market():
            return Position(
                address,
                supplied_shares / POW_10_18,
                supplied_assets / self.loan_token_factor,
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
            supplied_shares / POW_10_18,
            supplied_assets / self.loan_token_factor,
            borrowed_shares / POW_10_18,
            borrowed_assets / self.loan_token_factor,
            collateral / self.colateral_token_factor,
            collateral_value / self.loan_token_factor,
            (
                (collateral_value / self.loan_token_factor)
                / (collateral / self.colateral_token_factor)
                if collateral > 0
                else 0
            ),
            ltv / POW_10_18,
            health_ratio / POW_10_18,
        )

    def collateral_price(self):
        # todo: this oracle pricing is giving old and wrong results
        last_update = getattr(self, "last_oracle_update", None)
        if last_update is None or time.time() > last_update + 5:
            self.last_oracle_update = time.time()
            self.oracle_price = self.oracle_contract.functions.price().call() / (
                # Look at this for the decimals
                self.loan_token_factor * self.colateral_token_factor
            )
        return self.oracle_price

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
