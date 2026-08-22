# Fare Tracker

A lightweight flight price comparison and historical low-price tracking tool, built with Flask and PostgreSQL (Neon). It searches flights, shows the cheapest option per airline, flags direct vs. connecting flights (separately for outbound and return legs), and — once enough data accumulates — tells you whether today's price ranks among the historical lows for that route.

> **中文摘要**：機票比價與歷史低價追蹤工具，用 Flask + PostgreSQL(Neon) 打造。可查詢航班、列出每家航空公司最便宜的選項、標示去程/回程各自是直達還是轉機，並在累積足夠資料後，告訴你今天查到的價格在這條航線的歷史紀錄裡排名如何。

---

## Overview

Fare Tracker searches round-trip or one-way flights between two airports, filters by departure time, and highlights the cheapest options — while keeping a running history in a database so it can tell you if a price you're seeing right now is unusually good compared to what's been seen before on that route.

> **中文摘要**：可查單程或來回航班，依出發時間篩選，找出最便宜的選項，並且把每次查詢結果存進資料庫，之後能比對「這個價格算不算難得一見的低價」。

## Features

- Search one-way or round-trip flights between any two airports
- Filter by departure time (hourly granularity), separately for outbound and return
- See the cheapest flight for each airline, sorted by price
- Direct / connecting flight labels shown separately for outbound and return legs
- Booking links where available (falls back to a generic "search the airline's website" note when not)
- Chinese airline/airport names shown where available
- Historical low-price ranking: once a route has 50+ recorded searches, the cheapest result is flagged if it ranks in the top 5 lowest prices ever seen for that route (one-way and round-trip tracked separately)
- Per-IP search cooldown to avoid hammering the underlying data source

> **中文摘要**：可依出發時間篩選、看每家航空最便宜的選項、去程回程分別標示直達/轉機、有訂票連結（查不到就顯示通用文字）、有中文機場/航空公司名稱、累積滿50筆歷史紀錄後會標示「是不是近期難得低價」（單程來回分開統計）、每個IP有搜尋冷卻機制避免濫用。

## Data Source & Disclaimer

This project uses [`fli`](https://pypi.org/project/flights/), an open-source, reverse-engineered client for Google Flights' internal (undocumented) API. **This is not an official Google Flights API integration** — there is no official public API for this data, and this project makes no claim of an authorized partnership with Google. Prices shown are for reference only; always verify the final price on the airline's or a booking platform's own site before purchasing.

> **中文摘要**：資料來源是 `fli`，一個開源、逆向工程 Google Flights 內部（非公開）API 的套件，**不是官方授權的 Google Flights API 串接**，本專案跟 Google 沒有任何合作關係。頁面上的價格僅供參考，實際訂票請務必以航空公司或訂票平台當下顯示的金額為準。

## Tech Stack

- **Backend**: Python, Flask, gunicorn
- **Database**: PostgreSQL via [Neon](https://neon.tech) (serverless Postgres, free tier)
- **Flight data**: [`fli`](https://pypi.org/project/flights/)
- **Frontend**: server-rendered HTML (Jinja2 templates)

## Project Structure

```
fare-tracker/
├── main.py                # Flask entry point
├── schema.sql              # Database table definitions (run once in your own Neon project)
├── requirements.txt
├── templates/
│   └── index.html
├── src/
│   ├── flight_search.py    # Talks to fli, returns a unified flight data format
│   ├── filters.py          # Filtering / sorting / labeling logic
│   ├── csv_reader.py        # Static lookups (airline/airport names, websites)
│   └── db.py                # Neon read/write layer
├── data/
│   ├── airlines.csv
│   └── airports.csv
└── scripts/
    └── data_pipeline/       # One-off scripts used to generate the data/ CSV files
```

> **中文摘要**：`main.py` 是進入點；`src/` 底下各檔案職責分離（查航班、篩選分類、讀CSV、存取資料庫）；`data/` 是靜態機場/航空公司資料；`scripts/data_pipeline/` 是當初產生這些CSV用的一次性腳本，留著是為了讓資料來源透明可查證。

---

## Setup Guide（安裝與執行說明）

以下步驟假設你的電腦上**完全沒有裝過 Python 或任何開發工具**，會盡量寫得詳細一點。如果你已經有開發環境，可以跳過前兩步直接從「Clone 專案」開始。

### 1. 安裝 Python

前往 [python.org/downloads](https://www.python.org/downloads/)，下載並安裝最新版本的 Python（建議 3.10 以上）。

**Windows 使用者請特別注意**：安裝過程中會有一個畫面，下方有個 **"Add python.exe to PATH"** 的勾選框，**請務必勾選**，不然之後在終端機打 `python` 指令會找不到。

安裝完成後，打開終端機（Windows 是「命令提示字元」或 PowerShell，Mac 是「終端機」App），輸入：

```
python --version
```

如果有印出版本號（例如 `Python 3.12.x`），代表安裝成功。

### 2. 安裝 VS Code（建議，非必要）

如果你想直接打開專案資料夾檢視程式碼，可以裝 [Visual Studio Code](https://code.visualstudio.com/)（免費）。這一步不是執行程式的必要條件，純粹方便你瀏覽/編輯檔案。

打開專案資料夾後，可以用內建終端機執行後面步驟的指令，不用另外開系統的終端機程式：按 `` Ctrl+` ``（Esc 鍵下方那個反引號鍵）就會在下方開啟終端機面板，之後的 `pip install`、`python main.py` 等指令都可以直接在這裡輸入。

### 3. Clone 專案

如果你有裝 Git，在終端機輸入：

```
git clone https://github.com/songhua-dev/fare-tracker.git
cd fare-tracker
```

如果你沒有裝 Git、也不想裝，也可以直接在 GitHub 頁面上點綠色的 **"Code"** 按鈕 → **"Download ZIP"**，下載後解壓縮，再用終端機 `cd` 進去那個資料夾。

### 4. 建立虛擬環境

虛擬環境可以讓這個專案要裝的套件，不會跟你電腦上其他 Python 專案互相干擾。在專案資料夾裡執行：

```
python -m venv venv
```

啟用虛擬環境：

- **Windows（PowerShell）**：
  ```
  venv\Scripts\activate
  ```
- **Windows（命令提示字元 cmd）**：
  ```
  venv\Scripts\activate.bat
  ```
- **Mac / Linux**：
  ```
  source venv/bin/activate
  ```

啟用成功的話，終端機的提示字元前面會多出 `(venv)` 字樣。**之後每次要跑這個專案，都要先啟用虛擬環境。**

### 5. 安裝套件

虛擬環境啟用的狀態下，執行：

```
pip install -r requirements.txt
```

### 6. 建立自己的 Neon 資料庫（選用）

> **這一步可以跳過。** 如果你懶得申請資料庫，或只是想先看看比價功能能不能動，直接跳到「8. 執行」也完全沒問題——程式偵測不到資料庫設定時，會自動跳過歷史紀錄寫入跟歷史低價標示這兩個功能，比價查詢本身照樣正常運作，不會報錯或卡住。之後想要「歷史低價」這個功能了，隨時回來做這一步跟下一步（建立 `.env`）就可以補上。

這個專案的歷史低價功能需要一個 PostgreSQL 資料庫，本專案使用 [Neon](https://neon.tech)（有免費方案，不需要信用卡）。

1. 前往 [neon.tech](https://neon.tech) 註冊帳號（可以用 GitHub 登入）
2. 建立一個新 Project（不需要勾選 "Enable Neon Auth"，那是額外的登入系統功能，這個專案用不到）
3. 進入 Project 後，找到 **SQL Editor**
4. 打開這個專案根目錄的 `schema.sql` 檔案，複製全部內容，貼到 SQL Editor 裡執行一次（這會建立兩張表：`searches` 跟 `flight_results`）
5. 回到 Project 首頁，找到你的 **connection string**（長得像 `postgresql://user:password@ep-xxxx.region.aws.neon.tech/dbname?sslmode=require`），複製下來

### 7. 建立 `.env` 檔案（選用，跳過第 6 步的話這步也一併跳過）

在專案根目錄（跟 `main.py` 同一層）建立一個叫 `.env` 的檔案，內容是：

```
NEON_URL = "貼上你剛剛複製的 connection string"
```

### 8. 執行

虛擬環境啟用的狀態下，執行：

```
python main.py
```

打開瀏覽器，前往：

```
http://127.0.0.1:5000
```

就可以開始查詢了。

---

## Known Limitations

- Flight data comes from an unofficial, reverse-engineered source (`fli`) — it can break if Google changes their internal API, and there's no SLA or guarantee of accuracy.
- The historical low-price feature needs at least 50 recorded searches for a given route (tracked separately for one-way vs. round-trip) before it shows a ranking — it stays quiet until enough data accumulates.
- The per-IP search cooldown is stored in memory, not the database, so it resets whenever the server restarts.
- Some ultra-cheap results may be self-transfer itineraries (e.g. two separately-booked legs with a layover you have to manage yourself) rather than a single airline-coordinated connection — always check the stop label and verify booking details before assuming a "cheapest" result is a simple, single-ticket itinerary.

> **中文摘要**：資料源是逆向工程套件，Google 改版可能會壞掉，沒有任何保證；歷史低價功能要累積滿50筆同航線資料才會顯示排名；搜尋冷卻機制存在記憶體，伺服器重啟會重置；有些超便宜的結果可能是「自己接的轉機」（分開訂票、自己處理轉機），不是航空公司安排好的單一行程，訂票前務必自己再確認清楚。

## If `fli` Stops Working

Since `fli` is an unofficial, reverse-engineered client, it can break without warning whenever Google changes their internal API. If flight searches suddenly start failing:

1. Check the [`fli` GitHub repo](https://github.com/punitarani/fli) for open issues — if Google changed something, other users have likely already reported it there.
2. Try upgrading to the latest version: `pip install --upgrade flights`
3. If there's no fix available yet, this is an inherent risk of relying on an unofficial API — there's no guaranteed timeline for a fix, and in the meantime the search feature simply won't work until either `fli` is patched or you find an alternative data source.

> **中文摘要**：`fli` 是逆向工程套件，Google 隨時可能改版讓它失效。遇到查詢突然失敗時：先去 `fli` 的 GitHub repo 看有沒有其他人回報同樣問題（有的話通常會有討論或修復進度）；試試看 `pip install --upgrade flights` 升級到最新版本；如果暫時沒有修復版本，這是依賴非官方 API 的固有風險，沒有保證的修復時程，這段期間查詢功能就是無法使用，除非等到 `fli` 修好或找到替代資料源。

## License

MIT License. Feel free to fork, modify, and reuse this project however you like.

> **中文摘要**：MIT 授權，歡迎自由轉叉、修改、引用。

## Acknowledgments

Built on top of [`fli`](https://github.com/punitarani/fli), an open-source reverse-engineered Google Flights client.