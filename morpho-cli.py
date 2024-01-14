from web3 import Web3
from dotenv import load_dotenv
import morpho
from morpho import MorphoBlue, MetaMorpho
import os
import sys
import cmd
import math
import competition
from texttable import Texttable

load_dotenv()


class MorphoCli(cmd.Cmd):
    intro = 'Welcome to Steakhouse CLI.   Type help or ? to list commands.\n'
    prompt = '>> '
    vault = None 
    web3 = None 

    def __init__(self):
        cmd.Cmd.__init__(self)
        # Connect to web3
        self.web3 = Web3(Web3.HTTPProvider(os.environ.get('WEB3_HTTP_PROVIDER')))
        if(not self.web3.isConnected()):
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
        for m in self.vault.markets:
            p = m.position(address)
            print("{0}: supply: {1:,.0f} borrow: {2:,.0f} collateral: {3:,.0f} ltv: {4:.1f}%".format(m.name(), p.supplyAssets, p.borrowAssets, p.collateralValue, p.ltv*100.0))
        print()

    def do_prices(self, address):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        for m in self.vault.markets:
            p = m.collateralPrice()
            print("{0}/{1} = {2:.2f}".format(m.collateralTokenSymbol, m.loanTokenSymbol, p))
        print()


    def do_borrowers(self, address):
        if self.vault is None:
            print("First add a MetaMorpho vault")
            return
        for m in self.vault.markets:
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

        (supplyRate, borrowRate, cnt) = competition.sparkRates(self.web3) # Use DAI for Spark
        table.add_row(["Spark DAI", f"{supplyRate*100:.2f}%", f"{borrowRate*100:.2f}%", cnt])
        table.add_row(["=========", "", "", ""])

        for m in self.vault.markets:
            rate = m.borrowRate()
            table.add_row([m.collateralTokenSymbol, f"{self.vault.rate()*100:.2f}%", f"{rate*100:.2f}%", cnt])

        print(table.draw())


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
        minRate["wbIB01"] = 0.5
        maxRate = dict()
        maxRate["wstETH"] = aRate
        maxRate["wbIB01"] = 0.5
        overflowMarket = "wbIB01"
        OVERFLOW_AMOUNT = "115792089237316195423570985008687907853269984665640564039457584007913129639935"
        overflowAmount = 0
        UTIL_UP = 0.98

        overflowMarket = self.vault.getMarketByCollateral(overflowMarket)
        overflowMarketData = overflowMarket.marketData()
        availableLiquidity = 0
        neededLiquidity = 0
        actions = []

        if overflowMarket in minRate:
            print(f"You can't have a min rate for the overflow market {overflowMarket}")
        
        # First pass to check for excess liquidity markets
        for m in self.vault.markets:
            rate = m.borrowRate()
            data = m.marketData()

            if ((m.collateralTokenSymbol in minRate)
                    and rate < minRate[m.collateralTokenSymbol]):
                target_rate = minRate[m.collateralTokenSymbol]
                new_util = morpho.utils.utilizationForRate(data.borrowRateAtTarget, target_rate)
                target = data.totalBorrowAssets / new_util
                to_remove = data.totalSupplyAssets - target
                overflowAmount += to_remove
                availableLiquidity += to_remove
                print(f"{m.collateralTokenSymbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to remove {to_remove:,.0f} ({data.totalSupplyAssets:,.0f} -> {target:,.0f})")
                actions.append((target, -to_remove, m.marketParams()))

                
        # Second pass to find where more liquidity is ndeed
        for m in self.vault.markets:
            rate = m.borrowRate()
            data = m.marketData()

            if ((m.collateralTokenSymbol in minRate)
                    and rate > maxRate[m.collateralTokenSymbol]):
                target_rate = maxRate[m.collateralTokenSymbol]
                new_util = morpho.utils.utilizationForRate(data.borrowRateAtTarget, target_rate)
                target = data.totalBorrowAssets / new_util
                to_add = target - data.totalSupplyAssets
                neededLiquidity += to_add
                print(f"{m.collateralTokenSymbol}: Need {new_util*100:.1f}% utilization to get {target_rate*100:.2f}% borrow rate. Need to add {to_add:,.0f} ({data.totalSupplyAssets:,.0f} -> {target:,.0f})")
                actions.append((target, to_add, m.marketParams()))


        # If we don't have enough liquidity scale down expectations
        if availableLiquidity < neededLiquidity:
            ratio = availableLiquidity / neededLiquidity

            for action in actions:
                if action[1] > 0:
                    action[0] = action[0]*ratio

        if len(actions) == 0:
            print("Nothing to do")
            return

        # print(actions)

        script = "["

        for i, action in enumerate(actions):
            if i != 0:
                script = script + ", "
            script = script + f"[{action[2].toGnosisSafeString()}, \"{math.floor(action[0]*pow(10,self.vault.assetDecimals)):.0f}\"]"

        script = script + f", [{overflowMarket.params.toGnosisSafeString()}, \"{OVERFLOW_AMOUNT}\"]]"

        print(script)





if __name__ == '__main__':
    if len(sys.argv) > 1:
        MorphoCli().onecmd(' '.join(sys.argv[1:]))
    else:
        MorphoCli().cmdloop()