"""
main.py
"""

import time

from flask import Flask, render_template, request, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from src import db
from src.csv_reader import get_airline_display_name, get_airline_website, search_airports_by_keyword
from src.filters import (
    add_stop_label,
    filter_by_depart_time_after,
    filter_by_return_time_after,
    find_cheapest_per_airline,
)
from src.flight_search import search_cheapest
from src.i18n import get_text

app = Flask(__name__)

# 從 request 取得當前語系，並注入 Jinja2 樣板
@app.context_processor
def inject_i18n():
    current_lang = request.args.get("lang") or request.form.get("lang") or "zh_TW"
    def _(key, **kwargs):
        return get_text(key, lang=current_lang, **kwargs)
    return dict(_=_, current_lang=current_lang)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

SEARCH_COOLDOWN_SECONDS = 7
_last_search_time: dict[str, float] = {}


def _check_and_update_cooldown(client_ip: str) -> float:
    now = time.time()
    last_time = _last_search_time.get(client_ip, 0)
    elapsed = now - last_time

    if elapsed < SEARCH_COOLDOWN_SECONDS:
        return round(SEARCH_COOLDOWN_SECONDS - elapsed, 1)

    _last_search_time[client_ip] = now
    return 0


def _parse_hour_filter(raw: str) -> int | None:
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _enrich_leg(leg: dict, lang: str) -> dict:
    enriched = dict(leg)
    enriched["airline_name_zh"] = get_airline_display_name(
        leg["airline_code"], 
        leg.get("airline_name", ""), 
        lang=lang
    )
    enriched["booking_url"] = get_airline_website(leg["airline_code"])
    return enriched


def _enrich_flight(flight: dict, lang: str) -> dict:
    if "outbound" in flight:
        enriched = dict(flight)
        enriched["outbound"] = _enrich_leg(flight["outbound"], lang)
        enriched["return"] = _enrich_leg(flight["return"], lang)
        return enriched
    return _enrich_leg(flight, lang)


def _save_search_to_db(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None,
    flights: list[dict],
) -> None:
    try:
        search_id = db.insert_search(origin, destination, depart_date, return_date)
        db.insert_flight_results(search_id, flights)
    except Exception as e:
        app.logger.warning(f"寫入 Neon 失敗，跳過這次的歷史資料紀錄：{e}")


def _get_price_rank_safe(
    origin: str, destination: str, price: float, is_round_trip: bool
) -> dict | None:
    try:
        return db.get_price_rank(origin, destination, price, is_round_trip)
    except Exception as e:
        app.logger.warning(f"查詢歷史低價排名失敗：{e}")
        return None


@app.route("/ping", methods=["GET"])
def ping():
    return "ok", 200


@app.route("/api/airports", methods=["GET"])
def api_airports():
    query = request.args.get("q", "").strip()
    lang = request.args.get("lang", "zh_TW")
    if not query:
        return {"airports": []}
    airports = search_airports_by_keyword(query, lang=lang)
    return {"airports": airports}


@app.route("/", methods=["GET"])
def index():
    lang = request.args.get("lang", "zh_TW")
    return render_template("index.html", flights=None, error=None, disclaimer=get_text("disclaimer", lang=lang))


@app.route("/search", methods=["POST"])
def search():
    client_ip = request.remote_addr
    # 優先讀取 URL query param，若無則讀取 POST form 中的欄位
    lang = request.args.get("lang") or request.form.get("lang") or "zh_TW"

    wait_seconds = _check_and_update_cooldown(client_ip)
    if wait_seconds > 0:
        return render_template(
            "index.html",
            flights=None,
            error=get_text("err_cooldown", lang=lang, seconds=wait_seconds),
            disclaimer=get_text("disclaimer", lang=lang),
        )

    origin = request.form.get("origin", "").strip()
    destination = request.form.get("destination", "").strip()
    depart_date = request.form.get("depart_date", "").strip()
    return_date = request.form.get("return_date", "").strip() or None
    adults_raw = request.form.get("adults", "1").strip()
    depart_time_after = _parse_hour_filter(request.form.get("depart_time_after", "").strip())
    return_time_after = _parse_hour_filter(request.form.get("return_time_after", "").strip())

    if return_date is not None and return_date < depart_date:
        return render_template(
            "index.html",
            flights=None,
            error=get_text("err_invalid_return_date", lang=lang),
            disclaimer=get_text("disclaimer", lang=lang),
        )

    try:
        adults = int(adults_raw)
    except ValueError:
        return render_template(
            "index.html", flights=None, error=get_text("err_invalid_adults", lang=lang), disclaimer=get_text("disclaimer", lang=lang)
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
        return render_template("index.html", flights=None, error=str(e), disclaimer=get_text("disclaimer", lang=lang))

    is_round_trip = return_date is not None
    price_rank = None

    if flights:
        _save_search_to_db(origin, destination, depart_date, return_date, flights)

        if depart_time_after is not None:
            flights = filter_by_depart_time_after(flights, depart_time_after)
        if is_round_trip and return_time_after is not None:
            flights = filter_by_return_time_after(flights, return_time_after)

        if flights:
            cheapest_price = flights[0]["price"]
            price_rank = _get_price_rank_safe(origin, destination, cheapest_price, is_round_trip)

    # 傳入 lang 參數以精準渲染直達/轉機標籤
    flights = add_stop_label(flights, lang=lang)
    flights = [_enrich_flight(f, lang=lang) for f in flights]

    cheapest_per_airline = find_cheapest_per_airline(flights)

    return render_template(
        "index.html",
        flights=flights,
        cheapest_per_airline=cheapest_per_airline,
        error=None,
        disclaimer=get_text("disclaimer", lang=lang),
        is_round_trip=is_round_trip,
        price_rank=price_rank,
    )


if __name__ == "__main__":
    app.run(debug=True)