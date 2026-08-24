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
    MaxStops,
)
from fli.search import SearchFlights
from src.csv_reader import get_valid_airport_codes
from src.i18n import _

VALID_AIRPORT_CODES = get_valid_airport_codes()


def _validate_airport_code(code: str) -> str:
    """檢查機場代碼是否存在於 fli 支援的清單裡，不合法就丟出清楚的錯誤訊息。"""
    code = code.upper()
    if code not in VALID_AIRPORT_CODES:
        raise ValueError(_("invalid_airport_code", code=code))
    return code


def _get_max_stops_value(direct_only: bool):
    """
    動態取得 MaxStops 中代表「直飛」與「不限」的設定值，避免版號差異導致 AttributeError。
    """
    if not direct_only:
        return getattr(MaxStops, "ANY", None)

    # 依序嘗試常見的直飛 Enum 屬性，若皆無則直接帶入 0
    for attr in ["NON_STOP", "NONSTOP", "DIRECT", "ZERO"]:
        if hasattr(MaxStops, attr):
            return getattr(MaxStops, attr)
    
    try:
        return MaxStops(0)
    except Exception:
        return 0


def _search_with_retry(
    filters: FlightSearchFilters,
    top_n: int = 5,
    max_retries: int = 3,
) -> list:
    """
    包裝 SearchFlights().search()，遇到 HTTP 429（速率限制）時
    用指數退避（exponential backoff）重試，最多重試 max_retries 次。
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
    if flight.primary_airline is not None:
        return flight.primary_airline.name, flight.primary_airline_name, False

    first_leg = flight.legs[0]
    return first_leg.airline.name, first_leg.airline.value, True


def _flight_to_dict(flight) -> dict:
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
    direct_only: bool = False,
) -> list[dict]:
    """
    查詢航班，回傳統一格式的 dict list（已依價格由低到高排序）。
    """
    origin_code = _validate_airport_code(origin)
    destination_code = _validate_airport_code(destination)

    origin_airport = Airport[origin_code]
    destination_airport = Airport[destination_code]

    is_round_trip = return_date is not None

    stops_filter = _get_max_stops_value(direct_only)

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
        stops=stops_filter,
        sort_by=SortBy.CHEAPEST,
    )

    results = _search_with_retry(filters)

    output: list[dict] = []

    if is_round_trip:
        for outbound, return_flight in results:
            if outbound.price is None:
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