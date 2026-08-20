"""
scripts/build_airport_zh.py

讀取 data/airports.csv（fli 內建機場清單），查 Wikidata 的中文維基百科
條目標題當中文名稱，分 16 批處理，每批獨立存檔（支援斷點續傳），
全部跑完後合併成 data/airport_zh.csv，並清掉過程中的暫存檔。

用法：python scripts/build_airport_zh.py
（可重複執行：已完成的批次會自動跳過，只跑還沒完成的部分）
"""

import csv
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
AIRPORTS_CSV_PATH = DATA_DIR / "airports.csv"
OUTPUT_PATH = DATA_DIR / "airport_zh.csv"
PROGRESS_DIR = DATA_DIR / "airport_zh_progress"

NUM_BATCHES = 16
REQUEST_TIMEOUT_SECONDS = 60  # 單次請求逾時
BATCH_INTERVAL_SECONDS = 2  # 批次之間的間隔，對 Wikidata 服務禮貌一點


def load_airports() -> list[tuple[str, str]]:
    with open(AIRPORTS_CSV_PATH, encoding="utf-8") as f:
        return [(row["code"], row["name"]) for row in csv.DictReader(f)]


def split_into_batches(items: list, num_batches: int) -> list[list]:
    """把 items 平均切成 num_batches 份。"""
    batch_size = (len(items) + num_batches - 1) // num_batches  # 無條件進位
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def fetch_batch_chinese_names(codes: list[str]) -> dict[str, str]:
    """
    查一批機場代碼的中文維基百科條目標題。
    機場的 IATA 代碼在 Wikidata 是屬性 P238（航空公司用的是 P229）。
    """
    values_clause = " ".join(f'"{code}"' for code in codes)

    query = f"""
    SELECT ?iata ?name_zh WHERE {{
      VALUES ?iata {{ {values_clause} }}
      ?airport wdt:P238 ?iata .

      OPTIONAL {{
        ?zhwiki_sitelink schema:about ?airport ;
                          schema:isPartOf <https://zh.wikipedia.org/> ;
                          schema:name ?name_zh .
      }}
    }}
    """

    response = requests.post(
        "https://query.wikidata.org/sparql",
        data={"query": query, "format": "json"},
        headers={
            "User-Agent": "flight-ticket-analyzer/1.0",
            "Accept": "application/sparql-results+json",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = response.json()["results"]["bindings"]

    names_zh: dict[str, str] = {}
    for row in rows:
        code = row["iata"]["value"]
        name_zh = row.get("name_zh", {}).get("value", "")
        names_zh[code] = name_zh
    return names_zh


def batch_progress_path(batch_index: int) -> Path:
    return PROGRESS_DIR / f"batch_{batch_index:02d}.csv"


def batch_is_done(batch_index: int) -> bool:
    return batch_progress_path(batch_index).exists()


def save_batch_result(batch_index: int, batch_items: list[tuple[str, str]], names_zh: dict[str, str]) -> None:
    path = batch_progress_path(batch_index)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["airport_code", "airport_name", "airport_name_zh"])
        for code, name in batch_items:
            writer.writerow([code, name, names_zh.get(code) or "none"])


def run_batches(batches: list[list[tuple[str, str]]]) -> None:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    for i, batch_items in enumerate(batches, start=1):
        if batch_is_done(i):
            print(f"批次 {i}/{len(batches)} 已完成，跳過")
            continue

        codes = [code for code, _ in batch_items]
        print(f"批次 {i}/{len(batches)} 查詢中（{len(codes)} 筆）...")

        try:
            names_zh = fetch_batch_chinese_names(codes)
        except requests.exceptions.RequestException as e:
            print(f"批次 {i} 失敗：{e}")
            print("已完成的批次已存檔，重新執行本程式即可從這裡繼續。")
            raise

        save_batch_result(i, batch_items, names_zh)
        print(f"批次 {i}/{len(batches)} 完成，已存檔")

        time.sleep(BATCH_INTERVAL_SECONDS)


def merge_batches(num_batches: int) -> None:
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(["airport_code", "airport_name", "airport_name_zh"])

        for i in range(1, num_batches + 1):
            with open(batch_progress_path(i), encoding="utf-8") as in_f:
                reader = csv.reader(in_f)
                next(reader)  # 跳過該批次自己的表頭
                writer.writerows(reader)

    print(f"已合併成 {OUTPUT_PATH}")


def cleanup_progress_files(num_batches: int) -> None:
    for i in range(1, num_batches + 1):
        batch_progress_path(i).unlink()
    PROGRESS_DIR.rmdir()
    print("已清除暫存批次檔")


def main() -> None:
    airports = load_airports()
    batches = split_into_batches(airports, NUM_BATCHES)

    run_batches(batches)  # 若中途失敗會 raise，不會往下執行合併/清理

    merge_batches(len(batches))
    cleanup_progress_files(len(batches))

    total = len(airports)
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        found = sum(1 for row in csv.DictReader(f) if row["airport_name_zh"] != "none")

    print(f"總筆數: {total}")
    print(f"查到中文名稱: {found} 筆")
    print(f"涵蓋率: {found / total * 100:.1f}%")


if __name__ == "__main__":
    main()