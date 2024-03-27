from dataclasses import dataclass


MORPHO_PRICE = 0.5  # $1 per MORPHO token


@dataclass(frozen=True)
class MarketRewards:
    """For a given market provide how many MORPHO per day are given for the market and
    how much additionnal value per day.
    """

    morpho: float = 0.0
    additional: float = 0.0

    def apr(self, amount: float) -> float:
        """For a given market size (amount) provide the annualized percentage rate"""
        return (MORPHO_PRICE * self.morpho + self.additional) * 365.0 / amount


# Constant instance for no reward
ZERO_REWARDS = MarketRewards()


def rewards_for_market(market_id: str) -> MarketRewards:
    """Returns the market rewards for a given market id. Will default to zero rewards
    if there is no metadata for the market
    """
    if (
        market_id
        == "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc"
    ):
        # wstETH/USDC
        return MarketRewards(13000, 4903)
    elif (
        market_id
        == "0x3a85e619751152991742810df6ec69ce473daef99e28a64ab2340d7b7ccfee49"
    ):
        # WBTC/USDC
        return MarketRewards(3888.88, 0)
    elif (
        market_id
        == "0xa921ef34e2fc7a27ccc50ae7e4b154e16c9799d3387076c421423ef52ac4df99"
    ):
        # WBTC/USDT
        return MarketRewards(7777.77, 0)
    else:
        return ZERO_REWARDS
