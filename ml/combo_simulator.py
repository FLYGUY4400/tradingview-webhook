import pandas as pd
from datetime import datetime, timedelta

# Load files
trades = pd.read_csv("csv/simulated_trades.csv", parse_dates=["entry_time", "exit_time"])
ticks = pd.read_csv("csv/market_data_log.csv", parse_dates=["timestamp"])

# Constants
TICK_SIZE = 0.25  # MNQ tick size

# Each value represents ticks
TP_GRID = [i for i in range(4, 81, 4)]   # 4 to 80 ticks => 1 to 20 points
SL_GRID = [i for i in range(4, 41, 4)]   # 4 to 40 ticks => 1 to 10 points
LOT_GRID = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
MAX_HOLD_TIME = timedelta(seconds=600)

results = []

for _, trade in trades.iterrows():
    entry_time = trade['entry_time']
    entry_price = trade['entry_price']
    side = trade['side']
    signal_type = trade['signal_type']
    level = trade['level']
    weight = trade['weight']

    # Subset market data from entry_time
    future_ticks = ticks[ticks['timestamp'] >= entry_time].copy()

    for tp_ticks in TP_GRID:
        for sl_ticks in SL_GRID:
            for lot in LOT_GRID:
                hit_tp = hit_sl = False
                exit_price = entry_price
                exit_time = entry_time + MAX_HOLD_TIME

                tp_points = tp_ticks * TICK_SIZE
                sl_points = sl_ticks * TICK_SIZE

                for _, tick in future_ticks.iterrows():
                    price = tick['price']
                    time = tick['timestamp']

                    # Respect max hold time
                    if time - entry_time > MAX_HOLD_TIME:
                        break

                    if side == "buy":
                        if price >= entry_price + tp_points:
                            hit_tp = True
                            exit_price = entry_price + tp_points
                            exit_time = time
                            break
                        elif price <= entry_price - sl_points:
                            hit_sl = True
                            exit_price = entry_price - sl_points
                            exit_time = time
                            break
                    elif side == "sell":
                        if price <= entry_price - tp_points:
                            hit_tp = True
                            exit_price = entry_price - tp_points
                            exit_time = time
                            break
                        elif price >= entry_price + sl_points:
                            hit_sl = True
                            exit_price = entry_price + sl_points
                            exit_time = time
                            break

                # Calculate PnL
                if side == "buy":
                    pnl = (exit_price - entry_price) * lot
                else:
                    pnl = (entry_price - exit_price) * lot

                results.append({
                    "entry_time": entry_time,
                    "side": side,
                    "entry_price": entry_price,
                    "tp_ticks": tp_ticks,
                    "sl_ticks": sl_ticks,
                    "tp_points": tp_points,
                    "sl_points": sl_points,
                    "lot_size": lot,
                    "exit_price": exit_price,
                    "exit_time": exit_time,
                    "pnl": pnl,
                    "signal_type": signal_type,
                    "level": level,
                    "weight": weight
                })

# Save results
df = pd.DataFrame(results)
df.to_csv("csv/simulated_training_data.csv", index=False)
print("✅ Simulation complete. Output written to csv/simulated_training_data.csv")
