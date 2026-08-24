"""
src/i18n.py
多語系字典與翻譯管理模組 (無狀態、防循環引用設計)
"""

import json
import os
from typing import Dict, Any, Optional

class I18nManager:
    def __init__(self, default_lang: str = "zh_TW"):
        self.default_lang = default_lang
        self.translations: Dict[str, Dict[str, str]] = {}
        
        # 內建預設字典
        self._builtin_translations = {
            "zh_TW": {
                "site_title": "機票比價與歷史價格追蹤",
                "welcome": "歡迎使用本系統",
                "success": "操作成功",
                "error_occurred": "發生錯誤：{error}",
                "invalid_airport_code": "輸入機場錯誤: '{code}' 不是有效的機場代碼",
                "stop_direct": "直達",
                "stop_1_transfer": "轉機一次",
                "stop_n_transfers": "轉機{count}次",
                "err_neon_url_not_set": "環境變數 NEON_URL 未設定，請檢查本機 .env 或 Render 的環境變數設定",
                "disclaimer": "本頁價格僅供參考，實際訂票請以航空公司或訂票平台當下顯示金額為準。",
                "err_cooldown": "查詢太頻繁，請等 {seconds} 秒後再試一次",
                "err_invalid_return_date": "回程日期不能早於出發日期",
                "err_invalid_adults": "人數必須是數字",
                "label_origin": "出發地 (機場或城市代碼)",
                "label_destination": "目的地 (機場或城市代碼)",
                "label_depart_date": "去程日期",
                "label_depart_time_after": "去程出發時間不早於",
                "label_return_date": "回程日期 (單程免填)",
                "label_return_time_after": "回程出發時間不早於",
                "label_adults": "乘客人數 (成人)",
                "placeholder_origin": "例如：TPE 或 台北",
                "placeholder_destination": "例如：NRT 或 東京",
                "option_all_day": "不限時間 (全天)",
                "option_after_hour": "{hour} 以後",
                "btn_search": "搜尋最低機票價格",
                "error_prefix": "搜尋失敗：",
                "empty_results": "找不到符合條件的航班，請調整搜尋條件後重試。",
                "title_cheapest_per_airline": "各航空公司最低價組合",
                "title_all_results": "所有搜尋結果 (依價格排序)",
                "meta_outbound_stop": "去程：{stop}",
                "meta_return_stop": "回程：{stop}",
                "btn_book": "前往官網訂票",
                "no_booking_url": "無直接預訂連結",
                "flight_duration": "飛行時間 {minutes} 分鐘",
                "tag_outbound": "去程",
                "tag_return": "回程",
                "depart_time_format": "出發時間：{time}",
                "price_rank_badge": "歷史價格前 {rank} 低 (共 {total} 筆紀錄)",
                "label_direct_only": "僅限直飛航班",
            },
            "en_US": {
                "site_title": "Flight Comparison & Price History Tracker",
                "welcome": "Welcome to the system",
                "success": "Operation successful",
                "error_occurred": "An error occurred: {error}",
                "invalid_airport_code": "Invalid airport error: '{code}' is not a valid airport code",
                "stop_direct": "Direct",
                "stop_1_transfer": "1 stop",
                "stop_n_transfers": "{count} stops",
                "err_neon_url_not_set": "Environment variable NEON_URL is not set. Please check local .env or Render environment settings.",
                "disclaimer": "Prices are for reference only. Please refer to the airline or booking platform for actual prices.",
                "err_cooldown": "Search rate limit reached. Please wait {seconds} seconds before trying again.",
                "err_invalid_return_date": "Return date cannot be earlier than departure date.",
                "err_invalid_adults": "Number of passengers must be a valid number.",
                "label_origin": "Origin (Airport or City Code)",
                "label_destination": "Destination (Airport or City Code)",
                "label_depart_date": "Departure Date",
                "label_depart_time_after": "Depart No Earlier Than",
                "label_return_date": "Return Date (Optional for One-way)",
                "label_return_time_after": "Return No Earlier Than",
                "label_adults": "Passengers (Adults)",
                "placeholder_origin": "e.g., TPE or Taipei",
                "placeholder_destination": "e.g., NRT or Tokyo",
                "option_all_day": "Anytime (All Day)",
                "option_after_hour": "After {hour}",
                "btn_search": "Search Cheapest Flights",
                "error_prefix": "Search Failed: ",
                "empty_results": "No flights found matching your criteria. Please try different search parameters.",
                "title_cheapest_per_airline": "Cheapest Option per Airline",
                "title_all_results": "All Results (Sorted by Price)",
                "meta_outbound_stop": "Outbound: {stop}",
                "meta_return_stop": "Return: {stop}",
                "btn_book": "Book on Official Site",
                "no_booking_url": "No Booking URL",
                "flight_duration": "Duration: {minutes} mins",
                "tag_outbound": "Outbound",
                "tag_return": "Return",
                "depart_time_format": "Departure: {time}",
                "price_rank_badge": "Rank #{rank} lowest in history ({total} records total)",
                "label_direct_only": "Direct flights only",
            }
        }
        self.translations.update(self._builtin_translations)

    def _normalize_lang(self, lang: Optional[str]) -> str:
        """將傳入的語系參數對齊至字典 key (例如: zh -> zh_TW, en -> en_US)"""
        if not lang:
            return self.default_lang
        
        lang_str = str(lang).lower()
        if lang_str.startswith("en"):
            return "en_US"
        elif lang_str.startswith("zh"):
            return "zh_TW"
        
        return self.translations.get(lang, self.default_lang)

    def get_text(self, key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
        """
        取得翻譯文字，支援動態變數與無狀態 lang 傳入
        :param key: 字典 Key
        :param lang: 當前請求帶入的語言參數 (例如 request.args.get('lang'))
        """
        target_lang = self._normalize_lang(lang)
        lang_dict = self.translations.get(target_lang, self.translations.get(self.default_lang, {}))
        text = lang_dict.get(key, key)  # 若找不到 key 則返回 key 本身

        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                return text
        return text

    def load_from_json(self, json_path: str, lang: str) -> None:
        """從外部 JSON 檔案擴充字典"""
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                target_lang = self._normalize_lang(lang)
                if target_lang not in self.translations:
                    self.translations[target_lang] = {}
                self.translations[target_lang].update(data)

# 全域單例
i18n = I18nManager()

def get_text(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """文字翻譯專用主函式"""
    return i18n.get_text(key, lang=lang, **kwargs)

def _(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """國際化簡寫函式"""
    return i18n.get_text(key, lang=lang, **kwargs)