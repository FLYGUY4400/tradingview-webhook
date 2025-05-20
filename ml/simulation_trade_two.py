import os
import csv
import time
from decimal import Decimal
from datetime import datetime
from itertools import product
from dotenv import load_dotenv
from topstepapi.market_data import MarketDataClient

# === ENV SETUP ===
load_dotenv()
CONTRACT_ID = "CON.F.US.MNQ.M25"
SESSION_TOKEN = os.getenv("TOPSTEPX_SESSION_TOKEN")

# === CONFIGURATION ===
TP_VALUES = [2,3,4,5,6,7,8,9,10, 20, 30]
SL_VALUES = [2,3,4,5,6,7,8,9,10,20,30]
LOT_SIZES = [1, 2,3,4,5,6,7,8,9,10]
TICK_INTERVAL = 10
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
        if self.exit_price is None:
            pnl = None
        else:
            price_diff = (
                self.exit_price - self.entry_price
            if self.direction == "long"
            else self.entry_price - self.exit_price
        )
        pnl = float(price_diff * self.lot_size)

        return {
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price) if self.exit_price else None,
            "tp": float(self.tp),
            "sl": float(self.sl),
            "lot_size": self.lot_size,
            "outcome": self.outcome,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl": pnl
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

    def on_tick(self, price: float):
        now = datetime.utcnow()
        self.live_price = Decimal(str(price))
        self.tick_count += 1

        # Simulate new trade entries
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

        # Update all trades
        for trade in self.open_trades:
            trade.update(self.live_price, now)

        # Write closed trades
        closed = [t for t in self.open_trades if not t.is_open]
        if closed:
            with open(CSV_FILE, mode="a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=closed[0].to_csv_row().keys())
                for trade in closed:
                    writer.writerow(trade.to_csv_row())
            self.open_trades = [t for t in self.open_trades if t.is_open]


# === MAIN BOT WRAPPER ===
class LiveSimulatedBot:
    def __init__(self, contract_id: str, token: str):
        self.contract_id = contract_id
        self.token = token
        self.simulator = TradeSimulator()
        self.market_data = MarketDataClient(
            token=self.token,
            contract_id=self.contract_id,
            on_trade_callback=self._handle_trade
        )

    def _handle_trade(self, args):
        contract_id, trades = args
        if not trades or contract_id != self.contract_id:
            return
        price = trades[-1]["price"]
        print(f"Tick: {price}")
        self.simulator.on_tick(price)

    def run(self):
        print("Starting live market data feed...")
        self.market_data.start()  # Changed from connection() to start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nSimulation ended.")
            self.market_data.stop()  # Properly clean up the connection


# === ENTRYPOINT ===
if __name__ == "__main__":
    if not SESSION_TOKEN:
        raise ValueError("TOPSTEPX_SESSION_TOKEN is not set in environment")
    bot = LiveSimulatedBot(CONTRACT_ID, SESSION_TOKEN)
    bot.run()
