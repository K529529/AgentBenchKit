from parsing import parse_rows


def totals(text):
    result = {}
    for row in parse_rows(text):
        result[row["item"]] = result.get(row["item"], 0) + row["quantity"] * row["price"]
    return result
