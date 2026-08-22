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


def search_airports_by_keyword(keyword: str, limit: int = 10) -> list[dict]:
    """
    給前端機場 autocomplete 用：關鍵字同時比對機場代碼、英文名、中文名，
    任一欄位包含關鍵字（不分大小寫）就算命中。

    刻意不區分「現在 UI 是中文還是英文模式」——不管使用者打中文、英文、
    還是代碼，都應該查得到，這支函式跟畫面語言無關，畫面要顯示 name_zh
    還是 name_en 是前端渲染時的事。

    回傳的 dict 固定給三個欄位（code / name_en / name_zh），就算某個機場
    的 name_zh 是 "none"（資料不齊全），一樣照原樣回傳，交給前端自己
    決定要不要 fallback 顯示——這裡不做 get_airport_name_zh() 那種
    fallback 邏輯，因為那是「決定畫面上顯示什麼」的責任，不是搜尋比對
    的責任，兩者混在一起會讓這支函式意圖不清楚。
    """
    keyword_lower = keyword.strip().lower()
    if not keyword_lower:
        return []

    matches = []
    for code, row in _AIRPORTS.items():
        name_en = row["airport_name"]
        name_zh = row["airport_name_zh"]
        haystack = f"{code} {name_en} {name_zh}".lower()
        if keyword_lower in haystack:
            matches.append({"code": code, "name_en": name_en, "name_zh": name_zh})

    # 代碼開頭完全對上關鍵字的排最前面（例如打 "NRT" 就是想直接找那個
    # 機場，不該被一堆名稱裡剛好包含 "nrt" 子字串的結果洗掉），
    # 其餘依中文名稱排序，讓清單看起來有固定順序、不是每次都亂跳。
    matches.sort(key=lambda a: (not a["code"].lower().startswith(keyword_lower), a["name_zh"]))

    return matches[:limit]