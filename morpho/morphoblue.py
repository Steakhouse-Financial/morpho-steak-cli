import json
from .morphomarket import MorphoMarket
from dataclasses import dataclass
import os


@dataclass
class MaketParams:
    loan_token: str
    colateral_token: str
    oracle: str
    irm: str
    lltv: str

    def to_gnosis_safe_string(self):
        return (
            f'["{self.loan_token}",'
            f'"{self.colateral_token}",'
            f'"{self.oracle}",'
            f'"{self.irm}",'
            f'"{self.lltv}"]'
        )

    def to_tuple(self):
        return (self.loan_token, self.colateral_token, self.oracle, self.irm, self.lltv)


class MorphoBlue:
    def __init__(self, web3, address, markets=""):
        self.web3 = web3
        self.abi = json.load(open("abis/morphoblue.json"))
        self.address = web3.to_checksum_address(address)
        self.contract = web3.eth.contract(address=self.address, abi=self.abi)

        reader_abi = json.load(open("abis/MorphoReader.json"))
        reader_address = web3.to_checksum_address(os.environ.get("MORPHO_READER"))
        self.reader = web3.eth.contract(address=reader_address, abi=reader_abi)

        self.markets = []
        markets = markets or ""
        for id in markets.split(","):
            if not id == "":
                self.add_market(id.lower().strip())

    def market_data(self, id):
        return self.reader.functions.getMarketData(id).call()

    def market_params(self, id):
        data = self.contract.functions.idToMarketParams(id).call()
        return MaketParams(data[0], data[1], data[2], data[3], data[4])

    def add_market(self, id):
        if isinstance(id, str):
            market = MorphoMarket(self.web3, self, id)
        elif isinstance(id, bytes):
            market = MorphoMarket(self.web3, self, "0x" + id.hex())
        self.markets.append(market)
        return market

    def get_market(self, market):
        if market.startWith("0x"):
            return self.get_market_by_id(market)

    def get_market_by_id(self, id):
        for m in self.markets:
            if m.id == id:
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
