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

    def getIdleMarket(self):
        return list(filter(lambda x: x.isIdleMarket(), self.markets))[0]
    
    def hasIdleMarket(self):
        return len(list(filter(lambda x: x.isIdleMarket(), self.markets))) > 0
    
    def getBorrowMarkets(self):
        return filter(lambda x: not x.isIdleMarket(), self.markets)
    
    def summary(self):
        totalAssets = self.totalAssets();
        now = datetime.datetime.now()
        print(f"{self.symbol} - {self.name} - Assets: {totalAssets:,.2f} - {now:%H:%M:%S}")
        vaultRate = 0.0;
        liquidity = 0.0
        for m in filter(lambda x: not x.isIdleMarket(), self.markets):
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets
            share = position.supplyAssets/totalAssets*100.0 if totalAssets else 0
            metaRepresent = position.supplyAssets/marketData.totalSupplyAssets*100.0 if marketData.totalSupplyAssets else 0
            liquidity += marketData.totalSupplyAssets - marketData.totalBorrowAssets
            print(f"{m.name()} - rates: {marketData.supplyRate*100.0:.3f}%/{marketData.borrowRate*100.0:.5f}%[{marketData.borrowRateAtTarget*100.0:.5f}%] "+
                  f"exposure: {position.supplyAssets:,.2f} ({share:.1f}%), util: {marketData.utilization*100.0:.1f}%, vault %: {metaRepresent:.1f}%"
                )
            
        if self.hasIdleMarket():
            m = self.getIdleMarket()            
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets
            share = position.supplyAssets/totalAssets*100.0 if totalAssets else 0
            metaRepresent = position.supplyAssets/marketData.totalSupplyAssets*100.0 if marketData.totalSupplyAssets else 0
            liquidity += marketData.totalSupplyAssets - marketData.totalBorrowAssets
            print(f"{m.name()} - "+
                  f"exposure: {position.supplyAssets:,.2f} ({share:.1f}%), vault %: {metaRepresent:.1f}%"
                )
            
        vaultRate = vaultRate / totalAssets
        print(f"{self.symbol} rate {vaultRate*100.0:.2f}%, total liquidity {liquidity:,.0f}")


        
    def rate(self):
        totalAssets = self.totalAssets();
        vaultRate = 0.0;
        for m in self.getBorrowMarkets():
            position = m.position(self.address)
            marketData = m.marketData()
            vaultRate += marketData.supplyRate * position.supplyAssets

        vaultRate = vaultRate / totalAssets
        return vaultRate
