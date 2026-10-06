from parsing import parse_rows


def totals(text):
    return {row["item"]: row["price"] for row in parse_rows(text)}
