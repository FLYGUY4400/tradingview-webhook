import os
import csv
import time
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv
from topstepapi.market_data import MarketDataClient

# === ENV SETUP ===
load_dotenv()
CONTRACT_ID = "CON.F.US.MNQ.M25"
SESSION_TOKEN = os.getenv("TOPSTEPX_SESSION_TOKEN")

# === CSV SETUP ===
CSV_FILE = "csv/market_data_log.csv"
FIELDNAMES = ["timestamp", "price", "volume", "bid_price", "ask_price"]

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()


# === DATA LOGGER ===
class MarketDataLogger:
    def __init__(self):
        self.csv_file = CSV_FILE

    def on_tick(self, trade_data: dict):
        now = datetime.utcnow().isoformat()

        row = {
            "timestamp": now,
            "price": trade_data.get("price"),
            "volume": trade_data.get("volume"),
            "bid_price": trade_data.get("bidPrice"),
            "ask_price": trade_data.get("askPrice"),
        }

        with open(self.csv_file, mode="a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerow(row)

        print(row)


# === MAIN WRAPPER ===
class LiveMarketLoggerBot:
    def __init__(self, contract_id: str, token: str):
        self.contract_id = contract_id
        self.token = token
        self.logger = MarketDataLogger()
        self.market_data = MarketDataClient(
            token=self.token,
            contract_id=self.contract_id,
            on_trade_callback=self._handle_trade
        )

    def _handle_trade(self, args):
        contract_id, trades = args
        if not trades or contract_id != self.contract_id:
            return
        trade = trades[-1]  # Get most recent
        self.logger.on_tick(trade)

    def run(self):
        print("Starting market data capture to CSV...")
        self.market_data.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nCapture stopped.")
            self.market_data.stop()


# === ENTRYPOINT ===
if __name__ == "__main__":
    if not SESSION_TOKEN:
        raise ValueError("TOPSTEPX_SESSION_TOKEN is not set in .env")
    bot = LiveMarketLoggerBot(CONTRACT_ID, SESSION_TOKEN)
    bot.run()
