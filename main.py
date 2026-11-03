import json
import os
import requests
from flask import Flask, jsonify, request
import numpy as np
import pandas as pd
import yfinance as yf

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

PORTFOLIO_FILE = "portfolio.json"


def load_portfolio():
  """โหลดข้อมูลพอร์ตจากไฟล์ JSON ถ้าไม่มีให้ใช้ค่าเริ่มต้น"""
  if os.path.exists(PORTFOLIO_FILE):
    try:
      with open(PORTFOLIO_FILE, "r") as f:
        return json.load(f)
    except Exception:
      pass
  return {
      "cash": 5000000.0,
      "initial_capital": 5000000.0,
      "max_risk_per_trade": 50000.0,
      "positions": [],
  }


def save_portfolio(portfolio):
  """บันทึกข้อมูลพอร์ตลงไฟล์ JSON"""
  try:
    with open(PORTFOLIO_FILE, "w") as f:
      json.dump(portfolio, f, indent=4)
  except Exception as e:
    print(f"Error saving portfolio: {e}")


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


def check_market_regime():
  try:
    set_df = yf.download("^SET.BK", period="1y", interval="1d", progress=False)
    if set_df.empty:
      return "NEUTRAL", True
    if isinstance(set_df.columns, pd.MultiIndex):
      set_close = set_df["Close"].iloc[:, 0]
    else:
      set_close = set_df["Close"]
    set_ema200 = set_close.ewm(span=200, adjust=False).mean()
    cur_set = float(set_close.iloc[-1])
    cur_ema200 = float(set_ema200.iloc[-1])
    return (
        ("BULLISH (Safe to Trade)", True)
        if cur_set > cur_ema200
        else ("BEARISH (Defensive Mode)", False)
    )
  except Exception:
    return "NEUTRAL", True


@app.route("/")
def home():
  return "DPS V7.5 Persistent Portfolio Bot is running."


@app.route("/buy", methods=["GET"])
def simulate_buy():
  portfolio = load_portfolio()
  symbol = request.args.get("symbol", "").upper()
  shares = int(request.args.get("shares", 0))
  price = float(request.args.get("price", 0.0))
  stop_loss = float(request.args.get("sl", 0.0))

  if not symbol or shares <= 0 or price <= 0:
    return jsonify({
        "status": "error",
        "message": "Use format: /buy?symbol=PTT&shares=5000&price=34.0&sl=32.5",
    })

  total_cost = shares * price
  if total_cost > portfolio["cash"]:
    return jsonify({"status": "error", "message": "Insufficient Cash Balance"})

  portfolio["cash"] -= total_cost
  portfolio["positions"].append({
      "symbol": symbol,
      "shares": shares,
      "avg_cost": price,
      "stop_loss": stop_loss,
  })

  save_portfolio(portfolio)

  send_telegram_message(
      f"🛒 *SIMULATED BUY SAVED*\n- Symbol: `{symbol}`\n- Shares:"
      f" `{shares:,}` @ `{price}`\n- Stop Loss: `{stop_loss}`"
  )
  return jsonify({"status": "success", "portfolio": portfolio})


@app.route("/run-dps-scan", methods=["GET"])
def run_dps_scan():
  portfolio = load_portfolio()
  regime_text, is_safe_market = check_market_regime()

  report = "📊 *DPS V7.5 Portfolio & Market Monitor*\n\n"
  report += f"### A. Market Regime: `{regime_text}`\n\n"

  # 1. ติดตามสถานะหุ้นในพอร์ต
  report += "### B. Active Positions (พอร์ตที่ถืออยู่ปัจจุบัน)\n"
  total_market_value = portfolio["cash"]

  if portfolio["positions"]:
    for pos in portfolio["positions"]:
      sym_bk = pos["symbol"] + ".BK"
      try:
        df_cur = yf.download(
            sym_bk, period="5d", interval="1d", progress=False
        )
        curr_p = (
            float(df_cur["Close"].iloc[-1].iloc[0])
            if isinstance(df_cur.columns, pd.MultiIndex)
            else float(df_cur["Close"].iloc[-1])
        )
      except Exception:
        curr_p = pos["avg_cost"]

      market_val = pos["shares"] * curr_p
      total_market_value += market_val
      pnl = (curr_p - pos["avg_cost"]) * pos["shares"]
      pnl_pct = ((curr_p - pos["avg_cost"]) / pos["avg_cost"]) * 100

      sl_warning = (
          " ⚠️ *[PRICE NEAR/BELOW STOP LOSS]*"
          if curr_p <= pos["stop_loss"]
          else ""
      )

      report += f"• **{pos['symbol']}**{sl_warning}\n"
      report += f"  - Shares: `{pos['shares']:,}` | Cost: `{pos['avg_cost']}`\n"
      report += f"  - Current: `{curr_p:.2f}` | Stop Loss: `{pos['stop_loss']}`\n"
      report += (
          f"  - Unrealized PnL: `{pnl:,.2f} THB` (`{pnl_pct:+.2f}%`)\n\n"
      )
  else:
    report += "• *พอร์ตว่าง 100%* (รอจังหวะ High-Conviction)\n\n"

  total_pnl = total_market_value - portfolio["initial_capital"]
  total_pnl_pct = (total_pnl / portfolio["initial_capital"]) * 100
  report += f"💰 **Total Portfolio Value:** `{total_market_value:,.2f} THB`\n"
  report += (
      f"📈 **Total PnL:** `{total_pnl:+,.2f} THB` (`{total_pnl_pct:+.2f}%`)\n"
      f"- Cash: `{portfolio['cash']:,.2f} THB`\n\n"
  )

  # 2. สแกนหาหุ้นใหม่
  if is_safe_market and len(portfolio["positions"]) < 3:
    report += "### C. New Opportunities Scan\n"
    opportunities = []
    for ticker in WATCHLIST_UNIVERSE:
      if ticker.replace(".BK", "") in [
          p["symbol"] for p in portfolio["positions"]
      ]:
        continue
      try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 200:
          continue

        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
        df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()

        high_low = df["High"] - df["Low"]
        high_close = abs(df["High"] - df["Close"].shift(1))
        low_close = abs(df["Low"] - df["Close"].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean()

        if isinstance(df.columns, pd.MultiIndex):
          close = df["Close"].iloc[:, 0]
          ema20 = df["EMA20"].iloc[:, 0]
          ema50 = df["EMA50"].iloc[:, 0]
          ema200 = df["EMA200"].iloc[:, 0]
          volume = df["Volume"].iloc[:, 0]
          atr = df["ATR"].iloc[:, 0]
        else:
          close = df["Close"]
          ema20 = df["EMA20"]
          ema50 = df["EMA50"]
          ema200 = df["EMA200"]
          volume = df["Volume"]
          atr = df["ATR"]

        cur_price = float(close.iloc[-1])
        c_ema20 = float(ema20.iloc[-1])
        c_ema50 = float(ema50.iloc[-1])
        c_ema200 = float(ema200.iloc[-1])
        c_atr = float(atr.iloc[-1])
        avg_vol = float(volume.rolling(20).mean().iloc[-1])
        curr_vol = float(volume.iloc[-1])

        if cur_price > c_ema200 and c_ema50 > c_ema200:
          distance_from_ema20 = (cur_price - c_ema20) / c_ema20 * 100
          if -4.0 <= distance_from_ema20 <= 3.0 and curr_vol < (1.2 * avg_vol):
            grade = "SSS" if distance_from_ema20 <= 1.0 else "SS"
            stop_loss = round(c_ema50 - (1.0 * c_atr), 2)
            risk_per_share = cur_price - stop_loss
            if risk_per_share <= 0:
              continue
            suggested_shares = int(
                portfolio["max_risk_per_trade"] / risk_per_share
            )
            suggested_shares = round(suggested_shares, -2) // 100 * 100
            if suggested_shares < 100:
              suggested_shares = 100
            take_profit = round(cur_price + (2.0 * risk_per_share), 2)

            opportunities.append({
                "symbol": ticker.replace(".BK", ""),
                "grade": grade,
                "price": cur_price,
                "shares": suggested_shares,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            })
      except Exception as ex:
        print(f"Error {ticker}: {ex}")

    if opportunities:
      for opp in opportunities[:2]:
        report += f"• 🟢 **{opp['symbol']}** (Grade: `{opp['grade']}`)\n"
        report += (
            f"  - Action: ซื้อ `{opp['shares']:,}` หุ้น @ `{opp['price']:.2f}`\n"
        )
        report += f"  - Stop Loss: `{opp['stop_loss']}` | TP: `{opp['take_profit']}`\n\n"
    else:
      report += "• ไม่มีหุ้นเข้าเกณฑ์เพิ่มเติมในรอบนี้\n"
  else:
    report += "### C. New Opportunities Scan\n• พอร์ตเต็มหรือตลาดอยู่ในโหมดพักตัว\n"

  send_telegram_message(report)
  return jsonify({"status": "success", "portfolio": portfolio})


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
