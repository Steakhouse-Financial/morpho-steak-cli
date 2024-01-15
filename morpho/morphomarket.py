import json
from morpho.utils import POW_10_18, POW_10_36, secondToAPYRate
from morpho.utils import rateToTargetRate
from dataclasses import dataclass
import time

@dataclass
class Position:
    address: str
    supplyShares: float
    supplyAssets: float
    borrowShares: float
    borrowAssets: float
    collateral: float
    collateralValue: float
    ltv: float

    
@dataclass
class MaketData:
    totalSupplyAssets: float
    totalSupplyShares: float
    totalBorrowAssets: float
    totalBorrowShares: float
    lastUpdate: float
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
            self.irmContract = web3.eth.contract(address=web3.toChecksumAddress(params.irm), abi=json.load(open('abis/irm.json')))
        if params.oracle != "0x0000000000000000000000000000000000000000":
            self.oracleContract = web3.eth.contract(address=web3.toChecksumAddress(params.oracle), abi=json.load(open('abis/oracle.json')))
        self.lastOracleUpdate = 0
        
        # Get some data from erc20
        self.collateralToken = params.collateralToken
        if self.collateralToken != "0x0000000000000000000000000000000000000000":
            self.collateralTokenContract = web3.eth.contract(address=web3.toChecksumAddress(params.collateralToken), abi=json.load(open('abis/erc20.json')))
            self.collateralTokenDecimals = self.collateralTokenContract.functions.decimals().call()
            self.collateralTokenFactor = pow(10, self.collateralTokenDecimals)
            self.collateralTokenSymbol = self.collateralTokenContract.functions.symbol().call()
        else:
            self.collateralTokenSymbol = "Idle"
        self.loanTokenContract = web3.eth.contract(address=web3.toChecksumAddress(params.loanToken), abi=json.load(open('abis/erc20.json')))
        self.loanTokenDecimals = self.loanTokenContract.functions.decimals().call()
        self.loanTokenFactor = pow(10, self.loanTokenDecimals)
        self.loanTokenSymbol = self.loanTokenContract.functions.symbol().call()

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
        if time.time() < self.lastRateUpdate + 5:
            return self.lastRate
        
        marketData = self.blue.marketData(self.id)        
        rawdata =  self.irmContract.functions.borrowRateView(self.params.toTuple(), marketData).call()
        self.lastRate = secondToAPYRate(rawdata)
        self.lastRateUpdate = time.time()
        return self.lastRate


    def rateAtTarget(self):        
        rate = self.borrowRate()        
        ( totalSupplyAssets, totalSupplyShares, totalBorrowAssets, totalBorrowShares, lastUpdate, fee) = self._marketData()
        utilization = totalBorrowAssets/totalSupplyAssets if totalSupplyAssets else 0
        return rateToTargetRate(rate, utilization)

    
    def _marketData(self):
        if time.time() < self.lastMarketDataUpdate + 5:
            return self.lastMarketData
        self.lastMarketData = self.blue.marketData(self.id)
        self.lastMarketDataUpdate = time.time()
        return self.lastMarketData

    def marketParams(self):
        return self.params

    def marketData(self):
        
        ( totalSupplyAssets, totalSupplyShares, totalBorrowAssets, totalBorrowShares, lastUpdate, fee) = self._marketData()

        if self.isIdleMarket():
            return MaketData(totalSupplyAssets/self.loanTokenFactor, 
                         totalSupplyShares/POW_10_18, 
                         totalBorrowAssets/self.loanTokenFactor, 
                         totalBorrowShares/POW_10_18, 
                         lastUpdate, 
                         fee, 
                         0,
                         0,
                         0,
                         0)        

        rate = self.borrowRate()
        rateAtTarget = self.rateAtTarget()
        supplyRate = rate * totalBorrowAssets / totalSupplyAssets if totalSupplyAssets else 0 # TODO: Don't work with fees
        
        return MaketData(totalSupplyAssets/self.loanTokenFactor, 
                         totalSupplyShares/POW_10_18, 
                         totalBorrowAssets/self.loanTokenFactor, 
                         totalBorrowShares/POW_10_18, 
                         lastUpdate, 
                         fee, 
                         totalBorrowAssets/totalSupplyAssets if totalSupplyAssets else 0,
                         supplyRate,
                         rate,
                         rateAtTarget)        


    def position(self, address):
        ( totalSupplyAssets, totalSupplyShares, totalBorrowAssets, totalBorrowShares, lastUpdate, fee) = self.blue.marketData(self.id)
        ( supplyShares , borrowShares , collateral) = self.blue.position(self.id, self.web3.toChecksumAddress(address))
        price = self.collateralPrice()
        borrowAssets = borrowShares * (totalBorrowAssets/self.loanTokenFactor) / totalBorrowShares if totalBorrowShares else 0
        collateralValue = collateral/self.collateralTokenFactor*price
        return Position(address, 
                        supplyShares/POW_10_18, 
                        (supplyShares/POW_10_18) * (totalSupplyAssets/self.loanTokenFactor)/ (totalSupplyShares/POW_10_18)  if totalSupplyShares else 0,
                        borrowShares/POW_10_18, 
                        borrowAssets, 
                        collateral/self.collateralTokenFactor,
                        collateralValue,
                        borrowAssets / collateralValue if collateralValue else 0
                        )
    
    def collateralPrice(self):
        if time.time() < self.lastOracleUpdate + 5:
            return self.oraclePrice
        
        self.lastOracleUpdate = time.time()
        self.oraclePrice = self.oracleContract.functions.price().call() / (self.loanTokenFactor * self.collateralTokenFactor)
        return self.oraclePrice
    
    def borrowers(self):
        borrowers = []
        for b in self.blue.borrowers(self.id):
            borrowers.append(self.position(b))
        return sorted(borrowers, key=lambda p: p.ltv, reverse = True)
