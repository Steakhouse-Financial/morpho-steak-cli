from abc import ABC, abstractmethod
from .morphomarket import MorphoMarket
from .market_rewards import MarketRewards
from dataclasses import dataclass

from .utils import rate_from_target
from typing import Self


@dataclass(frozen=True)
class AllocationItem:
    market: MorphoMarket
    rewards: MarketRewards
    exposure: float
    supply: float
    borrow: float
    rate_u_target: float

    @property
    def utilization(self) -> float:
        return self.borrow / self.supply

    @property
    def base_apy(self) -> float:
        return rate_from_target(self.rate_u_target, self.utilization)

    @property
    def rewards_apr(self) -> float:
        return self.rewards.apr(self.supply)

    @property
    def total_apy(self) -> float:
        return self.base_apy + self.rewards_apr  # apr should be converted to apy maybe

    @property
    def liquidity(self) -> float:
        return min(self.exposure, self.supply - self.borrow)

    def __repr__(self) -> str:
        return (
            f"{self.market.collateralTokenSymbol}: {self.exposure:,.0f} "
            + f"({self.borrow:,.0f}/{self.supply:,.0f} / {self.borrow/self.supply*100:.2f}%) "
            + f"apy: {self.total_apy*100:.2f}% ( {self.base_apy*100:.2f}% + {self.rewards_apr*100:.2f}%)"
        )

    def copy(self, delta: float) -> Self:
        return AllocationItem(
            self.market,
            self.rewards,
            self.exposure + delta,
            self.supply + delta,
            self.borrow,
            self.rate_u_target,
        )

    def copy_without_liquidity(self) -> tuple[Self, float]:
        return (
            AllocationItem(
                self.market,
                self.rewards,
                self.exposure - self.liquidity,
                self.supply - self.liquidity,
                self.borrow,
                self.rate_u_target,
            ),
            self.liquidity,
        )


@dataclass(frozen=True)
class Allocation:
    items: list[AllocationItem]

    @property
    def total_apy(self) -> float:
        total_exposure = sum([i.exposure for i in self.items])
        if total_exposure == 0:
            return max([i.total_apy for i in self.items])
        else:
            return sum([i.total_apy * i.exposure for i in self.items]) / total_exposure

    @property
    def apy_deviation(self) -> float:
        """Return the average deviation in term on supply apy on the underlying items"""
        average = sum([i.total_apy for i in self.items]) / len(self.items)
        return sum([abs(i.total_apy - average) for i in self.items]) / len(self.items)

    @property
    def liquidity(self) -> float:
        return sum([i.liquidity for i in self.items])

    def __repr__(self) -> str:
        return (
            "\n".join(str(i) for i in self.items)
            + f"\nTotal vault {self.total_apy*100:.2f}% liquidity {self.liquidity:,.0f}"
            + f" apy deviation {self.apy_deviation*100:,.2f}%\n"
        )

    def copy_without_liquidity(self) -> tuple[Self, float]:
        tuples = [i.copy_without_liquidity() for i in self.items]
        items, liquidities = zip(*tuples)  # Unpack tuples into separate variables
        return Allocation(list(items)), sum(list(liquidities))

    def allocate_to(self, idx: int, amount: float) -> Self:
        """Allocate an amount to item idx"""
        items = map(
            lambda i: self.items[i].copy(amount) if i == idx else self.items[i],
            range(0, len(self.items)),
        )
        return Allocation(list(items))


class ReallocationStrategy(ABC):
    """Abstract class that define a reallocation strategy"""

    @abstractmethod
    def reallocate(self, allocation: Allocation) -> Allocation:
        pass


@dataclass(frozen=True)
class ReallocationParamsMarket:
    market: MorphoMarket
    target: float

    def __repr__(self) -> str:
        return (
            f'[["{self.market.loanToken}", '
            f'"{self.market.collateralToken}", '
            f'"{self.market.oracleContract}", '
            f'"{self.market.irmContract}", '
            f'"{self.market.lltv}"], '
            f'"{self.target * self.market.loanTokenFactor}"]'
        )


@dataclass(frozen=True)
class ReallocationParams:
    items: list[ReallocationParamsMarket]

    def __repr__(self) -> str:
        return "[" + ", ".join(str(i) for i in self.items) + "]"


def reallocation_params(starting: Allocation, ending: Allocation) -> ReallocationParams:
    """Provide the reallocation parameters for a MetaMorpho to move
    from starting allocation to ending allocation.
    Assume both allocation have the same market (but order doesn't matter).
    """
    # zip and make sure both allocation items are sorted the same order
    starting.items.sort(key=lambda i: i.market.id)
    ending.items.sort(key=lambda i: i.market.id)
    items = list(zip(starting.items, ending.items))

    # order from decreasing target to increasing targets
    items.sort(key=lambda t: t[1].exposure - t[0].exposure)

    items = list(
        map(lambda t: ReallocationParamsMarket(t[1].market, t[1].exposure), items)
    )

    items.append(
        ReallocationParamsMarket(
            items[0].market,
            115792089237316195423570985008687907853269984665640564039457584007913129639935,
        )
    )
    return ReallocationParams(items)
