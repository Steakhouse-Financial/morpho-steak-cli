import time
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
from web3.gas_strategies.time_based import medium_gas_price_strategy
from web3.gas_strategies.rpc import rpc_gas_price_strategy
import oneinch
from datetime import datetime

load_dotenv()


def log(message, addTimestamp=True):
    print(message)
    if os.environ.get("LOG_FILE") != "":
        with open(os.environ.get("LOG_FILE"), "a") as file:
            if addTimestamp:
                file.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S - "))
            file.write(f"{message}\n")


def executeTransaction(web3, fnct):
    privateKey = os.environ.get("PRIVATE_KEY")
    maxGas = int(os.environ.get("MAX_GWEI"))
    account = Account.from_key(privateKey)
    account_address = account.address
    # print(account_address)
    tx = fnct.build_transaction({"from": account_address})
    nonce = web3.eth.get_transaction_count(account.address)
    tx["nonce"] = nonce
    signed_transaction = account.sign_transaction(tx)
    log(f"gas prices => {web3.eth.generate_gas_price()/pow(10,9):,.0f}")
    if web3.eth.generate_gas_price() < Web3.to_wei(maxGas, "gwei"):
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
        super().__init__()

        self.start_ts = time.time()
        print(
            "Starting Morpho CLI at: ",
            datetime.fromtimestamp(self.start_ts).strftime("%Y-%m-%d %H:%M:%S"),
        )

        # Connect to web3
        self.web3 = Web3(Web3.HTTPProvider(os.environ.get("WEB3_HTTP_PROVIDER")))
        if not self.web3.is_connected():
            raise Exception("Issue to connect to Web3")

        self.web3.eth.set_gas_price_strategy(rpc_gas_price_strategy)

        # init morpho
        # morpho = MorphoBlue(web3, os.environ.get('MORPHO_BLUE'), os.environ.get('MORPHO_BLUE_MARKETS'))
        # print(morpho.marketData('0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc'))
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
        self.vault = MetaMorpho(self.web3, vault)
        self.vault.summary()
        print()

    def do_position(self, address):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        for m in self.vault.getBorrowMarkets():
            p = m.position(address)
            print(
                "{0}: supply: {1:,.0f} borrow: {2:,.0f} collateral: {3:,.0f} ltv: {4:.1f}%".format(
                    m.name(),
                    p.supplyAssets,
                    p.borrowAssets,
                    p.collateralValue,
                    p.ltv * 100.0,
                )
            )
        print()

    def do_prices(self, address):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        for m in self.vault.getBorrowMarkets():
            p = m.collateralPrice()
            print(
                "{0}/{1} = {2:.2f}".format(
                    m.collateralTokenSymbol, m.loanTokenSymbol, p
                )
            )
        print()

    def do_borrowers(self, address):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        for m in self.vault.getBorrowMarkets():
            print(f"{m.name()}")
            for p in m.borrowers():
                print(f"{p.ltv*100:.2f}% {p.address} ")
        print()

    def do_market_borrowers(self, address):
        if self.blue is None:
            print("First add a some market to get a blue object")
            return
        for m in self.blue.markets:
            print(f"{m.name()}")
            for p in m.borrowers():
                print(f"{p.ltv*100:.22f}% {p.address} ")
        print()

    def do_competition(self, args):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return

        table = Texttable()
        table.header(["Protocol", "Supply", "Borrow", "Obs"])
        table.set_cols_align(["l", "r", "r", "r"])
        table.set_deco(Texttable.HEADER)

        (supplyRate, borrowRate, cnt) = competition.aaveV3Rates(
            self.web3, self.vault.asset
        )
        table.add_row(
            ["Aave v3", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt]
        )

        (supplyRate, borrowRate, cnt) = competition.aaveV3Rates(
            self.web3, self.vault.asset, 7200
        )
        table.add_row(
            ["Aave v3 1d", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt]
        )

        (supplyRate, borrowRate, cnt) = competition.aaveV3Rates(
            self.web3, self.vault.asset, 7 * 7200
        )
        table.add_row(
            ["Aave v3 7d", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt]
        )

        (supplyRate, borrowRate, cnt) = competition.sparkRates(
            self.web3
        )  # Use DAI for Spark
        table.add_row(
            ["Spark DAI", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt]
        )
        table.add_row(["=========", "", "", ""])

        for m in self.vault.getBorrowMarkets():
            rate = m.borrowRate()
            table.add_row(
                [
                    m.collateralTokenSymbol,
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

        if self.vault.assetSymbol != "USDC":
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
        executeTransaction(self.web3, fnct)

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
        executeTransaction(self.web3, fnct)

    def liquidate(self, id, borrower):
        blue = MorphoBlue(self.web3, os.environ.get("MORPHO_BLUE"), id)
        market = blue.getMarketById(id)
        marketParams = blue.marketParams(id)
        pos = market.position(borrower)
        if pos.ltv < market.lltv:
            print(
                f"LTV of {borrower} is {pos.ltv*100:.2f}%, limit LTV is {market.lltv*100:.2f}%"
            )

        print(
            f"LTV of {borrower} is {pos.ltv*100:.2f}% above limit LTV {market.lltv*100:.2f}%, start liquidation"
        )

        print(
            f"Borrowed shares to be repaided {pos.borrowShares:,.18f} corresponding to {pos.borrowAssets:,.8f} assets"
        )
        # Compute seizable collateral

        incentiveFactor = min(1.15, 1 / (1 - 0.3 * (1 - market.lltv)))
        print(f"Incentive factor {incentiveFactor:,.4f}")

        theoreticalSeizableCollateral = (
            incentiveFactor * pos.borrowAssets * pos.collateralPrice
        )

        # In this case, we do not have to cover all the debt to retrieve the collateral. This is the case if there is a bad debt.
        if theoreticalSeizableCollateral > pos.collateral:
            seizedCollateral = pos.collateral
        else:
            seizedCollateral = theoreticalSeizableCollateral

        print(
            f"Will seize {seizedCollateral:,.4f} of collateral corresponding to {seizedCollateral * pos.collateralPrice:,.4f} in value"
        )

        abi = json.load(open("abis/MorphoLiquidator.json"))
        liquidator = self.web3.eth.contract(
            address=Web3.to_checksum_address(os.environ.get("LIQUIDATOR_STEAKHOUSE")),
            abi=abi,
        )
        fnct = liquidator.functions.liquidate(
            marketParams.toTuple(), Web3.to_checksum_address(borrower), 0, False
        )
        executeTransaction(self.web3, fnct)

    def liquidate_1inch(self, id, borrower):
        blue = MorphoBlue(self.web3, os.environ.get("MORPHO_BLUE"), id)
        market = blue.getMarketById(id)
        marketParams = blue.marketParams(id)
        pos = market.position(borrower)
        if pos.ltv < market.lltv:
            print(
                f"LTV of {borrower} is {pos.ltv*100:.2f}%, limit LTV is {market.lltv*100:.2f}%"
            )

        print(
            f"LTV of {borrower} is {pos.ltv*100:.2f}% above limit LTV {market.lltv*100:.2f}%, start liquidation"
        )

        print(
            f"Borrowed shares to be repaided {pos.borrowShares:,.18f} corresponding to {pos.borrowAssets:,.8f} assets"
        )
        # Compute seizable collateral

        incentiveFactor = min(1.15, 1 / (1 - 0.3 * (1 - market.lltv)))
        print(f"Incentive factor {incentiveFactor:,.4f}")

        theoreticalSeizableCollateral = (
            incentiveFactor * pos.borrowAssets * pos.collateralPrice
        )

        # In this case, we do not have to cover all the debt to retrieve the collateral. This is the case if there is a bad debt.
        if theoreticalSeizableCollateral > pos.collateral:
            seizedCollateral = pos.collateral
        else:
            seizedCollateral = theoreticalSeizableCollateral

        print(
            f"Will seize {seizedCollateral:,.4f} of collateral corresponding to {seizedCollateral * pos.collateralPrice:,.4f} in value"
        )

        abi = json.load(open("abis/liquidator.json"))
        amount = pos.collateral * market.collateralTokenFactor
        print(f"exact amount of collateral {amount}")
        oneinch_result = oneinch.swapData(
            marketParams.collateralToken,
            marketParams.loanToken,
            amount,
            os.environ.get("LIQUIDATOR_1INCH"),
        )
        print(oneinch_result)
        liquidator = self.web3.eth.contract(
            address=Web3.to_checksum_address(os.environ.get("LIQUIDATOR_1INCH")),
            abi=abi,
        )
        debug = {
            "tuple": marketParams.toTuple(),
            "who": Web3.to_checksum_address(borrower),
            "asset": int(pos.borrowShares * pow(10, 18)),
            "collateral": int(amount),
            "data": oneinch_result.json()["tx"]["data"][2:],
        }
        print(debug)
        fnct = liquidator.functions.liquidate(
            marketParams.toTuple(),
            Web3.to_checksum_address(borrower),
            0,
            int(pos.borrowShares * pow(10, 18)),
            bytes.fromhex(oneinch_result.json()["tx"]["data"][2:]),
        )
        executeTransaction(self.web3, fnct)

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
                if p.healthRatio < 0.99:
                    print(f"{p.address} health ratio is {p.healthRatio *100:.1f}%")
                    self.liquidate(m.id, p.address)
        print()

    def reallocation_pyusd(self, execute=False):
        if self.vault.symbol != "steakPYUSD":
            print("Work only for steakPYUSD for now")
            return

        targetBaseRate = 0.047

        minRate = dict()
        minRate["wstETH"] = (
            targetBaseRate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        minRate["WBTC"] = (
            targetBaseRate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        minRate["wbIB01"] = targetBaseRate + 0.001
        maxRate = dict()
        maxRate["wstETH"] = (
            targetBaseRate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        minRate["WBTC"] = (
            targetBaseRate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        maxRate["wbIB01"] = targetBaseRate + 0.001
        OVERFLOW_AMOUNT = 115792089237316195423570985008687907853269984665640564039457584007913129639935
        MAX_UTILIZATION_TARGET = 0.995

        overflowMarket = self.vault.getIdleMarket()
        overflowMarketData = overflowMarket.marketData()
        availableLiquidity = 0
        neededLiquidity = 0
        actions = []

        if overflowMarket in minRate:
            print(f"You can't have a min rate for the overflow market {overflowMarket}")

        # Ensure we empty the idle market
        idleMarket = self.vault.getIdleMarket()
        idleMarketData = idleMarket.marketData()
        idlePosition = idleMarket.position(self.vault.address)
        if idleMarketData.totalSupplyAssets > 0:
            log(
                f"Idle: Need to remove {idleMarketData.totalSupplyAssets:,.0f} ({idleMarketData.totalSupplyAssets:,.0f} -> {0:,.0f})"
            )
            availableLiquidity += idlePosition.supplyAssets
            actions = [
                (0, -idleMarketData.totalSupplyAssets, idleMarket.marketParams())
            ] + actions  # 0 instead of target just for safety

        # First pass to check for excess liquidity markets
        for m in self.vault.getBorrowMarkets():
            rate = m.borrowRate()
            data = m.marketData()
            position = m.position(self.vault.address)

            if (m.collateralTokenSymbol in minRate) and rate < minRate[
                m.collateralTokenSymbol
            ]:
                target_rate = minRate[m.collateralTokenSymbol]
                new_util = min(
                    MAX_UTILIZATION_TARGET,
                    morpho.utils.utilizationForRate(
                        data.borrowRateAtTarget, target_rate
                    ),
                )
                target = data.totalBorrowAssets / new_util
                to_remove = position.supplyAssets - target
                availableLiquidity += to_remove
                print(
                    f"{m.collateralTokenSymbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to remove {to_remove:,.0f} ({data.totalSupplyAssets:,.0f} -> {target:,.0f})"
                )
                if to_remove > 0:
                    actions.append((target, -to_remove, m.marketParams()))

        to_add = 0
        # Second pass to find where more liquidity is ndeed
        for m in self.vault.getBorrowMarkets():
            rate = m.borrowRate()
            data = m.marketData()
            position = m.position(self.vault.address)

            if (m.collateralTokenSymbol in minRate) and rate > maxRate[
                m.collateralTokenSymbol
            ]:
                target_rate = maxRate[m.collateralTokenSymbol]
                new_util = morpho.utils.utilizationForRate(
                    data.borrowRateAtTarget, target_rate
                )
                if new_util > 0:
                    target = data.totalBorrowAssets / new_util
                else:
                    target = data.totalBorrowAssets + 100000 * pow(
                        10, self.vault.assetDecimals
                    )  ## Min allocation if no borrow

                to_add = target - data.totalSupplyAssets
                neededLiquidity += to_add
                log(
                    f"{m.collateralTokenSymbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to add {to_add:,.0f} ({data.totalSupplyAssets:,.0f} -> {target:,.0f})"
                )
                if to_add > 0:
                    actions.append((target, to_add, m.marketParams()))

        # If there is not enough liquidity from active market, add the idle market first
        print(f"Available {availableLiquidity:,.0f} needed {neededLiquidity:,.0f}")
        if (
            availableLiquidity < neededLiquidity
            or overflowMarket.borrowRate() > targetBaseRate + 0.01
        ):
            # Unwind the sDAI bot
            sDAIBotUnwinded = True

            # take all liquidity from sDAI market
            overflowLiquidity = (
                overflowMarketData.totalSupplyAssets
                - overflowMarketData.totalBorrowAssets
            )
            if overflowLiquidity > 0:
                log(
                    f"{m.collateralTokenSymbol}: Take all liquidity {availableLiquidity:,.0f} ({overflowMarketData.totalSupplyAssets:,.0f} -> {overflowMarketData.totalBorrowAssets:,.0f})"
                )
                if to_add > 0:
                    actions.append(
                        (
                            overflowMarketData.totalBorrowAssets,
                            -overflowLiquidity,
                            m.marketParams(),
                        )
                    )

        # If we don't have enough liquidity scale down expectations
        if neededLiquidity > 0 and availableLiquidity < neededLiquidity:
            ratio = availableLiquidity / neededLiquidity
            log(
                f"Not enough available liquidity ({availableLiquidity:,.0f} vs {neededLiquidity:,.0f}). Reduce needs to {ratio*100.0:.2f}%"
            )

            neededLiquidity = availableLiquidity

            for i, action in enumerate(actions):
                if action[1] > 0 and action[1] > 0:
                    actions[i] = (
                        action[0] - (1 - ratio) * action[1],
                        ratio * action[1],
                        action[2],
                    )

        if len(actions) == 0 or max(availableLiquidity, neededLiquidity) < float(
            os.environ.get("REBALANCING_THRESHOLD")
        ):
            log(
                f"Nothing to do {max(availableLiquidity, neededLiquidity):,.0f} < {float(os.environ.get('REBALANCING_THRESHOLD')):,.0f}"
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
                + f'[{action[2].toGnosisSafeString()}, "{math.floor(action[0]*pow(10,self.vault.assetDecimals)):.0f}"]'
            )

        script = (
            script
            + f', [{overflowMarket.params.toGnosisSafeString()}, "{OVERFLOW_AMOUNT}"]]'
        )

        print(script)

        if execute:
            privateKey = os.environ.get("PRIVATE_KEY")
            maxGas = int(os.environ.get("MAX_GWEI"))
            script = []
            for i, action in enumerate(actions):
                # script = script + [((action[2].loanToken, action[2].collateralToken, action[2].oracle, action[2].irm, action[2].lltv), math.floor(action[0]*pow(10,self.vault.assetDecimals)))]
                script = script + [
                    (
                        action[2].toTuple(),
                        math.floor(action[0] * pow(10, self.vault.assetDecimals)),
                    )
                ]
            script = script + [(overflowMarket.params.toTuple(), OVERFLOW_AMOUNT)]
            # print(script)
            account = Account.from_key(privateKey)
            account_address = account.address
            # print(account_address)
            tx = self.vault.contract.functions.reallocate(script).build_transaction(
                {"from": account_address}
            )
            nonce = self.web3.eth.get_transaction_count(account.address)
            tx["nonce"] = nonce
            signed_transaction = account.sign_transaction(tx)
            log(f"gas prices => {self.web3.eth.generate_gas_price()/pow(10,9):,.0f}")
            if self.web3.eth.generate_gas_price() < Web3.to_wei(maxGas, "gwei"):
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
            print("Work only for steakUSDC for now")
            return

        sDAIBotUnwinded = False

        (a0, aRate, a1) = competition.aaveV3Rates(self.web3, self.vault.asset)

        (a0, aRateDay, a1) = competition.aaveV3Rates(self.web3, self.vault.asset, 7200)

        targetBaseRate = 0.047

        minRate = dict()
        minRate["wstETH"] = (
            targetBaseRate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        minRate["wbIB01"] = targetBaseRate + 0.001
        maxRate = dict()
        maxRate["wstETH"] = (
            targetBaseRate  # max(min(aRate, aRateDay) * 0.80, min(aRate, 0.047))
        )
        maxRate["wbIB01"] = targetBaseRate + 0.001
        OVERFLOW_AMOUNT = 115792089237316195423570985008687907853269984665640564039457584007913129639935
        MAX_UTILIZATION_TARGET = 0.995

        overflowMarket = self.vault.getMarketByCollateral("sDAI")
        overflowMarketData = overflowMarket.marketData()
        availableLiquidity = 0
        neededLiquidity = 0
        actions = []

        if overflowMarket in minRate:
            print(f"You can't have a min rate for the overflow market {overflowMarket}")

        # Ensure we empty the idle market
        idleMarket = self.vault.getIdleMarket()
        idleMarketData = idleMarket.marketData()
        idlePosition = idleMarket.position(self.vault.address)
        if idleMarketData.totalSupplyAssets > 0:
            log(
                f"Idle: Need to remove {idleMarketData.totalSupplyAssets:,.0f} ({idleMarketData.totalSupplyAssets:,.0f} -> {0:,.0f})"
            )
            availableLiquidity += idlePosition.supplyAssets
            actions = [
                (0, -idleMarketData.totalSupplyAssets, idleMarket.marketParams())
            ] + actions  # 0 instead of target just for safety

        # First pass to check for excess liquidity markets
        for m in self.vault.getBorrowMarkets():
            rate = m.borrowRate()
            data = m.marketData()
            position = m.position(self.vault.address)

            if (m.collateralTokenSymbol in minRate) and rate < minRate[
                m.collateralTokenSymbol
            ]:
                target_rate = minRate[m.collateralTokenSymbol]
                new_util = min(
                    MAX_UTILIZATION_TARGET,
                    morpho.utils.utilizationForRate(
                        data.borrowRateAtTarget, target_rate
                    ),
                )
                target = data.totalBorrowAssets / new_util
                to_remove = position.supplyAssets - target
                availableLiquidity += to_remove
                print(
                    f"{m.collateralTokenSymbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to remove {to_remove:,.0f} ({data.totalSupplyAssets:,.0f} -> {target:,.0f})"
                )
                if to_remove > 0:
                    actions.append((target, -to_remove, m.marketParams()))

        to_add = 0
        # Second pass to find where more liquidity is ndeed
        for m in self.vault.getBorrowMarkets():
            rate = m.borrowRate()
            data = m.marketData()
            position = m.position(self.vault.address)

            if (m.collateralTokenSymbol in minRate) and rate > maxRate[
                m.collateralTokenSymbol
            ]:
                target_rate = maxRate[m.collateralTokenSymbol]
                new_util = morpho.utils.utilizationForRate(
                    data.borrowRateAtTarget, target_rate
                )
                if new_util > 0:
                    target = data.totalBorrowAssets / new_util
                else:
                    target = data.totalBorrowAssets + 100000 * pow(
                        10, self.vault.assetDecimals
                    )  ## Min allocation if no borrow

                to_add = target - data.totalSupplyAssets
                neededLiquidity += to_add
                log(
                    f"{m.collateralTokenSymbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to add {to_add:,.0f} ({data.totalSupplyAssets:,.0f} -> {target:,.0f})"
                )
                if to_add > 0:
                    actions.append((target, to_add, m.marketParams()))

        # If there is not enough liquidity from active market, add the idle market first
        print(f"Available {availableLiquidity:,.0f} needed {neededLiquidity:,.0f}")
        if (
            availableLiquidity < neededLiquidity
            or overflowMarket.borrowRate() > targetBaseRate + 0.01
        ):
            # Unwind the sDAI bot
            sDAIBotUnwinded = True

            # take all liquidity from sDAI market
            overflowLiquidity = (
                overflowMarketData.totalSupplyAssets
                - overflowMarketData.totalBorrowAssets
            )
            if overflowLiquidity > 0:
                log(
                    f"{m.collateralTokenSymbol}: Take all liquidity {availableLiquidity:,.0f} ({overflowMarketData.totalSupplyAssets:,.0f} -> {overflowMarketData.totalBorrowAssets:,.0f})"
                )
                if to_add > 0:
                    actions.append(
                        (
                            overflowMarketData.totalBorrowAssets,
                            -overflowLiquidity,
                            m.marketParams(),
                        )
                    )

        # If we don't have enough liquidity scale down expectations
        if neededLiquidity > 0 and availableLiquidity < neededLiquidity:
            ratio = availableLiquidity / neededLiquidity
            log(
                f"Not enough available liquidity ({availableLiquidity:,.0f} vs {neededLiquidity:,.0f}). Reduce needs to {ratio*100.0:.2f}%"
            )

            neededLiquidity = availableLiquidity

            for i, action in enumerate(actions):
                if action[1] > 0 and action[1] > 0:
                    actions[i] = (
                        action[0] - (1 - ratio) * action[1],
                        ratio * action[1],
                        action[2],
                    )

        if len(actions) == 0 or max(-availableLiquidity, neededLiquidity) < float(
            os.environ.get("REBALANCING_THRESHOLD")
        ):
            log(
                f"Nothing to do {max(-availableLiquidity, neededLiquidity):,.0f} < {float(os.environ.get('REBALANCING_THRESHOLD')):,.0f}"
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
                + f'[{action[2].toGnosisSafeString()}, "{math.floor(action[0]*pow(10,self.vault.assetDecimals)):.0f}"]'
            )

        script = (
            script
            + f', [{overflowMarket.params.toGnosisSafeString()}, "{OVERFLOW_AMOUNT}"]]'
        )

        print(script)

        if execute:
            privateKey = os.environ.get("PRIVATE_KEY")
            maxGas = int(os.environ.get("MAX_GWEI"))
            script = []
            for i, action in enumerate(actions):
                # script = script + [((action[2].loanToken, action[2].collateralToken, action[2].oracle, action[2].irm, action[2].lltv), math.floor(action[0]*pow(10,self.vault.assetDecimals)))]
                script = script + [
                    (
                        action[2].toTuple(),
                        math.floor(action[0] * pow(10, self.vault.assetDecimals)),
                    )
                ]
            script = script + [(overflowMarket.params.toTuple(), OVERFLOW_AMOUNT)]
            # print(script)
            account = Account.from_key(privateKey)
            account_address = account.address
            # print(account_address)
            tx = self.vault.contract.functions.reallocate(script).build_transaction(
                {"from": account_address}
            )
            nonce = self.web3.eth.get_transaction_count(account.address)
            tx["nonce"] = nonce
            signed_transaction = account.sign_transaction(tx)
            log(f"gas prices => {self.web3.eth.generate_gas_price()/pow(10,9):,.0f}")
            if self.web3.eth.generate_gas_price() < Web3.to_wei(maxGas, "gwei"):
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
        self.do_summary("")
        self.do_competition("")
        self.do_reallocation("execute")
        self.do_borrowers("")


if __name__ == "__main__":

    morpho_cli_start = time.time()
    print("Starting Morpho CLI: ", datetime.fromtimestamp(morpho_cli_start))

    if len(sys.argv) > 1:
        MorphoCli().onecmd(" ".join(sys.argv[1:]))
    else:
        MorphoCli().cmdloop()

    morpho_cli_end = time.time()
    print("Ending Morpho CLI: ", datetime.fromtimestamp(morpho_cli_end))
    print("Total time: ", morpho_cli_end - morpho_cli_start)
