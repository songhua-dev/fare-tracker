"""
scripts/export_airports.py

跑一次，把 fli 內建的機場代碼清單匯出成 CSV，
給 src/flight_search.py 的 _validate_airport_code() 拿來驗證使用者輸入。

用法（在專案根目錄執行）：
    python scripts/export_airports.py
"""

import csv
from pathlib import Path

from fli.models import Airport

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "airports.csv"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["code", "name"])
        for airport in Airport:
            writer.writerow([airport.name, airport.value])

    print(f"已匯出 {len(Airport)} 個機場到 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()