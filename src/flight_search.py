"""
src/flight_search.py

負責跟 fli 溝通，拿到航班原始資料並整理成統一格式。
不做任何篩選/分類邏輯——那些邏輯放在 src/filters.py。
"""

import time
from fli.models import (
    Airport,
    FlightSearchFilters,
    FlightSegment,
    PassengerInfo,
    SeatType,
    SortBy,
    TripType,
)
from fli.search import SearchFlights
from src.csv_reader import get_valid_airport_codes

VALID_AIRPORT_CODES = get_valid_airport_codes()


def _validate_airport_code(code: str) -> str:
    """檢查機場代碼是否存在於 fli 支援的清單裡，不合法就丟出清楚的錯誤訊息。"""
    code = code.upper()
    if code not in VALID_AIRPORT_CODES:
        raise ValueError(f"輸入機場錯誤: '{code}' 不是有效的機場代碼")
    return code


def _search_with_retry(
    filters: FlightSearchFilters,
    top_n: int = 5,
    max_retries: int = 3,
) -> list:
    """
    包裝 SearchFlights().search()，遇到 HTTP 429（速率限制）時
    用指數退避（exponential backoff）重試，最多重試 max_retries 次。

    top_n 預設降到 3（fli 原本預設 5）：來回票查詢時，fli 會平行
    發出 top_n 個請求去查每個去程候選各自配哪些回程，數字越大同時
    打向 Google 的請求越多，越容易觸發 429。降到 3 是犧牲一點來回
    候選組合的豐富度，換取觸發限流的機率降低。
    """
    searcher = SearchFlights()
    for attempt in range(max_retries):
        try:
            return searcher.search(filters, top_n=top_n) or []
        except Exception as e:
            is_rate_limited = "429" in str(e)
            is_last_attempt = attempt == max_retries - 1
            if is_rate_limited and not is_last_attempt:
                wait_seconds = 2**attempt  # 1秒 → 2秒 → 4秒
                time.sleep(wait_seconds)
                continue
            raise
    return []


def _get_airline_info(flight) -> tuple[str, str, bool]:
    """
    回傳 (airline_code, airline_name, is_mixed_airline)。

    flight.primary_airline 在跨航司轉機時會是 None（Google 沒有單一
    「主要航空公司」的概念），此時退回用第一段航班的航空公司代表，
    並標記 is_mixed_airline=True 提醒使用者這趟涉及多家航空公司。
    """
    if flight.primary_airline is not None:
        return flight.primary_airline.name, flight.primary_airline_name, False

    first_leg = flight.legs[0]
    return first_leg.airline.name, first_leg.airline.value, True


def _flight_to_dict(flight) -> dict:
    """單程航班：完整欄位，含 price。"""
    airline_code, airline_name, is_mixed_airline = _get_airline_info(flight)
    return {
        "airline_code": airline_code,
        "airline_name": airline_name,
        "is_mixed_airline": is_mixed_airline,
        "price": flight.price,
        "currency": flight.currency,
        "flight_duration_min": flight.duration,
        "stop_count": flight.stops,
        "depart_time": flight.legs[0].departure_datetime,
        "arrive_time": flight.legs[-1].arrival_datetime,
        "co2_grams": flight.co2_emissions_g,
        "is_self_transfer": flight.self_transfer,
    }


def _leg_to_dict(flight) -> dict:
    """
    來回票中的單一段（去程或回程）的細節。

    刻意不含 price —— 來回票的 price 語意是「整組來回總價」，
    只會放在 search_cheapest() 回傳的最外層，這裡的 leg 細節
    只描述時間、轉機、航空公司這些跟金額無關的資訊，避免之後
    有人誤把這裡的數字當成「單獨這一段的票價」來用。
    """
    airline_code, airline_name, is_mixed_airline = _get_airline_info(flight)
    return {
        "airline_code": airline_code,
        "airline_name": airline_name,
        "is_mixed_airline": is_mixed_airline,
        "flight_duration_min": flight.duration,
        "stop_count": flight.stops,
        "depart_time": flight.legs[0].departure_datetime,
        "arrive_time": flight.legs[-1].arrival_datetime,
        "co2_grams": flight.co2_emissions_g,
        "is_self_transfer": flight.self_transfer,
    }


def search_cheapest(
    adults: int,
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None = None,
) -> list[dict]:
    """
    查詢航班，回傳統一格式的 dict list（已依價格由低到高排序）。

    單程（return_date=None）：
        每筆 dict 是一個完整航班，欄位見 _flight_to_dict()。

    來回（有給 return_date）：
        每筆 dict 是一組「去程+回程」配對，結構為：
        {
            "price": 這個組合的來回總價（float）,
            "currency": 幣別（str）,
            "flight_duration_min": 去程+回程的總飛行時間（分鐘）,
            "stop_count": 去程+回程的總轉機次數,
            "outbound": {...去程細節，不含 price，見 _leg_to_dict()...},
            "return": {...回程細節，不含 price，見 _leg_to_dict()...},
        }

        來回總價的取法是官方邏輯：Google Flights 把整組來回的總價
        放在「去程」那筆資料的 price 欄位上，回程那筆的 price 語意
        不明確、容易誤導，因此完全不採用。

    Raises:
        ValueError: origin 或 destination 不是合法的機場代碼。
    """
    origin_code = _validate_airport_code(origin)
    destination_code = _validate_airport_code(destination)

    origin_airport = Airport[origin_code]
    destination_airport = Airport[destination_code]

    is_round_trip = return_date is not None

    if is_round_trip:
        flight_segments = [
            FlightSegment(
                departure_airport=[[origin_airport, 0]],
                arrival_airport=[[destination_airport, 0]],
                travel_date=depart_date,
            ),
            FlightSegment(
                departure_airport=[[destination_airport, 0]],
                arrival_airport=[[origin_airport, 0]],
                travel_date=return_date,
            ),
        ]
        trip_type = TripType.ROUND_TRIP
    else:
        flight_segments = [
            FlightSegment(
                departure_airport=[[origin_airport, 0]],
                arrival_airport=[[destination_airport, 0]],
                travel_date=depart_date,
            )
        ]
        trip_type = TripType.ONE_WAY

    filters = FlightSearchFilters(
        trip_type=trip_type,
        passenger_info=PassengerInfo(adults=adults),
        flight_segments=flight_segments,
        seat_type=SeatType.ECONOMY,
        sort_by=SortBy.CHEAPEST,
    )

    results = _search_with_retry(filters)

    output: list[dict] = []

    if is_round_trip:
        for outbound, return_flight in results:
            if outbound.price is None:
                # Google 沒有給出這個組合的價格（常見於商務艙+多人數搜尋
                # 等情境），跳過這筆，不要存一個誤導性的 price=None 進資料庫
                continue
            output.append(
                {
                    "price": outbound.price,
                    "currency": outbound.currency,
                    "flight_duration_min": outbound.duration + return_flight.duration,
                    "stop_count": outbound.stops + return_flight.stops,
                    "outbound": _leg_to_dict(outbound),
                    "return": _leg_to_dict(return_flight),
                }
            )
    else:
        for flight in results:
            if flight.price is None:
                continue
            output.append(_flight_to_dict(flight))

    output.sort(key=lambda x: x["price"])
    return output