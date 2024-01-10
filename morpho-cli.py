from web3 import Web3
from dotenv import load_dotenv
from morpho import MorphoBlue, MetaMorpho
import os
import sys
import cmd

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
            print("Vault {0} loaded".format(self.vault.name))
    
    
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





if __name__ == '__main__':
    if len(sys.argv) > 1:
        MorphoCli().onecmd(' '.join(sys.argv[1:]))
    else:
        MorphoCli().cmdloop()