"""
src/csv_reader.py

統一處理 data/ 底下的靜態 CSV 資料讀取（airlines.csv、airports.csv），
提供給 main.py 查詢用。CSV 只在模組載入時讀一次，之後都是查記憶體裡的 dict。
"""

import csv
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_AIRLINES_CSV_PATH = _DATA_DIR / "airlines.csv"
_AIRPORTS_CSV_PATH = _DATA_DIR / "airports.csv"


def _load_csv_as_dict(path: Path, key_field: str) -> dict[str, dict]:
    """讀 CSV，回傳 {key_field 的值: 該列的 dict}。"""
    with open(path, encoding="utf-8") as f:
        return {row[key_field]: row for row in csv.DictReader(f)}


_AIRLINES = _load_csv_as_dict(_AIRLINES_CSV_PATH, key_field="airline_code")
_AIRPORTS = _load_csv_as_dict(_AIRPORTS_CSV_PATH, key_field="airport_code")


# ---------------------------------------------------------------------------
# 航空公司
# ---------------------------------------------------------------------------

def get_airline_website(airline_code: str) -> str | None:
    """查訂票網址，查不到這家航空公司、或欄位值是 'none'，都回傳 None。"""
    row = _AIRLINES.get(airline_code)
    if not row or row["website"] == "none":
        return None
    return row["website"]


def get_airline_name_zh(airline_code: str, fallback_name: str) -> str:
    """查中文名稱，查不到就退回 fallback_name（通常是英文名）。"""
    row = _AIRLINES.get(airline_code)
    if not row or row["airline_name_zh"] == "none":
        return fallback_name
    return row["airline_name_zh"]


# ---------------------------------------------------------------------------
# 機場
# ---------------------------------------------------------------------------

def get_valid_airport_codes() -> set[str]:
    """回傳所有合法機場代碼的集合，給輸入驗證用。"""
    return set(_AIRPORTS.keys())


def get_airport_name_zh(airport_code: str, fallback_name: str) -> str:
    """查機場中文名稱，查不到就退回 fallback_name（通常是英文名）。"""
    row = _AIRPORTS.get(airport_code)
    if not row or row["airport_name_zh"] == "none":
        return fallback_name
    return row["airport_name_zh"]