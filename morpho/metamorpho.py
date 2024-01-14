import json
import datetime

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

    def getMarketByCollateral(self, collateral):
        for m in self.markets:
            if collateral == m.collateralTokenSymbol:
                return m
        print(f"Market with collateral {collateral} doesn't excist for the MetaMorpho")
    
    def summary(self):
        totalAssets = self.totalAssets();
        now = datetime.datetime.now()
        print(f"{self.symbol} - {self.name} - Assets: {totalAssets:,.2f} - {now:%H:%M:%S}")
        vaultRate = 0.0;
        for m in self.markets:
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets
            utilization = position.supplyAssets/totalAssets*100.0 if totalAssets else 0
            metaRepresent = position.supplyAssets/marketData.totalSupplyAssets*100.0 if marketData.totalSupplyAssets else 0
            print(f"{m.name()} - rates: {marketData.supplyRate*100.0:.3f}%/{marketData.borrowRate*100.0:.5f}%[{marketData.borrowRateAtTarget*100.0:.5f}%] "+
                  f"exposure: {position.supplyAssets:,.2f} ({utilization:.1f}%), util: {marketData.utilization*100.0:.1f}%, vault %: {metaRepresent:.1f}%"
                )
        vaultRate = vaultRate / totalAssets
        print('{0} rate {1:.2f}%'.format(self.symbol, vaultRate*100.0))


        
    def rate(self):
        totalAssets = self.totalAssets();
        vaultRate = 0.0;
        for m in self.markets:
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets

        vaultRate = vaultRate / totalAssets
        return vaultRate
