from src.filters import add_stop_label, classify_stops, find_cheapest, find_cheapest_per_airline
from src.flight_search import search_cheapest

# ------------------------------------------------------------------
# 1. 單程查詢 + 串 filters.py（驗證扁平結構）
# ------------------------------------------------------------------
print("========== 單程查詢 ==========")
flights_ow = search_cheapest(
    adults=1,
    origin="TPE",
    destination="NRT",
    depart_date="2026-10-25",
)
for f in flights_ow:
    print(f)

print("\n--- 單程 + stop_label ---")
flights_ow_labeled = add_stop_label(flights_ow)
for f in flights_ow_labeled:
    print(f["price"], f["stop_label"])

print("\n--- 單程：全部結果裡最便宜的一筆 ---")
cheapest_ow = find_cheapest(flights_ow)
print(cheapest_ow)

print("\n--- 單程：每家航空公司各自最便宜 ---")
cheapest_per_airline_ow = find_cheapest_per_airline(flights_ow)
for f in cheapest_per_airline_ow:
    print(f["airline_name"], "->", f["price"])


# ------------------------------------------------------------------
# 2. 來回查詢 + 串 filters.py（驗證巢狀結構）
# ------------------------------------------------------------------
print("\n\n========== 來回查詢 ==========")
flights_rt = search_cheapest(
    adults=1,
    origin="TPE",
    destination="NRT",
    depart_date="2026-10-25",
    return_date="2026-11-02",
)
for f in flights_rt:
    print(f)

print("\n--- 來回 + stop_label ---")
flights_rt_labeled = add_stop_label(flights_rt)
for f in flights_rt_labeled:
    print(f["price"], f["stop_label"])

print("\n--- 來回：全部結果裡最便宜的一筆 ---")
cheapest_rt = find_cheapest(flights_rt)
print(cheapest_rt)

print("\n--- 來回：每家航空公司各自最便宜 ---")
cheapest_per_airline_rt = find_cheapest_per_airline(flights_rt)
for f in cheapest_per_airline_rt:
    print(f["outbound"]["airline_name"], "->", f["price"])


# ------------------------------------------------------------------
# 3. 錯誤機場代碼測試
# ------------------------------------------------------------------
print("\n\n========== 錯誤機場代碼測試 ==========")
try:
    search_cheapest(adults=1, origin="XXX", destination="NRT", depart_date="2026-10-25")
except ValueError as e:
    print(f"預期內的錯誤: {e}")