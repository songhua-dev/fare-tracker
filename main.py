"""
main.py

Flask 進入點：接表單 -> 呼叫 flight_search 查航班 -> filters 處理
-> csv_reader 補訂票連結/中文名稱 -> 寫入 Neon（歷史紀錄）
-> 查歷史低價排名 -> 顯示結果。

資料庫（Neon）是加值功能，不是核心流程的必要條件：寫入、查排名
任何一步失敗（例如額度用完、連線問題），都只印警告訊息、不中斷
使用者的查詢流程，頁面照樣正常顯示比價結果。
"""

import time

from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from src import db
from src.csv_reader import get_airline_name_zh, get_airline_website
from src.filters import add_stop_label, find_cheapest_per_airline
from src.flight_search import search_cheapest

app = Flask(__name__)

# Render（以及大多數雲端平台）是把 app 放在反向代理後面，Flask 直接拿到的
# request.remote_addr 會是代理伺服器的 IP，不是使用者真實 IP。ProxyFix 會
# 讀取 X-Forwarded-For 這個標頭，把 request.remote_addr 修正成真實使用者 IP。
# x_for=1 代表「信任一層代理」——本機開發沒有代理時，沒有這個標頭，
# ProxyFix 會直接維持原本的 remote_addr，不會出錯。
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

DISCLAIMER = "本頁價格僅供參考，實際訂票請以航空公司或訂票平台當下顯示金額為準。"

# --- 每人 7 秒搜尋冷卻 ---
# 存在記憶體字典裡，不是資料庫：Render 免費層閒置重啟會清空這份記錄，
# 影響只是冷卻機制重置（使用者少等一次 7 秒），不是嚴重問題，先不用
# 為了這個去綁定 db.py。
SEARCH_COOLDOWN_SECONDS = 7
_last_search_time: dict[str, float] = {}


def _check_and_update_cooldown(client_ip: str) -> float:
    """
    檢查這個 IP 是否還在冷卻中。

    回傳還要等待的秒數；0 代表可以搜尋（並且會順便更新這個 IP 的
    最後搜尋時間戳記，视为「這次搜尋已發生」）。
    """
    now = time.time()
    last_time = _last_search_time.get(client_ip, 0)
    elapsed = now - last_time

    if elapsed < SEARCH_COOLDOWN_SECONDS:
        return round(SEARCH_COOLDOWN_SECONDS - elapsed, 1)

    _last_search_time[client_ip] = now
    return 0


def _enrich_leg(leg: dict) -> dict:
    """幫一段航班（單程航班本身，或來回票裡的 outbound / return）
    補上中文名稱與訂票連結。booking_url 查不到就是 None，交給樣板
    去顯示「請自行搜尋官網」這種通用文字。"""
    enriched = dict(leg)
    enriched["airline_name_zh"] = get_airline_name_zh(leg["airline_code"], leg["airline_name"])
    enriched["booking_url"] = get_airline_website(leg["airline_code"])
    return enriched


def _enrich_flight(flight: dict) -> dict:
    """單程是扁平結構，直接補；來回是巢狀結構，outbound/return 各自補一次。"""
    if "outbound" in flight:
        enriched = dict(flight)
        enriched["outbound"] = _enrich_leg(flight["outbound"])
        enriched["return"] = _enrich_leg(flight["return"])
        return enriched
    return _enrich_leg(flight)


def _save_search_to_db(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None,
    flights: list[dict],
) -> None:
    """
    把這次查詢的結果寫進 Neon（searches + flight_results）。

    只有呼叫方確認 flights 非空（查詢真的有結果）才應該呼叫這支函式——
    查無機場代碼、查無航班這些情況不該寫進歷史資料，避免累積一堆
    沒有意義的紀錄，之後歷史低價排名的統計會失準。

    任何 DB 相關錯誤都吞掉、印警告訊息，不往外丟例外：寫歷史紀錄
    失敗不該讓使用者連這次的比價結果都看不到。
    """
    try:
        search_id = db.insert_search(origin, destination, depart_date, return_date)
        db.insert_flight_results(search_id, flights)
    except Exception as e:
        app.logger.warning(f"寫入 Neon 失敗，跳過這次的歷史資料紀錄：{e}")


def _get_price_rank_safe(
    origin: str, destination: str, price: float, is_round_trip: bool
) -> dict | None:
    """
    db.get_price_rank() 的安全包裝版：DB 查詢失敗時回傳 None，
    效果等同「這個價格不符合顯示標示的條件」，頁面就不會顯示歷史
    低價標示，但其他比價結果照樣正常顯示。
    """
    try:
        return db.get_price_rank(origin, destination, price, is_round_trip)
    except Exception as e:
        app.logger.warning(f"查詢歷史低價排名失敗：{e}")
        return None


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", flights=None, error=None, disclaimer=DISCLAIMER)


@app.route("/search", methods=["POST"])
def search():
    client_ip = request.remote_addr
    wait_seconds = _check_and_update_cooldown(client_ip)
    if wait_seconds > 0:
        return render_template(
            "index.html",
            flights=None,
            error=f"查詢太頻繁，請等 {wait_seconds} 秒後再試一次",
            disclaimer=DISCLAIMER,
        )

    origin = request.form.get("origin", "").strip()
    destination = request.form.get("destination", "").strip()
    depart_date = request.form.get("depart_date", "").strip()
    return_date = request.form.get("return_date", "").strip() or None
    adults_raw = request.form.get("adults", "1").strip()

    try:
        adults = int(adults_raw)
    except ValueError:
        return render_template(
            "index.html", flights=None, error="人數必須是數字", disclaimer=DISCLAIMER
        )

    try:
        flights = search_cheapest(
            adults=adults,
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
        )
    except ValueError as e:
        # 機場代碼不合法，search_cheapest 丟出的錯誤訊息已經寫得夠清楚，直接顯示
        # （這種情況不會走到下面的 DB 寫入，因為這裡就 return 掉了）
        return render_template("index.html", flights=None, error=str(e), disclaimer=DISCLAIMER)

    is_round_trip = return_date is not None

    # 歷史低價排名：只在真的有查到結果時才查，用 flights[0] 的價格——
    # search_cheapest() 回傳前已經照價格由低到高排序，flights[0] 就是
    # 最便宜的那一筆，也就是之後會顯示標示的那一筆。
    price_rank = None

    if flights:
        # 查詢成功才寫入 DB；查無航班（flights 是空 list）不寫，
        # 避免累積沒有意義的紀錄。
        _save_search_to_db(origin, destination, depart_date, return_date, flights)

        cheapest_price = flights[0]["price"]
        price_rank = _get_price_rank_safe(origin, destination, cheapest_price, is_round_trip)

    flights = add_stop_label(flights)
    flights = [_enrich_flight(f) for f in flights]

    cheapest_per_airline = find_cheapest_per_airline(flights)

    return render_template(
        "index.html",
        flights=flights,
        cheapest_per_airline=cheapest_per_airline,
        error=None,
        disclaimer=DISCLAIMER,
        is_round_trip=is_round_trip,
        price_rank=price_rank,
    )


if __name__ == "__main__":
    app.run(debug=True)