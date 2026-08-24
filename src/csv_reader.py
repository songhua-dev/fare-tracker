"""
src/csv_reader.py

統一處理 data/ 底下的靜態 CSV 資料讀取（airlines.csv、airports.csv），
提供給 main.py 查詢用。CSV 只在模組載入時讀一次，之後都是查記憶體裡的 dict。

i18n 相容說明：
- 「搜尋比對」（search_airports_by_keyword）永遠同時比對代碼、英文名、
  中文名，跟目前 UI 顯示語言（lang 參數）無關——這是刻意的設計，讓
  「搜尋邏輯」跟「顯示語言」分離。lang 只決定回傳結果裡的顯示名稱
  要放中文還是英文，不影響「查不查得到」這件事。
"""

import csv
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_AIRLINES_CSV_PATH = _DATA_DIR / "airlines.csv"
_AIRPORTS_CSV_PATH = _DATA_DIR / "airports.csv"


def _load_csv_as_dict(file_path: str, key_field: str) -> dict:
    result = {}
    # 改用 encoding="utf-8-sig" 自動去除 \ufeff (BOM)
    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 去除 key 與 value 前後可能多餘的空白
            clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
            if key_field in clean_row:
                result[clean_row[key_field]] = clean_row
    return result


_AIRLINES = _load_csv_as_dict(_AIRLINES_CSV_PATH, key_field="airline_code")
_AIRPORTS = _load_csv_as_dict(_AIRPORTS_CSV_PATH, key_field="airport_code")


# ---------------------------------------------------------------------------
# 航空公司
# ---------------------------------------------------------------------------

def get_airline_website(airline_code: str) -> str | None:
    """查訂票網址，查不到這家航空公司、或欄位值是 'none'，都回傳 None。"""
    row = _AIRLINES.get(airline_code.upper())
    if not row or row.get("website") == "none":
        return None
    return row.get("website")


def get_airline_display_name(airline_code: str, default_name: str = "", lang: str = "zh_TW") -> str:
    """
    依語言回傳航空公司顯示名稱，main.py 的 _enrich_leg() 直接呼叫這支。

    - zh_TW：優先回傳 airlines.csv 裡的中文名稱，查不到（或欄位值是
      "none"）就退回 default_name（呼叫方傳進來的英文名，通常來自
      fli 即時查詢結果本身自帶的英文名）。
    - en_US：airlines.csv 目前沒有另外存一份英文航空公司名稱——英文
      名稱本來就是 fli 查詢結果自帶的（也就是 default_name），不需要
      查表，直接回傳 default_name 即可。
    """
    is_en = str(lang).lower().startswith("en")
    if is_en:
        return default_name or airline_code

    row = _AIRLINES.get(airline_code.upper())
    if not row or row.get("airline_name_zh") == "none" or not row.get("airline_name_zh"):
        return default_name
    return row.get("airline_name_zh")


def get_airline_name_zh(airline_code: str, default_name: str = "") -> str:
    """相容 i18n 導入前的舊呼叫方式，固定回傳中文名稱。"""
    return get_airline_display_name(airline_code, default_name, lang="zh_TW")


# ---------------------------------------------------------------------------
# 機場
# ---------------------------------------------------------------------------

def get_valid_airport_codes() -> set[str]:
    """回傳所有合法機場代碼的集合，給 flight_search.py 做輸入驗證用。"""
    return set(_AIRPORTS.keys())


def get_airport_name_zh(airport_code: str, fallback_name: str) -> str:
    """查機場中文名稱，查不到就退回 fallback_name（通常是英文名）。"""
    row = _AIRPORTS.get(airport_code)
    if not row or row.get("airport_name_zh") == "none" or not row.get("airport_name_zh"):
        return fallback_name
    return row.get("airport_name_zh")


def search_airports_by_keyword(keyword: str, lang: str = "zh_TW", limit: int = 10) -> list[dict]:
    """
    給前端機場 autocomplete 用（/api/airports 路由呼叫這支）。

    比對邏輯跟語言無關，lang 決定回傳的 "name" 欄位要放哪個語言的名稱給前端直接顯示；
    "name_zh"/"name_en" 兩個原始欄位固定都回傳。
    """
    keyword_lower = keyword.strip().lower()
    if not keyword_lower:
        return []

    is_en = str(lang).lower().startswith("en")
    matches = []

    for code, row in _AIRPORTS.items():
        name_en = row.get("airport_name", "")
        name_zh = row.get("airport_name_zh", "")

        # 建立比對字串 (包含代碼、英文名、中文名)
        haystack = f"{code} {name_en} {name_zh}".lower()
        if keyword_lower in haystack:
            # 依據語系決定 display_name，並做好降級備援 (fallback)
            if is_en:
                display_name = name_en if (name_en and name_en != "none") else name_zh
            else:
                display_name = name_zh if (name_zh and name_zh != "none") else name_en

            matches.append({
                "code": code,
                "name": display_name,
                "name_en": name_en,
                "name_zh": name_zh,
            })

    # 代碼開頭完全對上關鍵字的排最前面，其餘依顯示名稱排序
    matches.sort(key=lambda a: (not a["code"].lower().startswith(keyword_lower), a["name"]))

    return matches[:limit]