POW_10_18 = pow(10, 18)
POW_10_36 = pow(10, 36)

TARGET_UTILIZATION = 0.9
CURVE_STEEPNESS = 4


def secondToAPYRate(second):
    return (second * 365 * 24 * 3600) / POW_10_18


def error(utilization):
    if utilization > TARGET_UTILIZATION:
        return (utilization - TARGET_UTILIZATION) / (1 - TARGET_UTILIZATION)
    else:
        return (utilization - TARGET_UTILIZATION) / TARGET_UTILIZATION


def curve(utilization):
    err = error(utilization)
    if utilization > TARGET_UTILIZATION:
        return (CURVE_STEEPNESS - 1) * err + 1
    else:
        return (1 - 1 / CURVE_STEEPNESS) * err + 1


def rateToTargetRate(rate, utilization):
    return rate / curve(utilization)


def rate_from_target(rate_at_target: float, utilization: float) -> float:
    """From a given rate at target and an utilization ratio returns the borrow rate"""
    if utilization > TARGET_UTILIZATION:
        return rate_at_target * (1 + error(utilization) * (CURVE_STEEPNESS - 1))
    else:
        return rate_at_target * (
            1 + error(utilization) * (CURVE_STEEPNESS - 1) / CURVE_STEEPNESS
        )


# From a current target rate, find the utilization ratio that match the wanted borrow rate
def utilizationForRate(targetRate, rate):
    if rate > targetRate:
        maxRate = CURVE_STEEPNESS * targetRate
        if rate > maxRate:
            return 1.0
        else:
            return TARGET_UTILIZATION + (1 - TARGET_UTILIZATION) * (
                rate - targetRate
            ) / (maxRate - targetRate)
    else:
        minRate = (1 / CURVE_STEEPNESS) * targetRate
        if rate < minRate:
            return 0.0
        else:
            return TARGET_UTILIZATION * (rate - minRate) / (targetRate - minRate)
