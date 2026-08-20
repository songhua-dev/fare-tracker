"""
scripts/add_chinese_names.py

讀取 data/airlines_with_website.csv 和 data/airlines_missing_website.csv，
只查詢 Wikidata 的中文名稱（不碰網址，避免查詢過肥導致 JSON 解析失敗），
幫兩份 CSV 各自加上 airline_name_zh 欄位，查不到就填 "none"。

用法：python scripts/add_chinese_names.py
（需先跑過 scripts/build_airline_websites.py 產生這兩份 CSV）
"""

import csv
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WITH_WEBSITE_PATH = DATA_DIR / "airlines_with_website.csv"
MISSING_WEBSITE_PATH = DATA_DIR / "airlines_missing_website.csv"


def load_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_chinese_names(codes: list[str]) -> dict[str, str]:
    """
    只查中文名稱，不查網址。用 VALUES 限定只查這些代碼，
    縮小查詢範圍，避免像上次那樣資料量過大導致 JSON 截斷。

    改用「中文維基百科條目標題」而不是 Wikidata 的標籤欄位——
    標籤欄位要人手動填，常常漏填或沒同步；維基百科條目存在
    與否本身就是一個更可靠、更新更即時的訊號。
    """
    values_clause = " ".join(f'"{code}"' for code in codes)

    query = f"""
    SELECT ?iata ?name_zh WHERE {{
      VALUES ?iata {{ {values_clause} }}
      ?airline wdt:P229 ?iata .
      ?article schema:about ?airline ;
               schema:isPartOf <https://zh.wikipedia.org/> ;
               schema:name ?name_zh .
    }}
    """

    response = requests.post(
        "https://query.wikidata.org/sparql",
        data={"query": query, "format": "json"},
        headers={
            "User-Agent": "flight-ticket-analyzer/1.0",
            "Accept": "application/sparql-results+json",
        },
    )
    response.raise_for_status()
    rows = response.json()["results"]["bindings"]

    names_zh: dict[str, str] = {}
    for row in rows:
        code = row["iata"]["value"]
        name_zh = row.get("name_zh", {}).get("value", "")
        names_zh[code] = name_zh
    return names_zh


def write_csv_with_chinese(path: Path, rows: list[dict], names_zh: dict[str, str]) -> None:
    fieldnames = list(rows[0].keys()) + ["airline_name_zh"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row["airline_name_zh"] = names_zh.get(row["airline_code"]) or "none"
            writer.writerow(row)


def main() -> None:
    with_website_rows = load_csv(WITH_WEBSITE_PATH)
    missing_website_rows = load_csv(MISSING_WEBSITE_PATH)

    all_codes = [r["airline_code"] for r in with_website_rows] + [
        r["airline_code"] for r in missing_website_rows
    ]

    names_zh = fetch_chinese_names(all_codes)

    write_csv_with_chinese(WITH_WEBSITE_PATH, with_website_rows, names_zh)
    write_csv_with_chinese(MISSING_WEBSITE_PATH, missing_website_rows, names_zh)

    found_count = sum(1 for code in all_codes if names_zh.get(code))
    with_website_found = sum(
        1 for r in with_website_rows if names_zh.get(r["airline_code"])
    )
    missing_website_found = sum(
        1 for r in missing_website_rows if names_zh.get(r["airline_code"])
    )

    print(f"總筆數: {len(all_codes)}")
    print(f"查到中文名稱: {found_count} 筆")
    print(f"查無中文名稱（填 none）: {len(all_codes) - found_count} 筆")
    print(f"中文名稱涵蓋率: {found_count / len(all_codes) * 100:.1f}%")
    print()
    print(f"data/airlines_with_website.csv    中文涵蓋率: {with_website_found}/{len(with_website_rows)} ({with_website_found / len(with_website_rows) * 100:.1f}%)")
    print(f"data/airlines_missing_website.csv 中文涵蓋率: {missing_website_found}/{len(missing_website_rows)} ({missing_website_found / len(missing_website_rows) * 100:.1f}%)")
    print(f"已更新 {WITH_WEBSITE_PATH} 和 {MISSING_WEBSITE_PATH}")


if __name__ == "__main__":
    main()