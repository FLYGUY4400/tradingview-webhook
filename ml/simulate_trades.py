import csv
from decimal import Decimal
from datetime import datetime
from itertools import product

# === CONFIGURATION ===
TP_VALUES = [10, 20, 30]
SL_VALUES = [10, 15, 20]
LOT_SIZES = [1, 2]
TICK_INTERVAL = 10  # Simulate trades every N ticks

CSV_FILE = "simulated_trades.csv"


# === SIMULATED TRADE OBJECT ===
class SimulatedTrade:
    def __init__(self, entry_price, direction, tp, sl, lot_size, timestamp):
        self.entry_price = entry_price
        self.direction = direction  # "long" or "short"
        self.tp = tp
        self.sl = sl
        self.lot_size = lot_size
        self.timestamp = timestamp
        self.is_open = True
        self.exit_price = None
        self.exit_time = None
        self.outcome = None  # "TP" or "SL"

    def update(self, current_price, now):
        if not self.is_open:
            return

        price_diff = current_price - self.entry_price if self.direction == "long" else self.entry_price - current_price

        if price_diff >= self.tp:
            self.outcome = "TP"
            self.exit_price = current_price
            self.exit_time = now
            self.is_open = False
        elif price_diff <= -self.sl:
            self.outcome = "SL"
            self.exit_price = current_price
            self.exit_time = now
            self.is_open = False

    def to_csv_row(self):
        return {
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price) if self.exit_price else None,
            "tp": float(self.tp),
            "sl": float(self.sl),
            "lot_size": self.lot_size,
            "outcome": self.outcome,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None
        }


# === SIMULATION ENGINE ===
class TradeSimulator:
    def __init__(self):
        self.live_price = None
        self.tick_count = 0
        self.open_trades = []
        self.param_combinations = list(product(TP_VALUES, SL_VALUES, LOT_SIZES))

        # Initialize CSV output
        with open(CSV_FILE, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "direction", "entry_price", "exit_price", "tp", "sl",
                "lot_size", "outcome", "exit_time"
            ])
            writer.writeheader()

    def on_tick(self, price):
        now = datetime.utcnow()
        self.live_price = Decimal(str(price))
        self.tick_count += 1

        # Simulate trade entries every TICK_INTERVAL
        if self.tick_count % TICK_INTERVAL == 0:
            for tp, sl, lot in self.param_combinations:
                for direction in ["long", "short"]:
                    self.open_trades.append(SimulatedTrade(
                        entry_price=self.live_price,
                        direction=direction,
                        tp=Decimal(tp),
                        sl=Decimal(sl),
                        lot_size=lot,
                        timestamp=now
                    ))

        # Update open trades
        for trade in self.open_trades:
            trade.update(self.live_price, now)

        # Write closed trades to CSV
        closed_trades = [t for t in self.open_trades if not t.is_open]
        if closed_trades:
            with open(CSV_FILE, mode="a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=closed_trades[0].to_csv_row().keys())
                for trade in closed_trades:
                    writer.writerow(trade.to_csv_row())
            self.open_trades = [t for t in self.open_trades if t.is_open]


# === USAGE EXAMPLE ===
# In your real bot's tick handler, simply call:
# simulator.on_tick(tick_price)

if __name__ == "__main__":
    # This section is for demonstration only.
    # In production, you'd import TradeSimulator and call .on_tick(price) from your live data feed.

    import random
    import time

    simulator = TradeSimulator()

    print("Starting tick simulation. Press Ctrl+C to stop.")
    try:
        while True:
            fake_price = 18500 + random.uniform(-10, 10)  # Simulated tick price
            simulator.on_tick(fake_price)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Simulation stopped.")
