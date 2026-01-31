FROM python:3.11-slim

WORKDIR /app

# ログをリアルタイム出力
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PORT=8080
EXPOSE 8080

# 起動コマンド
CMD ["python", "app.py"]
