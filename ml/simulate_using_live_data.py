import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# --- Config ---
SLIPPAGE_TICKS = 1
TICK_SIZE = 0.25

# Load tick data (from your CSV)
tick_df = pd.read_csv("csv/market_data_log.csv", parse_dates=["timestamp"])

# Load daily levels and assign weights
daily_levels_df = pd.read_csv("csv/daily_levels.csv")
level_weights = {
    "POC": 1.0,
    "YESTERDAYS HIGH": 0.9,
    "YESTERDAYS LOW": 0.9,
    "YESTERDAYS VPOC": 0.95,
    "VALUE AREA": 0.8,
    "SUPPORT": 0.6,
    "RESISTANCE": 0.6,
    "WKO HIGH": 0.5,
    "WKOLOW": 0.5,
}

# Expand weights to rows

def get_level_weight(label):
    for key in level_weights:
        if key in label:
            return level_weights[key]
    return 0.3  # default weight

daily_levels_df["weight"] = daily_levels_df["Label"].apply(get_level_weight)

# Convert levels to float prices
daily_levels_df["Value"] = pd.to_numeric(daily_levels_df["Value"], errors="coerce")
levels = daily_levels_df.dropna().to_dict("records")

# --- Helper Functions ---
def apply_slippage(price):
    return price + random.choice([-1, 1]) * SLIPPAGE_TICKS * TICK_SIZE

def get_closest_level_weight(price):
    closest = min(levels, key=lambda lvl: abs(lvl["Value"] - price))
    dist = abs(price - closest["Value"])
    score = closest["weight"] / (1 + dist)
    return score, closest["Label"], closest["Value"]

def get_dynamic_tp_sl(price, score):
    base_tp = 8 * TICK_SIZE  # e.g., 2 points
    base_sl = 4 * TICK_SIZE  # e.g., 1 point
    return base_tp * (1 + score), base_sl * (1 - score / 2)

# --- Strategy Logic ---
class TradeSimulator:
    def __init__(self):
        self.open_trade = None
        self.trades = []

    def process_tick(self, row):
        ts, price = row["timestamp"], row["price"]

        if self.open_trade:
            # Monitor open trade
            direction = self.open_trade["direction"]
            entry_price = self.open_trade["entry_price"]
            tp = self.open_trade["tp"]
            sl = self.open_trade["sl"]

            if direction == "long":
                if price >= tp:
                    self.close_trade(ts, price, "TP")
                elif price <= sl:
                    self.close_trade(ts, price, "SL")
            else:
                if price <= tp:
                    self.close_trade(ts, price, "TP")
                elif price >= sl:
                    self.close_trade(ts, price, "SL")

        else:
            # Look for trade opportunities
            score, label, lvl_price = get_closest_level_weight(price)
            if score > 0.6:
                if abs(price - lvl_price) < 1.0:
                    if price > lvl_price:
                        self.open_trade = self.open_trade_at(ts, price, "breakout", "long", score)
                    elif price < lvl_price:
                        self.open_trade = self.open_trade_at(ts, price, "fade", "short", score)
                elif abs(price - lvl_price) < 2.0:
                    if price > lvl_price:
                        self.open_trade = self.open_trade_at(ts, price, "retest", "long", score)
                    elif price < lvl_price:
                        self.open_trade = self.open_trade_at(ts, price, "retest", "short", score)

    def open_trade_at(self, ts, price, signal_type, direction, score):
        fill_price = apply_slippage(price)
        tp_offset, sl_offset = get_dynamic_tp_sl(fill_price, score)
        trade = {
            "entry_time": ts,
            "entry_price": fill_price,
            "direction": direction,
            "signal_type": signal_type,
            "score": score,
        }
        if direction == "long":
            trade["tp"] = fill_price + tp_offset
            trade["sl"] = fill_price - sl_offset
        else:
            trade["tp"] = fill_price - tp_offset
            trade["sl"] = fill_price + sl_offset
        return trade

    def close_trade(self, ts, price, reason):
        self.open_trade["exit_time"] = ts
        self.open_trade["exit_price"] = price
        self.open_trade["exit_reason"] = reason
        self.open_trade["pnl"] = (
            (price - self.open_trade["entry_price"]) if self.open_trade["direction"] == "long"
            else (self.open_trade["entry_price"] - price)
        )
        self.trades.append(self.open_trade)
        self.open_trade = None

# --- Run Simulation ---
sim = TradeSimulator()
for _, row in tick_df.iterrows():
    sim.process_tick(row)

# Save trade logs
trades_df = pd.DataFrame(sim.trades)
trades_df.to_csv("csv/simulated_trades.csv", index=False)
print("Simulation complete. Saved to csv/simulated_trades.csv")
