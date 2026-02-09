import json
import os
import pandas as pd
from utils import to_csv_rows

JSONL_PATH = "output/vagas_output.jsonl"
CSV_PATH = "output/vagas_output.csv"

def read_jsonl(path: str):
    if not os.path.exists(path):
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items

def export_csv():
    items = read_jsonl(JSONL_PATH)
    if not items:
        print("Sem dados no JSONL.")
        return

    rows = to_csv_rows(items)
    df = pd.DataFrame(rows)

    # (opcional) dedupe por URL aqui
    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"], keep="last")

    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"Exportado CSV: {CSV_PATH} (linhas: {len(df)})")

if __name__ == "__main__":
    export_csv()
