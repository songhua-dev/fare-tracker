"""
src/db.py

負責跟 Neon (PostgreSQL) 溝通：存查詢紀錄、存航班結果、查歷史低價排名。
每次查詢開關一個 connection，不用 connection pool（流量小，先求簡單）。

設計上刻意「不」在這支檔案裡吞掉資料庫錯誤——DB 出問題就正常丟例外，
讓呼叫方（main.py）自己決定要怎麼處理（目前的決定是：main.py 那邊
用 try/except 包起來，DB 失敗就跳過寫入/跳過歷史排名，不影響核心的
比價查詢功能）。這樣分工比較清楚：db.py 只管「怎麼跟資料庫講話」，
「DB 掛了要不要緊」是 main.py 的責任。
"""

import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_NEON_URL = os.environ.get("NEON_URL")


@contextmanager
def get_connection():
    """
    開一個新連線，用完自動 commit 並關閉；發生例外時自動 rollback。

    用法：
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    if not _NEON_URL:
        raise RuntimeError(
            "環境變數 NEON_URL 未設定，請檢查本機 .env 或 Render 的環境變數設定"
        )

    conn = psycopg2.connect(_NEON_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 寫入
# ---------------------------------------------------------------------------

def insert_search(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None = None,
) -> int:
    """新增一筆查詢紀錄，回傳這筆紀錄的 id（給 insert_flight_results 用）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO searches (origin, destination, depart_date, return_date)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (origin, destination, depart_date, return_date),
            )
            return cur.fetchone()[0]


def _flatten_flight_for_db(flight: dict) -> dict:
    """
    把 flight_search.py 回傳的單程（扁平）或來回（巢狀）結構，
    統一轉成 flight_results 表要存的欄位。

    來回票的處理方式：
    - airline_code / airline_name：用去程（outbound）代表，跟
      filters.py 的 _get_airline_code() 邏輯一致。
    - departure_datetime：去程出發時間。
    - arrival_datetime：回程抵達時間（涵蓋整趟行程的時間跨度）。
    - co2_emissions_g：去程 + 回程相加。
    - self_transfer：去程或回程任一段是自行轉機就標記 True
      （對使用者來說，整趟行程只要有一段要自己轉機就算風險）。
    """
    if "outbound" in flight:
        outbound = flight["outbound"]
        return_leg = flight["return"]
        return {
            "airline_code": outbound["airline_code"],
            "airline_name": outbound["airline_name"],
            "price": flight["price"],
            "currency": flight["currency"],
            "duration_minutes": flight["flight_duration_min"],
            "stops": flight["stop_count"],
            "departure_datetime": outbound["depart_time"],
            "arrival_datetime": return_leg["arrive_time"],
            "co2_emissions_g": outbound["co2_grams"] + return_leg["co2_grams"],
            "self_transfer": outbound["is_self_transfer"] or return_leg["is_self_transfer"],
        }

    return {
        "airline_code": flight["airline_code"],
        "airline_name": flight["airline_name"],
        "price": flight["price"],
        "currency": flight["currency"],
        "duration_minutes": flight["flight_duration_min"],
        "stops": flight["stop_count"],
        "departure_datetime": flight["depart_time"],
        "arrival_datetime": flight["arrive_time"],
        "co2_emissions_g": flight["co2_grams"],
        "self_transfer": flight["is_self_transfer"],
    }


def insert_flight_results(search_id: int, flights: list[dict]) -> None:
    """把這次查詢的所有航班結果存進 flight_results，關聯到同一個 search_id。"""
    if not flights:
        return

    rows = [{**_flatten_flight_for_db(f), "search_id": search_id} for f in flights]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO flight_results (
                    search_id, airline_code, airline_name, price, currency,
                    duration_minutes, stops, departure_datetime, arrival_datetime,
                    co2_emissions_g, self_transfer
                ) VALUES (
                    %(search_id)s, %(airline_code)s, %(airline_name)s, %(price)s, %(currency)s,
                    %(duration_minutes)s, %(stops)s, %(departure_datetime)s, %(arrival_datetime)s,
                    %(co2_emissions_g)s, %(self_transfer)s
                )
                """,
                rows,
            )


# ---------------------------------------------------------------------------
# 查詢：歷史低價排名
# ---------------------------------------------------------------------------

def get_price_rank(
    origin: str, destination: str, price: float, is_round_trip: bool
) -> dict | None:
    """
    查這個價格在該航線的歷史紀錄裡排第幾低（用來在「全部結果」列表裡，
    最便宜那一筆旁邊標示「N筆中第X低」）。

    單程和來回分開統計——來回票是兩段航程的總價，跟單程票的價格量級
    不同，混在一起比較沒有意義，所以用 is_round_trip 篩選
    searches.return_date 是否為 NULL 來區分成兩個獨立的統計池。

    同價格用 DENSE_RANK()：如果有兩筆歷史紀錄價格完全一樣，兩筆都算
    同一個名次（例如都是「第4低」），不會因為資料庫剛好把哪筆排前面
    而給出誤導的名次差異。

    符合以下條件才回傳結果，否則回傳 None（代表「不要顯示標示」）：
    - 該航線、該行程類型（單程/來回）的歷史紀錄至少 50 筆
    - 這個價格的名次在前 5 名以內
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH route_history AS (
                    SELECT fr.price
                    FROM flight_results fr
                    JOIN searches s ON fr.search_id = s.id
                    WHERE s.origin = %(origin)s
                      AND s.destination = %(destination)s
                      AND (s.return_date IS NOT NULL) = %(is_round_trip)s
                ),
                ranked AS (
                    SELECT price, DENSE_RANK() OVER (ORDER BY price ASC) AS rnk
                    FROM route_history
                )
                SELECT
                    (SELECT COUNT(*) FROM route_history) AS total_records,
                    (SELECT MIN(rnk) FROM ranked WHERE price = %(price)s) AS rank_from_bottom
                """,
                {
                    "origin": origin,
                    "destination": destination,
                    "is_round_trip": is_round_trip,
                    "price": price,
                },
            )
            total_records, rank_from_bottom = cur.fetchone()

    if total_records is None or total_records < 50:
        return None
    if rank_from_bottom is None or rank_from_bottom > 5:
        return None

    return {
        "total_records": total_records,
        "rank_from_bottom": rank_from_bottom,
    }