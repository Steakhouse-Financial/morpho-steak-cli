from web3 import Web3
from web3 import Account
import json
from dotenv import load_dotenv
import morpho
from morpho import MorphoBlue, MetaMorpho
import os
import sys
import cmd
import math
import competition
from texttable import Texttable
from web3.gas_strategies.rpc import rpc_gas_price_strategy
import oneinch
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


load_dotenv()


def log(message, addTimestamp=True):
    print(message)
    if os.environ.get("LOG_FILE") != "":
        with open(os.environ.get("LOG_FILE"), "a") as file:
            if addTimestamp:
                file.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S - "))
            file.write(f"{message}\n")


def execute_transaction(web3, fnct):
    private_key = os.environ.get("PRIVATE_KEY")
    max_gas = int(os.environ.get("MAX_GWEI"))
    account = Account.from_key(private_key)
    account_address = account.address
    # print(account_address)
    tx = fnct.build_transaction({"from": account_address})
    nonce = web3.eth.get_transaction_count(account.address)
    tx["nonce"] = nonce
    signed_transaction = account.sign_transaction(tx)
    log(f"gas prices => {web3.eth.generate_gas_price()/pow(10,9):,.0f}")
    if web3.eth.generate_gas_price() < Web3.to_wei(max_gas, "gwei"):
        tx_hash = web3.eth.send_raw_transaction(signed_transaction.rawTransaction)
        log(f"Executed with hash => {tx_hash.hex()}")
    else:
        log(f"gas price too high => {web3.eth.generate_gas_price()/pow(10,9):,.0f}")


class MorphoCli(cmd.Cmd):
    intro = "Welcome to Steakhouse CLI.   Type help or ? to list commands.\n"
    prompt = ">> "
    vault = None
    web3 = None

    def __init__(self):
        cmd.Cmd.__init__(self)

        # Connect to web3
        self.web3 = Web3(Web3.HTTPProvider(os.environ.get("WEB3_HTTP_PROVIDER")))
        if not self.web3.is_connected():
            raise Exception("Issue to connect to Web3")

        self.web3.eth.set_gas_price_strategy(rpc_gas_price_strategy)

        # init morpho
        # morpho = MorphoBlue(web3, os.environ.get('MORPHO_BLUE'), os.environ.get('MORPHO_BLUE_MARKETS'))
        # print(morpho.market_data('0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc'))
        if os.environ.get("META_MORPHO") != "":
            self.vault = MetaMorpho(self.web3, os.environ.get("META_MORPHO"))
            # print("Vault {0} loaded".format(self.vault.name))

        if os.environ.get("MORPHO_BLUE_MARKETS") != "":
            self.blue = MorphoBlue(
                self.web3,
                os.environ.get("MORPHO_BLUE"),
                os.environ.get("MORPHO_BLUE_MARKETS"),
            )

    def do_chmeta(self, args):
        if not args:
            args = input("Please provide an argument or enter 'q' to go back: ")
            if args == "q":
                return

        print(args)

        if args[:2] == "0x":
            self.vault = MetaMorpho(self.web3, args)
        else:
            self.vault = MetaMorpho(self.web3, os.environ.get(args.upper()))

    def do_summary(self, line):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        self.vault.summary()
        print()

    def do_set_vault(self, vault):
        if not vault:
            vault = input("Please provide a vault address or enter 'q' to go back: ")
            if vault == "q":
                return
        self.vault = MetaMorpho(self.web3, vault)
        self.vault.summary()
        print()

    def do_position(self, address):
        if not address:
            address = input("Please provide a vault address or enter 'q' to go back: ")
            if address == "q":
                return
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return

        def fetch_position(market):
            # Fetch the position for a given market
            position = market.position(address)
            return market, position

        # Initialize ThreadPoolExecutor
        with ThreadPoolExecutor(
            max_workers=os.environ.get("MAX_WORKERS", 10)
        ) as executor:
            # Submit tasks to executor
            futures = [
                executor.submit(fetch_position, m)
                for m in self.vault.get_borrow_markets()
            ]

            for future in as_completed(futures):
                market, position = future.result()
                print(
                    "{0}: supply: {1:,.0f} borrow: {2:,.0f} collateral: {3:,.0f} ltv: {4:.1f}%".format(
                        market.name(),
                        position.supply_assets,
                        position.borrow_assets,
                        position.collateral_value,
                        position.ltv * 100.0,
                    )
                )

    def do_prices(self, address):
        # giving bad data in a number of ways

        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        for m in self.vault.get_borrow_markets():
            p = m.collateral_price()
            if p == "No Oracle Contract":
                print(f"{m.name()} {p}")
            else:
                print(
                    "{0}/{1} = {2:.2f}".format(
                        m.collateral_token_symbol, m.loan_token_symbol, p
                    )
                )
        print()

    def do_borrowers(self, address):
        def fetch_borrowers(market):
            borrowers = []
            for p in market.borrowers():
                borrowers.append((f"{p.ltv*100:.2f}% {p.address}",))
            return market.name(), borrowers

        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        with ThreadPoolExecutor(
            max_workers=os.environ.get("MAX_WORKERS", 10)
        ) as executor:
            futures = {
                executor.submit(fetch_borrowers, m): m
                for m in self.vault.get_borrow_markets()
            }

            for future in as_completed(futures):
                market_name, borrowers_info = future.result()
                print(f"{market_name}")
                for borrower_info in borrowers_info:
                    print(borrower_info[0])
                print()

    def do_market_borrowers(self, address):
        if self.blue is None:
            print("First add a some market to get a blue object")
            return
        for m in self.blue.markets:
            print(f"{m.name()}")
            for p in m.borrowers():
                print(f"{p.ltv*100:.22f}% {p.address} ")

    def do_competition(self, args):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return

        def fetch_rates(source, *args):
            # This function is a wrapper to fetch rates based on the source
            if source == "aaveV3":
                return ("Aave v3",) + competition.aave_v3_rates(*args)
            elif source == "aaveV3_1d":
                return ("Aave v3 1d",) + competition.aave_v3_rates(*args)
            elif source == "aaveV3_7d":
                return ("Aave v3 7d",) + competition.aave_v3_rates(*args)
            elif source == "spark":
                return ("Spark DAI",) + competition.spark_rates(*args)

        tasks = [
            ("aaveV3", self.web3, self.vault.asset),
            ("aaveV3_1d", self.web3, self.vault.asset, 7200),
            ("aaveV3_7d", self.web3, self.vault.asset, 7 * 7200),
            ("spark", self.web3),  # only web3 needed
        ]

        table = Texttable()
        table.header(["Protocol", "Supply", "Borrow", "Obs"])
        table.set_cols_align(["l", "r", "r", "r"])
        table.set_deco(Texttable.HEADER)

        with ThreadPoolExecutor(len(tasks)) as executor:
            future_to_task = {
                executor.submit(fetch_rates, *task): task[0] for task in tasks
            }

            for future in as_completed(future_to_task):
                protocol, supply_rate, borrow_rate, cnt = future.result()
                table.add_row(
                    [
                        protocol,
                        f"{supply_rate*100:.2f}%",
                        f"{borrow_rate*100:.2f}%",
                        cnt,
                    ]
                )
        table.add_row(["=========", "", "", ""])

        def get_rate(market):
            rate = market.borrow_rate()
            return market.collateral_token_symbol, rate

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            future_to_task = {
                executor.submit(get_rate, m): m for m in self.vault.get_borrow_markets()
            }

            for future in as_completed(future_to_task):
                collateral_token_symbol, rate = future.result()
                table.add_row(
                    [
                        collateral_token_symbol,
                        f"{self.vault.rate()*100:.2f}%",
                        f"{rate*100:.2f}%",
                        "",
                    ]
                )

        print(table.draw())
        print()

    def do_wind(self, args):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return

        if self.vault.asset_symbol != "USDC":
            print("Only work for steakUSDC")
            return

    def do_grant_admin(self, args):
        (contract, to) = args.split()
        # Not the best ABI but works
        abi = json.load(open("abis/MorphoLiquidator.json"))
        liquidator = self.web3.eth.contract(
            address=Web3.to_checksum_address(contract), abi=abi
        )
        fnct = liquidator.functions.grantRole(
            liquidator.functions.DEFAULT_ADMIN_ROLE().call(),
            Web3.to_checksum_address(to),
        )
        execute_transaction(self.web3, fnct)

    def do_grant_operator(self, args):
        (contract, to) = args.split()
        # Not the best ABI but works
        abi = json.load(open("abis/MorphoLiquidator.json"))
        liquidator = self.web3.eth.contract(
            address=Web3.to_checksum_address(contract), abi=abi
        )
        fnct = liquidator.functions.grantRole(
            liquidator.functions.OPERATOR_ROLE().call(), Web3.to_checksum_address(to)
        )
        execute_transaction(self.web3, fnct)

    def liquidate(self, id, borrower):
        blue = MorphoBlue(self.web3, os.environ.get("MORPHO_BLUE"), id)
        market = blue.get_market_by_id(id)
        market_params = blue.market_params(id)
        pos = market.position(borrower)
        if pos.ltv < market.lltv:
            print(
                f"LTV of {borrower} is {pos.ltv*100:.2f}%, limit LTV is {market.lltv*100:.2f}%"
            )

        print(
            f"LTV of {borrower} is {pos.ltv*100:.2f}% above limit LTV {market.lltv*100:.2f}%, start liquidation"
        )

        print(
            f"Borrowed shares to be repaided {pos.borrow_shares:,.18f} corresponding to {pos.borrow_assets:,.8f} assets"
        )
        # Compute seizable collateral

        incentive_factor = min(1.15, 1 / (1 - 0.3 * (1 - market.lltv)))
        print(f"Incentive factor {incentive_factor:,.4f}")

        theoretical_seizable_collateral = (
            incentive_factor * pos.borrow_assets * pos.collateral_price
        )

        # In this case, we do not have to cover all the debt to retrieve the collateral. This is the case if there is a bad debt.
        if theoretical_seizable_collateral > pos.collateral:
            seized_collateral = pos.collateral
        else:
            seized_collateral = theoretical_seizable_collateral

        print(
            f"Will seize {seized_collateral:,.4f} of collateral corresponding to {seized_collateral * pos.collateral_price:,.4f} in value"
        )

        abi = json.load(open("abis/MorphoLiquidator.json"))
        liquidator = self.web3.eth.contract(
            address=Web3.to_checksum_address(os.environ.get("LIQUIDATOR_STEAKHOUSE")),
            abi=abi,
        )
        fnct = liquidator.functions.liquidate(
            market_params.to_tuple(), Web3.to_checksum_address(borrower), 0, False
        )
        execute_transaction(self.web3, fnct)

    def liquidate_1inch(self, id, borrower):
        blue = MorphoBlue(self.web3, os.environ.get("MORPHO_BLUE"), id)
        market = blue.get_market_by_id(id)
        market_params = blue.market_params(id)
        pos = market.position(borrower)
        if pos.ltv < market.lltv:
            print(
                f"LTV of {borrower} is {pos.ltv*100:.2f}%, limit LTV is {market.lltv*100:.2f}%"
            )

        print(
            f"LTV of {borrower} is {pos.ltv*100:.2f}% above limit LTV {market.lltv*100:.2f}%, start liquidation"
        )

        print(
            f"Borrowed shares to be repaided {pos.borrow_shares:,.18f} corresponding to {pos.borrow_assets:,.8f} assets"
        )
        # Compute seizable collateral

        incentive_factor = min(1.15, 1 / (1 - 0.3 * (1 - market.lltv)))
        print(f"Incentive factor {incentive_factor:,.4f}")

        theoretical_seizable_collateral = (
            incentive_factor * pos.borrow_assets * pos.collateral_price
        )

        # In this case, we do not have to cover all the debt to retrieve the collateral. This is the case if there is a bad debt.
        if theoretical_seizable_collateral > pos.collateral:
            seized_collateral = pos.collateral
        else:
            seized_collateral = theoretical_seizable_collateral

        print(
            f"Will seize {seized_collateral:,.4f} of collateral corresponding to {seized_collateral * pos.collateral_price:,.4f} in value"
        )

        abi = json.load(open("abis/liquidator.json"))
        amount = pos.collateral * market.colateral_token_factor
        print(f"exact amount of collateral {amount}")
        oneinch_result = oneinch.swapData(
            market_params.colateral_token,
            market_params.loan_token,
            amount,
            os.environ.get("LIQUIDATOR_1INCH"),
        )
        print(oneinch_result)
        liquidator = self.web3.eth.contract(
            address=Web3.to_checksum_address(os.environ.get("LIQUIDATOR_1INCH")),
            abi=abi,
        )
        debug = {
            "tuple": market_params.to_tuple(),
            "who": Web3.to_checksum_address(borrower),
            "asset": int(pos.borrow_shares * pow(10, 18)),
            "collateral": int(amount),
            "data": oneinch_result.json()["tx"]["data"][2:],
        }
        print(debug)
        fnct = liquidator.functions.liquidate(
            market_params.to_tuple(),
            Web3.to_checksum_address(borrower),
            0,
            int(pos.borrow_shares * pow(10, 18)),
            bytes.fromhex(oneinch_result.json()["tx"]["data"][2:]),
        )
        execute_transaction(self.web3, fnct)

    def do_liquidate(self, args):
        (id, borrower) = args.split()
        self.liquidate(id, borrower)
        print()

    def do_liquidate_1inch(self, args):
        (id, borrower) = args.split()
        self.liquidate_1inch(id, borrower)
        print()

    def do_liquidate_markets(self, args):
        if self.blue is None:
            print("First add a some market to get a blue object")
            return
        for m in self.blue.markets:
            print(f"{m.name()}")
            for p in m.borrowers():
                if p.health_ratio < 0.99:
                    print(f"{p.address} health ratio is {p.health_ratio *100:.1f}%")
                    self.liquidate(m.id, p.address)
        print()

    def reallocation_pyusd(self, execute=False):
        if self.vault.symbol != "steakPYUSD":
            print("Work only for steakPYUSD for now")
            return

        target_base_rate = 0.047

        min_rate = dict()
        min_rate["wstETH"] = (
            target_base_rate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        min_rate["WBTC"] = (
            target_base_rate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        min_rate["wbIB01"] = target_base_rate + 0.001
        max_rate = dict()
        max_rate["wstETH"] = (
            target_base_rate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        # todo: Get the proper max_rate (hold for now)
        # I am assuming this needs to be max_rate["WBTC"] vs. min since min rate is instantiated above
        max_rate["WBTC"] = (
            target_base_rate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        max_rate["wbIB01"] = target_base_rate + 0.001
        OVERFLOW_AMOUNT = 115792089237316195423570985008687907853269984665640564039457584007913129639935
        MAX_UTILIZATION_TARGET = 0.995

        overflow_market = self.vault.get_idle_market()
        overflow_market_data = overflow_market.market_data()
        available_liquidity = 0
        needed_liquidity = 0
        actions = []

        if overflow_market in min_rate:
            print(
                f"You can't have a min rate for the overflow market {overflow_market}"
            )

        # Ensure we empty the idle market
        idle_market = self.vault.get_idle_market()
        idle_market_data = idle_market.market_data()
        idle_position = idle_market.position(self.vault.address)
        if idle_market_data.total_supply_assets > 0:
            log(
                f"Idle: Need to remove {idle_market_data.total_supply_assets:,.0f} ({idle_market_data.total_supply_assets:,.0f} -> {0:,.0f})"
            )
            available_liquidity += idle_position.supply_assets
            actions = [
                (0, -idle_market_data.total_supply_assets, idle_market.market_params())
            ] + actions  # 0 instead of target just for safety

        # First pass to check for excess liquidity markets
        for m in self.vault.get_borrow_markets():
            rate = m.borrow_rate()
            data = m.market_data()
            position = m.position(self.vault.address)

            if (m.collateral_token_symbol in min_rate) and rate < min_rate[
                m.collateral_token_symbol
            ]:
                target_rate = min_rate[m.collateral_token_symbol]
                new_util = min(
                    MAX_UTILIZATION_TARGET,
                    morpho.utils.utilization_for_rate(
                        data.borrow_rate_at_target, target_rate
                    ),
                )
                target = data.total_borrow_assets / new_util
                to_remove = position.supply_assets - target
                available_liquidity += to_remove
                print(
                    f"{m.collateral_token_symbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to remove {to_remove:,.0f} ({data.total_supply_assets:,.0f} -> {target:,.0f})"
                )
                if to_remove > 0:
                    actions.append((target, -to_remove, m.market_params()))

        to_add = 0
        # Second pass to find where more liquidity is needed
        for m in self.vault.get_borrow_markets():
            rate = m.borrow_rate()
            data = m.market_data()
            position = m.position(self.vault.address)

            if (m.collateral_token_symbol in max_rate) and rate > max_rate[
                m.collateral_token_symbol
            ]:
                target_rate = max_rate[m.collateral_token_symbol]
                new_util = morpho.utils.utilization_for_rate(
                    data.borrow_rate_at_target, target_rate
                )
                if new_util > 0:
                    target = data.total_borrow_assets / new_util
                else:
                    target = data.total_borrow_assets + 100000 * pow(
                        10, self.vault.asset_decimals
                    )  ## Min allocation if no borrow

                to_add = target - data.total_supply_assets
                needed_liquidity += to_add
                log(
                    f"{m.collateral_token_symbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to add {to_add:,.0f} ({data.total_supply_assets:,.0f} -> {target:,.0f})"
                )
                if to_add > 0:
                    actions.append((target, to_add, m.market_params()))
        # If there is not enough liquidity from active market, add the idle market first
        print(f"Available {available_liquidity:,.0f} needed {needed_liquidity:,.0f}")
        if (
            available_liquidity < needed_liquidity
            or overflow_market.borrow_rate() > target_base_rate + 0.01
        ):
            # Unwind the sDAI bot (uncomment when ready)
            # sDAIBotUnwinded = True

            # take all liquidity from sDAI market
            overflowLiquidity = (
                overflow_market_data.total_supply_assets
                - overflow_market_data.total_borrow_assets
            )
            if overflowLiquidity > 0:
                # todo: check if this is the right market to take liquidity from (maybe this should be the idle market instead of the sDAI market)
                m = self.vault.get_market_by_collateral("sDAI")
                log(
                    f"{m.collateral_token_symbol}: Take all liquidity {available_liquidity:,.0f} ({overflow_market_data.total_supply_assets:,.0f} -> {overflow_market_data.total_borrow_assets:,.0f})"
                )
                if to_add > 0:
                    actions.append(
                        (
                            overflow_market_data.total_borrow_assets,
                            -overflowLiquidity,
                            m.market_params(),
                        )
                    )

        # If we don't have enough liquidity scale down expectations
        if needed_liquidity > 0 and available_liquidity < needed_liquidity:
            ratio = available_liquidity / needed_liquidity
            log(
                f"Not enough available liquidity ({available_liquidity:,.0f} vs {needed_liquidity:,.0f}). Reduce needs to {ratio*100.0:.2f}%"
            )

            needed_liquidity = available_liquidity

            for i, action in enumerate(actions):
                if action[1] > 0 and action[1] > 0:
                    actions[i] = (
                        action[0] - (1 - ratio) * action[1],
                        ratio * action[1],
                        action[2],
                    )

        if len(actions) == 0 or max(available_liquidity, needed_liquidity) < float(
            os.environ.get("REBALANCING_THRESHOLD")
        ):
            log(
                f"Nothing to do {max(available_liquidity, needed_liquidity):,.0f} < {float(os.environ.get('REBALANCING_THRESHOLD')):,.0f}"
            )
            print()
            return

        # Tbd
        # table = Texttable()
        # table.header(["Market", "Delta", "Util", "Obs"])
        # table.set_cols_align(['l', 'r', 'r', 'r'])
        # table.set_deco(Texttable.HEADER )
        # print(actions)

        # print(table.draw())

        print()

        script = "["

        for i, action in enumerate(actions):
            if i != 0:
                script = script + ", "
            script = (
                script
                + f'[{action[2].to_gnosis_safe_string()}, "{math.floor(action[0]*pow(10,self.vault.asset_decimals)):.0f}"]'
            )

        script = (
            script
            + f', [{overflow_market.params.to_gnosis_safe_string()}, "{OVERFLOW_AMOUNT}"]]'
        )

        print(script)
        print("execute: ", execute)
        if execute:
            private_key = os.environ.get("PRIVATE_KEY")
            max_gas = int(os.environ.get("MAX_GWEI"))
            script = []
            for i, action in enumerate(actions):
                # script = script + [((action[2].loan_token, action[2].colateral_token, action[2].oracle, action[2].irm, action[2].lltv), math.floor(action[0]*pow(10,self.vault.asset_decimals)))]
                script = script + [
                    (
                        action[2].to_tuple(),
                        math.floor(action[0] * pow(10, self.vault.asset_decimals)),
                    )
                ]
            script = script + [(overflow_market.params.to_tuple(), OVERFLOW_AMOUNT)]
            # print(script)
            account = Account.from_key(private_key)
            account_address = account.address
            # print(account_address)
            tx = self.vault.contract.functions.reallocate(script).build_transaction(
                {"from": account_address}
            )
            nonce = self.web3.eth.get_transaction_count(account.address)
            tx["nonce"] = nonce
            signed_transaction = account.sign_transaction(tx)
            log(f"gas prices => {self.web3.eth.generate_gas_price()/pow(10,9):,.0f}")
            if self.web3.eth.generate_gas_price() < Web3.to_wei(max_gas, "gwei"):
                tx_hash = self.web3.eth.send_raw_transaction(
                    signed_transaction.rawTransaction
                )
                log(f"Executed with hash => {tx_hash.hex()}")
            else:
                log(
                    f"gas price too high => {self.web3.eth.generate_gas_price()/pow(10,9):,.0f}"
                )

        print()

    def reallocation_usdc(self, execute=False):
        if self.vault.symbol != "steakUSDC":
            print("Works only for steakUSDC for now")
            return

        # not being used, leaving to ensure is ok
        # sDAIBotUnwinded = False

        # don't seem necessary
        # (a0, aRate, a1) = competition.aave_v3_rates(self.web3, self.vault.asset)
        # (a0, aRateDay, a1) = competition.aave_v3_rates(self.web3, self.vault.asset, 7200)

        target_base_rate = 0.047

        min_rate = dict()
        # todo: check for the min_rate of WBTC and sDAI
        min_rate["wstETH"] = (
            target_base_rate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        min_rate["wbIB01"] = target_base_rate + 0.001
        max_rate = dict()
        # todo: check for the max_rate of WBTC and sDAI
        max_rate["wstETH"] = (
            target_base_rate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        max_rate["wbIB01"] = target_base_rate + 0.001
        OVERFLOW_AMOUNT = 115792089237316195423570985008687907853269984665640564039457584007913129639935
        MAX_UTILIZATION_TARGET = 0.995

        overflow_market = self.vault.get_market_by_collateral("sDAI")
        overflow_market_data = overflow_market.market_data()
        available_liquidity = 0
        needed_liquidity = 0
        actions = []

        if overflow_market in min_rate:
            print(
                f"You can't have a min rate for the overflow market {overflow_market}"
            )

        # Ensure we empty the idle market
        idle_market = self.vault.get_idle_market()
        idle_market_data = idle_market.market_data()
        idle_position = idle_market.position(self.vault.address)
        if idle_market_data.total_supply_assets > 0:
            log(
                f"Idle: Need to remove {idle_market_data.total_supply_assets:,.0f} ({idle_market_data.total_supply_assets:,.0f} -> {0:,.0f})"
            )
            available_liquidity += idle_position.supply_assets
            actions = [
                (0, -idle_market_data.total_supply_assets, idle_market.market_params())
            ] + actions  # 0 instead of target just for safety

        # First pass to check for excess liquidity markets

        def excess_liquidity(m, min_rate, vaultAddress):
            rate = m.borrow_rate()
            data = m.market_data()
            position = m.position(vaultAddress)

            if (m.collateral_token_symbol in min_rate) and rate < min_rate[
                m.collateral_token_symbol
            ]:
                target_rate = min_rate[m.collateral_token_symbol]
                new_util = min(
                    MAX_UTILIZATION_TARGET,
                    morpho.utils.utilization_for_rate(
                        data.borrow_rate_at_target, target_rate
                    ),
                )
                target = data.total_borrow_assets / new_util
                to_remove = position.supply_assets - target
                available_liquidity = to_remove
                print(
                    f"{m.collateral_token_symbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to remove {to_remove:,.0f} ({data.total_supply_assets:,.0f} -> {target:,.0f})"
                )
                if to_remove > 0:
                    return (target, m.market_params(), to_remove, available_liquidity)
                return None
            else:
                if m.collateral_token_symbol not in min_rate:
                    print(f"{m.collateral_token_symbol}: No min rate")
                    return None
                print(
                    f"{m.collateral_token_symbol}: rate: {rate} > min_rate: {min_rate[m.collateral_token_symbol]}"
                )
                return None

        with ThreadPoolExecutor(
            max_workers=os.environ.get("MAX_WORKERS", 10)
        ) as executor:
            futures = {
                executor.submit(excess_liquidity, m, min_rate, self.vault.address): m
                for m in self.vault.get_borrow_markets()
            }

            for future in as_completed(futures):
                result = future.result()
                if result:
                    target, market_params, to_remove, liquidity = future.result()
                    actions.append((target, -to_remove, market_params))
                    available_liquidity += liquidity

        print()
        to_add = 0
        # Second pass to find where more liquidity is ndeed

        def liquidity_needed(m, max_rate, asset_decimals):
            rate = m.borrow_rate()
            data = m.market_data()

            if (m.collateral_token_symbol in max_rate) and rate > max_rate[
                m.collateral_token_symbol
            ]:
                target_rate = max_rate[m.collateral_token_symbol]
                new_util = morpho.utils.utilization_for_rate(
                    data.borrow_rate_at_target, target_rate
                )
                if new_util > 0:
                    target = data.total_borrow_assets / new_util
                else:
                    target = data.total_borrow_assets + 100000 * pow(
                        10, asset_decimals
                    )  ## Min allocation if no borrow

                to_add = target - data.total_supply_assets
                log(
                    f"{m.collateral_token_symbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to add {to_add:,.0f} ({data.total_supply_assets:,.0f} -> {target:,.0f})"
                )
                if to_add > 0:
                    return (target, to_add, m.market_params())

        with ThreadPoolExecutor(
            max_workers=os.environ.get("MAX_WORKERS", 10)
        ) as executor:
            futures = {
                executor.submit(
                    liquidity_needed,
                    m,
                    max_rate,
                    self.vault.asset_decimals,
                ): m
                for m in self.vault.get_borrow_markets()
            }

            for future in as_completed(futures):
                result = future.result()
                if result:
                    target, to_add, market_params = future.result()
                    actions.append((target, to_add, market_params))
                    needed_liquidity += to_add

        # If there is not enough liquidity from active market, add the idle market first
        print()
        print(f"Available {available_liquidity:,.0f} needed {needed_liquidity:,.0f}")
        if (
            available_liquidity < needed_liquidity
            or overflow_market.borrow_rate() > target_base_rate + 0.01
        ):
            # Unwind the sDAI bot (uncomment when ready)
            # sDAIBotUnwinded = True

            # take all liquidity from sDAI market
            overflowLiquidity = (
                overflow_market_data.total_supply_assets
                - overflow_market_data.total_borrow_assets
            )
            # todo: check if this is the right market to take liquidity from (maybe this should be the idle market instead of the sDAI market)
            m = self.vault.get_market_by_collateral("sDAI")

            if overflowLiquidity > 0:
                log(
                    f"{m.collateral_token_symbol}: Take all liquidity {available_liquidity:,.0f} ({overflow_market_data.total_supply_assets:,.0f} -> {overflow_market_data.total_borrow_assets:,.0f})"
                )
                if to_add > 0:
                    actions.append(
                        (
                            overflow_market_data.total_borrow_assets,
                            -overflowLiquidity,
                            m.market_params(),
                        )
                    )

        # If we don't have enough liquidity scale down expectations
        if needed_liquidity > 0 and available_liquidity < needed_liquidity:
            ratio = available_liquidity / needed_liquidity
            log(
                f"Not enough available liquidity ({available_liquidity:,.0f} vs {needed_liquidity:,.0f}). Reduce needs to {ratio*100.0:.2f}%"
            )

            needed_liquidity = available_liquidity

            for i, action in enumerate(actions):
                if action[1] > 0 and action[1] > 0:
                    actions[i] = (
                        action[0] - (1 - ratio) * action[1],
                        ratio * action[1],
                        action[2],
                    )

        if len(actions) == 0 or max(-available_liquidity, needed_liquidity) < float(
            os.environ.get("REBALANCING_THRESHOLD")
        ):
            log(
                f"Nothing to do {max(-available_liquidity, needed_liquidity):,.0f} < {float(os.environ.get('REBALANCING_THRESHOLD')):,.0f}"
            )
            print()
            return

        # Tbd
        # table = Texttable()
        # table.header(["Market", "Delta", "Util", "Obs"])
        # table.set_cols_align(['l', 'r', 'r', 'r'])
        # table.set_deco(Texttable.HEADER )
        # print(actions)

        # print(table.draw())

        print()

        script = "["

        for i, action in enumerate(actions):
            if i != 0:
                script = script + ", "
            script = (
                script
                + f'[{action[2].to_gnosis_safe_string()}, "{math.floor(action[0]*pow(10,self.vault.asset_decimals)):.0f}"]'
            )

        script = (
            script
            + f', [{overflow_market.params.to_gnosis_safe_string()}, "{OVERFLOW_AMOUNT}"]]'
        )

        print(script)

        if execute:
            private_key = os.environ.get("PRIVATE_KEY")
            max_gas = int(os.environ.get("MAX_GWEI"))
            script = []
            for i, action in enumerate(actions):
                # script = script + [((action[2].loan_token, action[2].colateral_token, action[2].oracle, action[2].irm, action[2].lltv), math.floor(action[0]*pow(10,self.vault.asset_decimals)))]
                script = script + [
                    (
                        action[2].to_tuple(),
                        math.floor(action[0] * pow(10, self.vault.asset_decimals)),
                    )
                ]
            script = script + [(overflow_market.params.to_tuple(), OVERFLOW_AMOUNT)]
            # print(script)
            account = Account.from_key(private_key)
            account_address = account.address
            # print(account_address)
            tx = self.vault.contract.functions.reallocate(script).build_transaction(
                {"from": account_address}
            )
            nonce = self.web3.eth.get_transaction_count(account.address)
            tx["nonce"] = nonce
            signed_transaction = account.sign_transaction(tx)
            log(f"gas prices => {self.web3.eth.generate_gas_price()/pow(10,9):,.0f}")
            if self.web3.eth.generate_gas_price() < Web3.to_wei(max_gas, "gwei"):
                tx_hash = self.web3.eth.send_raw_transaction(
                    signed_transaction.rawTransaction
                )
                log(f"Executed with hash => {tx_hash.hex()}")
            else:
                log(
                    f"gas price too high => {self.web3.eth.generate_gas_price()/pow(10,9):,.0f}"
                )

        print()

    def do_reallocation(self, args):
        if self.vault is None:
            print("First add a MetaMorpho vault")
        elif self.vault.symbol == "steakUSDC":
            self.reallocation_usdc(args == "execute")
        elif self.vault.symbol == "steakPYUSD":
            self.reallocation_pyusd(args == "execute")

    def do_full(self, args):
        # todo: print outs are async and cause confusion (obviously).  If this is important for speed we can make them vars and print at end in order (as a quick idea)
        # tasks = [
        #     (self.do_summary, ""),
        #     (self.do_competition, ""),
        #     (self.do_reallocation, "execute"),
        #     (self.do_borrowers, ""),
        # ]

        # # Execute tasks in parallel
        # with ThreadPoolExecutor() as executor:
        #     # Executes the tasks [0] and gives the input [1]
        #     futures = [executor.submit(task[0], task[1]) for task in tasks]
        #     for future in futures:
        #         future.result()  # This will re-raise any exceptions encountered in the task
        self.do_summary("")
        self.do_competition("")
        self.do_reallocation("execute")
        self.do_borrowers("")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        MorphoCli().onecmd(" ".join(sys.argv[1:]))
    else:
        MorphoCli().cmdloop()
