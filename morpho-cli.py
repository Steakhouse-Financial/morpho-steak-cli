from web3 import Web3
from web3 import Account

from dotenv import load_dotenv
import morpho
from morpho import MorphoBlue, MetaMorpho
import os
import sys
import cmd
import math
import competition
from texttable import Texttable
import datetime

load_dotenv()

def log(message, addTimestamp = True):
    print(message)
    if os.environ.get('LOG_FILE') != "":
        with open(os.environ.get('LOG_FILE'), 'a') as file:
            if addTimestamp:
                file.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S - "))
            file.write(f"{message}\n")


class MorphoCli(cmd.Cmd):
    intro = 'Welcome to Steakhouse CLI.   Type help or ? to list commands.\n'
    prompt = '>> '
    vault = None 
    web3 = None 

    def __init__(self):
        cmd.Cmd.__init__(self)
        # Connect to web3
        self.web3 = Web3(Web3.HTTPProvider(os.environ.get('WEB3_HTTP_PROVIDER')))
        if(not self.web3.is_connected()):
            raise Exception("Issue to connect to Web3")
        
        # init morpho
        # morpho = MorphoBlue(web3, os.environ.get('MORPHO_BLUE'), os.environ.get('MORPHO_BLUE_MARKETS'))
        # print(morpho.marketData('0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc'))
        if os.environ.get('META_MORPHO') != '':
            self.vault = MetaMorpho(self.web3, os.environ.get('META_MORPHO'))
            #print("Vault {0} loaded".format(self.vault.name))
    
    
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
            print("{0}: supply: {1:,.0f} borrow: {2:,.0f} collateral: {3:,.0f} ltv: {4:.1f}%".format(m.name(), p.supplyAssets, p.borrowAssets, p.collateralValue, p.ltv*100.0))
        print()

    def do_prices(self, address):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        for m in self.vault.getBorrowMarkets():
            p = m.collateralPrice()
            print("{0}/{1} = {2:.2f}".format(m.collateralTokenSymbol, m.loanTokenSymbol, p))
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


    def do_competition(self, args):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        
        table = Texttable()
        table.header(["Protocol", "Supply", "Borrow", "Obs"])
        table.set_cols_align(['l', 'r', 'r', 'r'])
        table.set_deco(Texttable.HEADER )
        
        (supplyRate, borrowRate, cnt) = competition.aaveV3Rates(self.web3, self.vault.asset)        
        table.add_row(["Aave v3", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt])

        (supplyRate, borrowRate, cnt) = competition.aaveV3Rates(self.web3, self.vault.asset, 7200)        
        table.add_row(["Aave v3 1d", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt])

        (supplyRate, borrowRate, cnt) = competition.aaveV3Rates(self.web3, self.vault.asset, 7*7200)        
        table.add_row(["Aave v3 7d", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt])

        (supplyRate, borrowRate, cnt) = competition.sparkRates(self.web3) # Use DAI for Spark
        table.add_row(["Spark DAI", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt])
        table.add_row(["=========", "", "", ""])

        for m in self.vault.getBorrowMarkets():
            rate = m.borrowRate()
            table.add_row([m.collateralTokenSymbol, f"{self.vault.rate()*100:.2f}%", f"{rate*100:.2f}%", ""])

        print(table.draw())
        print()


    def do_reallocation(self, args):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return

        if self.vault.symbol != "steakUSDC":
            print("Work only for steakUSDC for now")
            return
        
        (a0,aRate,a1) = competition.aaveV3Rates(self.web3, self.vault.asset) 
        
        minRate = dict()
        minRate["wstETH"] = aRate * 0.95
        minRate["wbIB01"] = 0.0477
        maxRate = dict()
        maxRate["wstETH"] = aRate * 0.95
        maxRate["wbIB01"] = 0.0477
        OVERFLOW_AMOUNT = 115792089237316195423570985008687907853269984665640564039457584007913129639935
        MAX_UTILIZATION_TARGET = 0.995

        overflowMarket = self.vault.getIdleMarket()
        overflowMarketData = overflowMarket.marketData()
        availableLiquidity = 0
        neededLiquidity = 0
        actions = []

        if overflowMarket in minRate:
            print(f"You can't have a min rate for the overflow market {overflowMarket}")
        
        # First pass to check for excess liquidity markets
        for m in self.vault.getBorrowMarkets():
            rate = m.borrowRate()
            data = m.marketData()

            if ((m.collateralTokenSymbol in minRate)
                    and rate < minRate[m.collateralTokenSymbol]):
                target_rate = minRate[m.collateralTokenSymbol]
                new_util = min(MAX_UTILIZATION_TARGET, morpho.utils.utilizationForRate(data.borrowRateAtTarget, target_rate))
                target = data.totalBorrowAssets / new_util
                to_remove = data.totalSupplyAssets - target
                availableLiquidity += to_remove
                print(f"{m.collateralTokenSymbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to remove {to_remove:,.0f} ({data.totalSupplyAssets:,.0f} -> {target:,.0f})")
                if to_remove > 0:
                    actions.append((target, -to_remove, m.marketParams()))

                
        # Second pass to find where more liquidity is ndeed
        for m in self.vault.getBorrowMarkets():
            rate = m.borrowRate()
            data = m.marketData()

            if ((m.collateralTokenSymbol in minRate)
                    and rate > maxRate[m.collateralTokenSymbol]):
                target_rate = maxRate[m.collateralTokenSymbol]
                new_util = morpho.utils.utilizationForRate(data.borrowRateAtTarget, target_rate)
                target = data.totalBorrowAssets / new_util
                to_add = target - data.totalSupplyAssets
                neededLiquidity += to_add
                log(f"{m.collateralTokenSymbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to add {to_add:,.0f} ({data.totalSupplyAssets:,.0f} -> {target:,.0f})")
                if to_add > 0:
                    actions.append((target, to_add, m.marketParams()))

        # If there is not enough liquidity from active market, add the idle market first
        print(f"Available {availableLiquidity:,.0f} needed {neededLiquidity:,.0f}")
        if availableLiquidity < neededLiquidity:
            to_remove = min(overflowMarketData.totalSupplyAssets, neededLiquidity - availableLiquidity)
            availableLiquidity += to_remove
            target = overflowMarketData.totalSupplyAssets - to_remove
            log(f"Idle: Need to remove {to_remove:,.0f} ({overflowMarketData.totalSupplyAssets:,.0f} -> {target:,.0f})")
            actions = [(target, -to_remove, overflowMarket.marketParams())] + actions


        # If we don't have enough liquidity scale down expectations
        if availableLiquidity < neededLiquidity:
            ratio = availableLiquidity / neededLiquidity
            log(f"Not enough available liquidity ({availableLiquidity:,.0f} vs {neededLiquidity:,.0f}). Reduce needs to {ratio*100.0:.2f}%")

            neededLiquidity = availableLiquidity

            for i, action in enumerate(actions):
                if action[1] > 0 and action[1] > 0:
                    actions[i] = (action[0]-(1-ratio)*action[1], ratio*action[1], action[2])

        if len(actions) == 0 or max(availableLiquidity, neededLiquidity) < float(os.environ.get('REBALANCING_THRESHOLD')):
            log(f"Nothing to do {max(availableLiquidity, neededLiquidity):,.0f} < {float(os.environ.get('REBALANCING_THRESHOLD')):,.0f}")
            print()
            return

        # Tbd
        #table = Texttable()
        #table.header(["Market", "Delta", "Util", "Obs"])
        #table.set_cols_align(['l', 'r', 'r', 'r'])
        #table.set_deco(Texttable.HEADER )
        # print(actions)

        # print(table.draw())

        print()

        script = "["

        for i, action in enumerate(actions):
            if i != 0:
                script = script + ", "
            script = script + f"[{action[2].toGnosisSafeString()}, \"{math.floor(action[0]*pow(10,self.vault.assetDecimals)):.0f}\"]"

        script = script + f", [{overflowMarket.params.toGnosisSafeString()}, \"{OVERFLOW_AMOUNT}\"]]"

        print(script)

        if args == "execute":
            privateKey = os.environ.get('PRIVATE_KEY')
            script = []            
            for i, action in enumerate(actions):
                #script = script + [((action[2].loanToken, action[2].collateralToken, action[2].oracle, action[2].irm, action[2].lltv), math.floor(action[0]*pow(10,self.vault.assetDecimals)))]
                script = script + [(action[2].toTuple(), math.floor(action[0]*pow(10,self.vault.assetDecimals)))]
            script = script + [(overflowMarket.params.toTuple(), OVERFLOW_AMOUNT)]
            #print(script)
            account = Account.privateKeyToAccount(privateKey)
            account_address = account.address
            #print(account_address)
            tx = self.vault.contract.functions.reallocate(script).build_transaction({
                    "from": account_address
                })
            nonce = self.web3.eth.get_transaction_count(account.address)
            tx['nonce'] = nonce
            signed_transaction = account.signTransaction(tx)
            log(f"gas prices => {self.web3.eth.generate_gas_price()/pow(10,9):,.0f}")
            if self.web3.eth.generate_gas_price() < Web3.to_wei(40, 'gwei'):
                tx_hash = self.web3.eth.send_raw_transaction(signed_transaction.rawTransaction)
                log(f"Executed with hash => {tx_hash.hex()}")
            else:
                log(f"gas price too high => {self.web3.eth.generate_gas_price()/pow(10,9):,.0f}")


        print()


    def do_full(self, args):
        self.do_summary("")
        self.do_competition("")
        self.do_reallocation("execute")
        self.do_borrowers("")



if __name__ == '__main__':
    if len(sys.argv) > 1:
        MorphoCli().onecmd(' '.join(sys.argv[1:]))
    else:
        MorphoCli().cmdloop()