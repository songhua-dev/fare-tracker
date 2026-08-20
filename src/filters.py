"""
src/filters.py

負責「篩選 / 分類 / 分組」邏輯，輸入輸出都是
flight_search.py 回傳的 dict list，不呼叫任何外部 API。

單程航班的 dict 是扁平結構（airline_code 在最外層）；
來回航班的 dict 是巢狀結構（airline_code 在 outbound / return 底下）。
這支檔案裡的函式都要能同時處理這兩種結構，用 _get_airline_code() 統一取值。
"""


def _is_round_trip(entry: dict) -> bool:
    """判斷這筆資料是來回票（巢狀結構）還是單程（扁平結構）。"""
    return "outbound" in entry


def _get_airline_code(entry: dict) -> str:
    """
    取得代表這筆航班的航空公司代碼。

    來回票取「去程」的航空公司代表整組——因為使用者訂票時，
    通常是先看去程是哪家航空公司，回程即使換了別家，
    去程航空公司還是使用者對這組行程的第一印象。
    """
    if _is_round_trip(entry):
        return entry["outbound"]["airline_code"]
    return entry["airline_code"]


def classify_stops(stop_count: int) -> str:
    """把轉機次數的數字，轉成人看得懂的中文分類。"""
    if stop_count == 0:
        return "直達"
    elif stop_count == 1:
        return "轉機一次"
    else:
        return f"轉機{stop_count}次"


def filter_direct_only(flights: list[dict]) -> list[dict]:
    """
    只留下直達航班（stop_count == 0）。

    來回票的 stop_count 是「去程+回程轉機次數的總和」，
    所以這裡篩出來的來回票，代表去程、回程都是直達。
    """
    return [f for f in flights if f["stop_count"] == 0]


def filter_by_max_price(flights: list[dict], max_price: float) -> list[dict]:
    """只留下價格 <= max_price 的航班。"""
    return [f for f in flights if f["price"] <= max_price]


def filter_by_depart_time_after(flights: list[dict], hour: int) -> list[dict]:
    """
    只留下「出發時間的小時 >= hour」的航班，對應使用者選的『去程時間』篩選。

    單程直接看最外層的 depart_time；來回票看 outbound（去程段）的
    depart_time —— 使用者選的「去程時間」本來就是針對去程那一段的
    起飛時間，跟回程無關。
    """
    result = []
    for flight in flights:
        leg = flight["outbound"] if _is_round_trip(flight) else flight
        if leg["depart_time"].hour >= hour:
            result.append(flight)
    return result


def filter_by_return_time_after(flights: list[dict], hour: int) -> list[dict]:
    """
    只留下「回程出發時間的小時 >= hour」的航班，對應使用者選的『回程時間』篩選。

    只適用於來回票——呼叫方應該只在確定是來回票（return_date 有值）
    時才呼叫這支函式，單程資料沒有 "return" 這個欄位，呼叫下去會出錯。
    """
    return [f for f in flights if f["return"]["depart_time"].hour >= hour]


def find_cheapest(flights: list[dict]) -> dict | None:
    """
    從一堆航班結果裡，找出價格最低的那一筆。

    flight_search.py 回傳前已經照 price 排序，理論上 flights[0]
    就是答案；這裡用 min() 重新算一次，是為了讓這支函式不依賴
    「呼叫者有沒有先排序」這個假設，獨立使用也不會出錯。
    """
    if not flights:
        return None
    return min(flights, key=lambda f: f["price"])


def find_cheapest_per_airline(flights: list[dict]) -> list[dict]:
    """
    依航空公司分組，每家航空公司只留「該公司最便宜」的一筆。

    對應需求「哪一家航空公司的機票最便宜」——回傳結果依價格由低到高
    排序，所以看第一筆就是全部航空公司裡最便宜的那家。
    """
    cheapest_by_code: dict[str, dict] = {}

    for flight in flights:
        code = _get_airline_code(flight)
        if code not in cheapest_by_code or flight["price"] < cheapest_by_code[code]["price"]:
            cheapest_by_code[code] = flight

    result = list(cheapest_by_code.values())
    result.sort(key=lambda f: f["price"])
    return result


def add_stop_label(flights: list[dict]) -> list[dict]:
    """
    在每筆航班的 dict 裡，加上一個 stop_label 欄位（"直達"／"轉機一次"...）。

    不修改原本的 flights list，回傳一份新的 list，
    避免呼叫者不小心依賴到「這個函式會動到原本資料」這種副作用。
    """
    output = []
    for flight in flights:
        new_flight = dict(flight)
        new_flight["stop_label"] = classify_stops(flight["stop_count"])
        output.append(new_flight)
    return output