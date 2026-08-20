"""
scripts/build_airline_websites.py

1. 查詢 Wikidata（P229 IATA航空公司代碼、P856 官方網站）
2. 匯入 data/fli_airlines.csv（fli 內建的航空公司清單）
3. 取兩者交集：
   - 有 website 的 -> data/airlines_with_website.csv
   - website 為 None 的 -> data/airlines_missing_website.csv

兩份輸出的欄位順序完全一致（都是 airline_code, airline_name, website），
沒有網址的那份 website 欄位固定填 "none"，避免之後合併兩份檔案時
因為欄位數不一致而對不齊。

用法：python scripts/build_airline_websites.py
（需先跑過 scripts/export_fli_airlines.py 產生 data/fli_airlines.csv）
"""

import csv
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FLI_AIRLINES_PATH = DATA_DIR / "fli_airlines.csv"
WITH_WEBSITE_PATH = DATA_DIR / "airlines_with_website.csv"
MISSING_WEBSITE_PATH = DATA_DIR / "airlines_missing_website.csv"

SPARQL_QUERY = """
SELECT ?iata ?airlineLabel ?website WHERE {
  ?airline wdt:P229 ?iata .
  OPTIONAL { ?airline wdt:P856 ?website . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


def fetch_wikidata_websites() -> dict[str, str]:
    """回傳 {airline_code: website}，只收有 website 的筆數（website 為空的不放進這個 dict）。"""
    response = requests.get(
        "https://query.wikidata.org/sparql",
        params={"query": SPARQL_QUERY, "format": "json"},
        headers={"User-Agent": "flight-ticket-analyzer/1.0"},
    )
    rows = response.json()["results"]["bindings"]

    websites: dict[str, str] = {}
    for row in rows:
        code = row["iata"]["value"]
        website = row.get("website", {}).get("value", "")
        if website:
            websites[code] = website
    return websites


def load_fli_airlines() -> list[tuple[str, str]]:
    """讀 data/fli_airlines.csv，回傳 [(code, name), ...]。"""
    with open(FLI_AIRLINES_PATH, encoding="utf-8") as f:
        return [(row["airline_code"], row["airline_name"]) for row in csv.DictReader(f)]


def main() -> None:
    if not FLI_AIRLINES_PATH.exists():
        raise FileNotFoundError(
            f"{FLI_AIRLINES_PATH} 不存在，請先跑 scripts/export_fli_airlines.py"
        )

    fli_airlines = load_fli_airlines()
    wikidata_websites = fetch_wikidata_websites()

    with_website = []
    missing_website = []

    for code, name in fli_airlines:
        website = wikidata_websites.get(code)  # 查不到或 Wikidata 沒填，都是 None
        if website:
            with_website.append([code, name, website])
        else:
            missing_website.append([code, name, "none"])

    with open(WITH_WEBSITE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["airline_code", "airline_name", "website"])
        writer.writerows(with_website)

    with open(MISSING_WEBSITE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["airline_code", "airline_name", "website"])
        writer.writerows(missing_website)

    total = len(fli_airlines)
    print(f"fli 內建航空公司總數: {total}")
    print(f"有網址: {len(with_website)} 筆 -> {WITH_WEBSITE_PATH}")
    print(f"無網址: {len(missing_website)} 筆 -> {MISSING_WEBSITE_PATH}")
    print(f"涵蓋率: {len(with_website) / total * 100:.1f}%")


if __name__ == "__main__":
    main()