import json
from .morphomarket import MorphoMarket
from dataclasses import dataclass
import os


@dataclass
class MaketParams:
    loanToken: str
    collateralToken: str
    oracle: str
    irm: str
    lltv: str

    def toGnosisSafeString(self):
        return f'["{self.loanToken}","{self.collateralToken}","{self.oracle}","{self.irm}","{self.lltv}"]'

    def toTuple(self):
        return (self.loanToken, self.collateralToken, self.oracle, self.irm, self.lltv)


class MorphoBlue:

    def __init__(self, web3, address, markets=""):
        self.web3 = web3
        self.abi = json.load(open("abis/morphoblue.json"))
        self.address = web3.to_checksum_address(address)
        self.contract = web3.eth.contract(address=self.address, abi=self.abi)

        readerAbi = json.load(open("abis/MorphoReader.json"))
        readerAddress = web3.to_checksum_address(os.environ.get("MORPHO_READER"))
        self.reader = web3.eth.contract(address=readerAddress, abi=readerAbi)

        self.markets = []
        markets = markets or ""  # if markets is None, set it to ""
        for id in markets.split(","):
            if not id == "":
                self.addMarket(id.lower().strip())

    def marketData(self, id):
        return self.reader.functions.getMarketData(id).call()

    def marketParams(self, id):
        data = self.contract.functions.idToMarketParams(id).call()
        return MaketParams(data[0], data[1], data[2], data[3], data[4])

    def addMarket(self, id):
        market = MorphoMarket(self.web3, self, id)
        self.markets.append(market)
        return market

    def getMarket(self, market):
        if market.startWith("0x"):
            return self.getMarketById(market)

    def getMarketById(self, id):
        for m in self.markets:
            if m.id == id:
                return m

    def getMarket(self, name):
        for m in self.markets:
            if m.name() == name:
                return m

    def position(self, id, address):
        return self.reader.functions.getPosition(id, address).call()

    def borrowers(self, id):
        borrowers = set()
        logs = (
            self.contract.events.Borrow()
            .create_filter(fromBlock=18920518, argument_filters={"id": id})
            .get_all_entries()
        )
        for log in logs:
            borrowers.add(log.args.onBehalf)
        return list(borrowers)
