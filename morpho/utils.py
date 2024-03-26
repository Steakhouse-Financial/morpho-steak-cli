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


def rate_to_target_rate(rate, utilization):
    return rate / curve(utilization)


# From a current target rate, find the utilization ration that match the wanted borrow rate
def utilization_for_rate(target_rate, rate):
    if rate > target_rate:
        max_rate = CURVE_STEEPNESS * target_rate
        if rate > max_rate:
            return 1.0
        else:
            return TARGET_UTILIZATION + (1 - TARGET_UTILIZATION) * (
                rate - target_rate
            ) / (max_rate - target_rate)
    else:
        min_rate = (1 / CURVE_STEEPNESS) * target_rate
        if rate < min_rate:
            return 0.0
        else:
            return TARGET_UTILIZATION * (rate - min_rate) / (target_rate - min_rate)
