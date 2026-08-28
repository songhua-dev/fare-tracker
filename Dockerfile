# 1. 基礎環境:用官方的 Python 3.12 精簡版image
FROM python:3.12-slim

# 2. 在 container 裡建立一個工作資料夾,之後的指令都在這裡執行
WORKDIR /app

# 3. 先只複製 requirements.txt(還沒複製其他程式碼)
COPY requirements.txt .

# 4. 安裝套件
RUN pip install --no-cache-dir -r requirements.txt

# 5. 複製你專案裡剩下的所有檔案(main.py、src/、templates/...)進去
COPY . .

# 6. 告訴外界這個 container 對外開放 5000 這個 port(Flask 預設的 port)
EXPOSE 5000

# 7. container 啟動時要執行的指令
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:5000"]