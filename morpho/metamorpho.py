import json

from .morphomarket import MorphoMarket, Position
from .morphoblue import MorphoBlue

class MetaMorpho:    
    def __init__(self, web3, address):
        self.address = address
        self.abi = json.load(open('abis/metamorpho.json'))
        self.address = web3.toChecksumAddress(address)
        self.contract = web3.eth.contract(address=self.address, abi=self.abi)
        morphoAddress = self.contract.functions.MORPHO().call()
        self.symbol = self.contract.functions.symbol().call()
        self.name = self.contract.functions.name().call()
        self.asset = self.contract.functions.asset().call()
        self.assetContract = web3.eth.contract(address=self.asset, abi=json.load(open('abis/erc20.json')))
        self.assetDecimals = self.assetContract.functions.decimals().call()
        self.assetSymbol = self.assetContract.functions.symbol().call()

        self.blue = MorphoBlue(web3, morphoAddress, '')

        self.initMarkets()

    def totalAssets(self):
        return self.contract.functions.totalAssets().call() / pow(10, self.assetDecimals)
    
    def initMarkets(self):
        self.markets = []
        nb = self.contract.functions.withdrawQueueLength().call()
        for i in range(0, nb):
            market = self.blue.addMarket(self.contract.functions.withdrawQueue(i).call())
            self.markets.append(market)
    
    def summary(self):
        totalAssets = self.totalAssets();
        print('{0} - {1} - Assets: {2:,.2f}'.format(self.symbol, self.name, totalAssets))
        vaultRate = 0.0;
        for m in self.markets:
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets
            print('{0} - rates: {1:.3f}%/{2:.3f}%, invested: {3:,.2f} ({6:.1f}%), utilization: {4:.1f}%, represents: {5:.1f}%'.format(
                m.name(), marketData.supplyRate*100.0, marketData.borrowRate*100.0, position.supplyAssets, marketData.utilization*100.0,
                position.supplyAssets/marketData.totalSupplyAssets*100.0,
                position.supplyAssets/totalAssets*100.0
                ))
        vaultRate = vaultRate / totalAssets
        print('{0} rate {1:.2f}%'.format(self.symbol, vaultRate*100.0))
