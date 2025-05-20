import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Parameters
SLIPPAGE_TICKS = 1  # Slippage in ticks
TICK_SIZE = 0.25
TICK_VALUE = 0.5
BASE_TP_TICKS = 12
BASE_SL_TICKS = 8
STRATEGY_TYPE = "breakout"  # can be "breakout", "retest", or "fade"
MAX_LOT_SIZE = 10

def level_weight(label):
    label = label.upper()
    for key, weight in level_weights.items():
        if key in label:
            return weight
    return 1.0

def determine_lot_size(weight: float, signal_type: str) -> int:
    base_size = 1
    if signal_type == "breakout":
        base_size += 1
    elif signal_type == "retest":
        base_size += 0
    elif signal_type == "fade":
        base_size = 1
    weight_factor = 1 + weight
    lot_size = int(round(base_size * weight_factor))
    return max(1, min(lot_size, MAX_LOT_SIZE))

def simulate_trades(tick_data_path="csv/market_data_log.csv", levels_path="csv/daily_levels.csv"):
    tick_data = pd.read_csv(tick_data_path, parse_dates=["timestamp"])
    levels_df = pd.read_csv("csv/daily_levels.csv")
    levels_df["Value"] = pd.to_numeric(levels_df["Value"], errors="coerce")
    levels_df.dropna(inplace=True)

    global level_weights
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

    simulated_trades = []
    active_trade = None

    for i in range(1, len(tick_data)):
        row = tick_data.iloc[i]
        price = row["price"]
        timestamp = row["timestamp"]

        if active_trade:
            if active_trade["side"] == "buy":
                if price >= active_trade["tp"] or price <= active_trade["sl"]:
                    active_trade["exit_price"] = price
                    active_trade["exit_time"] = timestamp
                    lots = determine_lot_size(active_trade["weight"], active_trade["signal_type"])
                    tick_diff = (price - active_trade["entry_price"]) / TICK_SIZE
                    active_trade["pnl"] = tick_diff * TICK_VALUE * lots
                    simulated_trades.append(active_trade)
                    active_trade = None
            elif active_trade["side"] == "sell":
                if price <= active_trade["tp"] or price >= active_trade["sl"]:
                    active_trade["exit_price"] = price
                    active_trade["exit_time"] = timestamp
                    lots = determine_lot_size(active_trade["weight"], active_trade["signal_type"])
                    tick_diff = (price - active_trade["entry_price"]) / TICK_SIZE
                    tick_diff = -tick_diff  # for short position
                    active_trade["pnl"] = tick_diff * TICK_VALUE * lots
                    simulated_trades.append(active_trade)
                    active_trade = None

        if active_trade:
            continue

        for _, level_row in levels_df.iterrows():
            level = level_row["Value"]
            label = level_row["Label"]
            weight = level_weight(label)

            tp_ticks = int(BASE_TP_TICKS * weight)
            sl_ticks = int(BASE_SL_TICKS * weight)
            slippage = SLIPPAGE_TICKS * TICK_SIZE

            if STRATEGY_TYPE == "breakout":
                if price > level + slippage and tick_data.iloc[i-1]["price"] <= level:
                    active_trade = {
                        "side": "buy",
                        "entry_price": price + slippage,
                        "tp": price + slippage + tp_ticks * TICK_SIZE,
                        "sl": price + slippage - sl_ticks * TICK_SIZE,
                        "entry_time": timestamp,
                        "level": label,
                        "weight": weight,
                        "signal_type": STRATEGY_TYPE,
                        "lot_size": determine_lot_size(weight, STRATEGY_TYPE)
                    }
                    break
                elif price < level - slippage and tick_data.iloc[i-1]["price"] >= level:
                    active_trade = {
                        "side": "sell",
                        "entry_price": price - slippage,
                        "tp": price - slippage - tp_ticks * TICK_SIZE,
                        "sl": price - slippage + sl_ticks * TICK_SIZE,
                        "entry_time": timestamp,
                        "level": label,
                        "weight": weight,
                        "signal_type": STRATEGY_TYPE,
                        "lot_size": determine_lot_size(weight, STRATEGY_TYPE)
                    }
                    break

            elif STRATEGY_TYPE == "retest":
                if abs(price - level) <= TICK_SIZE and tick_data.iloc[i-1]["price"] < level:
                    active_trade = {
                        "side": "buy",
                        "entry_price": price + slippage,
                        "tp": price + slippage + tp_ticks * TICK_SIZE,
                        "sl": price + slippage - sl_ticks * TICK_SIZE,
                        "entry_time": timestamp,
                        "level": label,
                        "weight": weight,
                        "signal_type": STRATEGY_TYPE,
                        "lot_size": determine_lot_size(weight, STRATEGY_TYPE)       
                    }
                    break
                elif abs(price - level) <= TICK_SIZE and tick_data.iloc[i-1]["price"] > level:
                    active_trade = {
                        "side": "sell",
                        "entry_price": price - slippage,
                        "tp": price - slippage - tp_ticks * TICK_SIZE,
                        "sl": price - slippage + sl_ticks * TICK_SIZE,
                        "entry_time": timestamp,
                        "level": label,
                        "weight": weight,
                        "signal_type": STRATEGY_TYPE,
                        "lot_size": determine_lot_size(weight, STRATEGY_TYPE)       
                    }
                    break

            elif STRATEGY_TYPE == "fade":
                if abs(price - level) <= TICK_SIZE:
                    if price < level:
                        active_trade = {
                            "side": "sell",
                            "entry_price": price - slippage,
                            "tp": price - slippage - tp_ticks * TICK_SIZE,
                            "sl": price - slippage + sl_ticks * TICK_SIZE,
                            "entry_time": timestamp,
                            "level": label,
                            "weight": weight,
                            "signal_type": STRATEGY_TYPE,
                            "lot_size": determine_lot_size(weight, STRATEGY_TYPE)       
                        }
                        break
                    else:
                        active_trade = {
                            "side": "buy",
                            "entry_price": price + slippage,
                            "tp": price + slippage + tp_ticks * TICK_SIZE,
                            "sl": price + slippage - sl_ticks * TICK_SIZE,
                            "entry_time": timestamp,
                            "level": label,
                            "weight": weight,
                            "signal_type": STRATEGY_TYPE,
                            "lot_size": determine_lot_size(weight, STRATEGY_TYPE)       
                        }
                        break

    if simulated_trades:
        trades_df = pd.DataFrame(simulated_trades)
        trades_df.to_csv("csv/simulated_trades.csv", index=False)
        print(f"✅ Simulated {len(trades_df)} trades. Saved to csv/simulated_trades.csv.")
    else:
        print("⚠️ No trades triggered. Adjust strategy or check your level/price data.")

if __name__ == "__main__":
    simulate_trades()
