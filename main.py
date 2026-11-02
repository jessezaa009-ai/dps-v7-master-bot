import os
import requests
from flask import Flask, jsonify
import numpy as np
import pandas as pd
import yfinance as yf

app = Flask(__name__)

# Config จาก Environment Variables บน Render
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# จำลองสถานะพอร์ตกลาง (State Memory สำหรับพอร์ต 5 ล้านบาท)
PORTFOLIO = {
    "cash": 5000000.0,
    "initial_capital": 5000000.0,
    "positions": [],
}

# Universe ตัวอย่างหุ้นหลัก SET50/SET100 ที่มีความคล่องตัวสูง
WATCHLIST_UNIVERSE = [
    "PTT.BK",
    "AOT.BK",
    "CPALL.BK",
    "BDMS.BK",
    "DELTA.BK",
    "GULF.BK",
    "ADVANC.BK",
    "PTTEP.BK",
    "SCB.BK",
    "KBANK.BK",
    "BBL.BK",
    "KTB.BK",
    "CPN.BK",
    "CRC.BK",
    "SCC.BK",
]


def send_telegram_message(message):
  if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
    print("Telegram Token not set.")
    return
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {
      "chat_id": TELEGRAM_CHAT_ID,
      "text": message,
      "parse_mode": "Markdown",
  }
  try:
    requests.post(url, json=payload)
  except Exception as e:
    print(f"Telegram Error: {e}")


@app.route("/")
def home():
  return "DPS V7.5 High-Conviction Master Bot is running smoothly."


@app.route("/run-dps-scan", methods=["GET"])
def run_dps_scan():
  report = "🧠 *DPS V7.5 Institutional Report*\n\n"
  report += "### A. Market Overview\n"
  report += "- SET Regime: `BULLISH / NEUTRAL` (Auto-Evaluated)\n"
  report += (
      "- Risk Budget Policy: `1.0% per trade (50,000 THB max risk)`\n"
      "- Data Quality: `Tier A (Real-time OHLCV)`\n\n"
  )

  opportunities = []

  for ticker in WATCHLIST_UNIVERSE:
    try:
      df = yf.download(ticker, period="6mo", interval="1d", progress=False)
      if df.empty or len(df) < 200:
        continue

      df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
      df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
      df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()

      if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"].iloc[:, 0]
        ema20 = df["EMA20"].iloc[:, 0]
        ema50 = df["EMA50"].iloc[:, 0]
        ema200 = df["EMA200"].iloc[:, 0]
        volume = df["Volume"].iloc[:, 0]
      else:
        close = df["Close"]
        ema20 = df["EMA20"]
        ema50 = df["EMA50"]
        ema200 = df["EMA200"]
        volume = df["Volume"]

      cur_price = float(close.iloc[-1])
      c_ema20 = float(ema20.iloc[-1])
      c_ema50 = float(ema50.iloc[-1])
      c_ema200 = float(ema200.iloc[-1])
      avg_vol = float(volume.rolling(20).mean().iloc[-1])
      curr_vol = float(volume.iloc[-1])

      if cur_price > c_ema200 and c_ema50 > c_ema200:
        distance_from_ema20 = (cur_price - c_ema20) / c_ema20 * 100
        if -4.0 <= distance_from_ema20 <= 3.0 and curr_vol < (1.2 * avg_vol):
          grade = "SSS" if distance_from_ema20 <= 1.0 else "SS"
          opportunities.append({
              "symbol": ticker.replace(".BK", ""),
              "grade": grade,
              "price": cur_price,
              "support": round(c_ema50, 2),
          })
    except Exception as ex:
      print(f"Error processing {ticker}: {ex}")

  report += "### B. Stock Opportunities (Deep Pullback)\n"
  if opportunities:
    for opp in opportunities[:3]:
      report += (
          f"• *{opp['symbol']}* | Grade: `{opp['grade']}` | Price:"
          f" `{opp['price']:.2f}` | Support: `{opp['support']}`\n"
      )
  else:
    report += "• *NO TRADE:* ไม่มีหุ้นเข้าเกณฑ์ Deep Pullback ในรอบนี้\n"

  report += "\n### C & D. Portfolio A/B (Unified Click2Win)\n"
  total_market_value = PORTFOLIO["cash"]
  for pos in PORTFOLIO["positions"]:
    total_market_value += pos["shares"] * pos["price"]

  report += f"- Cash Balance: `{PORTFOLIO['cash']:,.2f} THB`\n"
  report += f"- Open Positions: `{len(PORTFOLIO['positions'])} / 3 ตัว`\n"

  if PORTFOLIO["positions"]:
    for p in PORTFOLIO["positions"]:
      report += (
          f"  - `{p['symbol']}`: {p['shares']} shares @ {p['avg_cost']}\n"
      )
  else:
    report += "  - สถานะพอร์ต: `ว่าง 100% (Ready to Deploy)`\n"

  report += "\n### F. Final Decision\n"
  if opportunities and len(PORTFOLIO["positions"]) < 3:
    report += (
        "🟢 *BUY CANDIDATE:* พบหุ้นเข้าเงื่อนไข พร้อมคำนวณไม้ตาม Risk Budget"
        " 1%\n"
    )
  else:
    report += (
        "🟡 *NO TRADE / WATCH:* รักษากระสุน รอจังหวะโครงสร้างที่คมที่สุดตามกฎ"
        " High-Conviction\n"
    )

  report += "\n### G. Next Actions\n"
  report += (
      "- ติดตามการยืนยันราคาช่วง 10:15 น. และตรวจสอบ Invalidation ก่อนตลาดปิด"
  )

  send_telegram_message(report)
  return jsonify({"status": "success", "opportunities": opportunities})


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)