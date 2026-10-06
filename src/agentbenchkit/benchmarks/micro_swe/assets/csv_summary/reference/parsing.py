import csv
import io


def parse_rows(text):
    return [
        {"item": row["item"], "quantity": int(row["quantity"]), "price": float(row["price"])}
        for row in csv.DictReader(io.StringIO(text))
    ]
