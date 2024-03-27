from morpho.reallocation_strategy import Allocation, ReallocationStrategy


class StrategyEqualYield(ReallocationStrategy):
    """Strategy that minimize the discrepency of supply APY on Morpho Blue markets.
    This strategy only consider market that already have some exposure.
    """

    def reallocate(self, allocation: Allocation) -> Allocation:
        allocation, excess_liquidity = allocation.copy_without_liquidity()
        step = excess_liquidity / 100  # 100 steps
        while excess_liquidity > 0:
            to_allocate = step if step < excess_liquidity else excess_liquidity
            excess_liquidity -= step
            allocation = self._allocate(allocation, to_allocate)

        return allocation

    def _allocate(self, allocation: Allocation, amount: float) -> Allocation:
        """Add the amount to allocation item that reduce market supply APY deviation"""
        solutions = map(
            lambda idx: allocation.allocate_to(idx, amount),
            range(0, len(allocation.items)),
        )
        return min(solutions, key=lambda a: a.apy_deviation)
