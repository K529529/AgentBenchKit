def merge_intervals(intervals):
    values = sorted((a, b) for a, b in intervals)
    result = []
    for a, b in values:
        if a > b:
            raise ValueError("reversed interval")
        if result and a <= result[-1][1]:
            result[-1] = (result[-1][0], max(b, result[-1][1]))
        else:
            result.append((a, b))
    return result
