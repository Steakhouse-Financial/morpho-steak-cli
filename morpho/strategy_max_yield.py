from morpho.reallocation_strategy import Allocation, ReallocationStrategy


class StrategyMaxYield(ReallocationStrategy):
    """Strategy that allocate capital to maximize the vault total APY
    This strategy has the drawback of trying to put some market at 100% utlization.
    Works best when the vault is small compared to the other Morpho competitors.
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
        """Add the amount to allocation item that decrease the least the apy"""
        solutions = map(
            lambda idx: allocation.allocate_to(idx, amount),
            range(0, len(allocation.items)),
        )
        return max(solutions, key=lambda a: a.total_apy)
