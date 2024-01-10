import json
from morpho.utils import POW_10_18, POW_10_36, secondToAPYRate
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



class MorphoMarket:
    
    def __init__(self, web3, blue, id):
        self.web3 = web3
        self.blue = blue
        self.id = id
        params = blue.marketParams(id)
        self.loanToken = params[0]
        self.collateralToken = params[1]
        self.oracle = params[2]
        self.irm = params[3]
        self.lltv = params[4]
        self.irmContract = web3.eth.contract(address=web3.toChecksumAddress(self.irm), abi=json.load(open('abis/irm.json')))
        self.oracleContract = web3.eth.contract(address=web3.toChecksumAddress(self.oracle), abi=json.load(open('abis/oracle.json')))
        self.lastOracleUpdate = 0
        
        # Get some data from erc20
        self.collateralTokenContract = web3.eth.contract(address=web3.toChecksumAddress(self.collateralToken), abi=json.load(open('abis/erc20.json')))
        self.collateralTokenDecimals = self.collateralTokenContract.functions.decimals().call()
        self.collateralTokenFactor = pow(10, self.collateralTokenDecimals)
        self.collateralTokenSymbol = self.collateralTokenContract.functions.symbol().call()
        self.loanTokenContract = web3.eth.contract(address=web3.toChecksumAddress(self.loanToken), abi=json.load(open('abis/erc20.json')))
        self.loanTokenDecimals = self.loanTokenContract.functions.decimals().call()
        self.loanTokenFactor = pow(10, self.loanTokenDecimals)
        self.loanTokenSymbol = self.loanTokenContract.functions.symbol().call()


    def name(self):        
        return "{0}[{1}]".format(self.loanTokenSymbol, self.collateralTokenSymbol)

    def borrowRate(self):
        marketData = self.blue.marketData(self.id)        
        rawdata =  self.irmContract.functions.borrowRateView((self.loanToken, self.collateralToken, self.oracle, self.irm, self.lltv), marketData).call()
        return secondToAPYRate(rawdata)

        
    def rateAtTarget(self):
        return secondToAPYRate(self.irmContract.functions.rateAtTarget(self.id).call())
    
    def marketData(self):
        ( totalSupplyAssets, totalSupplyShares, totalBorrowAssets, totalBorrowShares, lastUpdate, fee) = self.blue.marketData(self.id)
        rate = self.borrowRate()
        supplyRate = rate * totalBorrowAssets / totalSupplyAssets # TODO: Don't work with fees
        return MaketData(totalSupplyAssets/self.loanTokenFactor, 
                         totalSupplyShares/POW_10_18, 
                         totalBorrowAssets/self.loanTokenFactor, 
                         totalBorrowShares/POW_10_18, 
                         lastUpdate, 
                         fee, 
                         totalBorrowAssets/totalSupplyAssets,
                         supplyRate,
                         rate)


    def position(self, address):
        ( totalSupplyAssets, totalSupplyShares, totalBorrowAssets, totalBorrowShares, lastUpdate, fee) = self.blue.marketData(self.id)
        ( supplyShares , borrowShares , collateral) = self.blue.position(self.id, self.web3.toChecksumAddress(address))
        price = self.collateralPrice()
        borrowAssets = borrowShares * (totalBorrowAssets/self.loanTokenFactor) / totalBorrowShares
        collateralValue = collateral/self.collateralTokenFactor*price
        return Position(address, 
                        supplyShares/POW_10_18, 
                        (supplyShares/POW_10_18) * (totalSupplyAssets/self.loanTokenFactor)/ (totalSupplyShares/POW_10_18),
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
