"""
scripts/export_fli_airlines.py

匯出 fli 內建的航空公司清單（AIRLINE_NAMES），存成 CSV。
用法：python scripts/export_fli_airlines.py
"""

import csv
from pathlib import Path

from fli.models.airline import AIRLINE_NAMES

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "fli_airlines.csv"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["airline_code", "airline_name"])
        for code, name in AIRLINE_NAMES.items():
            writer.writerow([code, name])

    print(f"已匯出 {len(AIRLINE_NAMES)} 家航空公司到 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()