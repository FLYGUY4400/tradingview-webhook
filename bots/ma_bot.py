import os
import time
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from topstepapi import TopstepClient
from topstepapi.load_env import load_environment
from topstepapi.order import OrderAPI
from strategies.ma_crossover import RealTimeMACrossover  # <--- Import the strategy

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
TRADES_LOG = "trades.txt"

# Email config
EMAIL_ENABLED = True
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "dawsonbremner4400@gmail.com"
EMAIL_PASSWORD = "hqqu suys gbdi otnr"
TO_EMAIL = "dawsonbremner0@gmail.com"

class TradingBot:
    def __init__(self):
        load_environment()
        self.client = TopstepClient(
            username=os.getenv("TOPSTEPX_USERNAME"),
            api_key=os.getenv("TOPSTEPX_API_KEY")
        )
        self.order_api = OrderAPI(token=os.getenv("TOPSTEPX_SESSION_TOKEN"), base_url=os.getenv("TOPSTEP_BASE_URL"))

        self.contract_id = "CON.F.US.MNQ.M25"
        self.tp_points = Decimal("25")
        self.sl_points = Decimal("12.5")
        self.position_size = 2

        self.account_id = None
        self.current_position = 0
        self.latest_trade_price: Optional[Decimal] = None
        self.entry_price: Optional[Decimal] = None
        self.realized_pnl: Decimal = Decimal("0.0")

        # Strategy setup
        self.strategy = RealTimeMACrossover(
            client=self.client,
            trader=self,
            contract_id=self.contract_id,
            fast_period=10,
            slow_period=30,
            position_size=self.position_size
        )

    def setup(self):
        accounts = self.client.account.search_accounts(only_active=True)
        if not accounts:
            raise ValueError("No active trading accounts found")
        self.account_id = accounts[0]["id"]
        logger.info(f"Using account ID: {self.account_id}")

        positions = self.client.position.search_open_positions(self.account_id)
        for pos in positions:
            if pos["contractId"] == self.contract_id:
                self.current_position = pos["size"]
                self.entry_price = Decimal(str(pos["averageOpenPrice"]))
                logger.info(f"Found open position of size {self.current_position} at {self.entry_price}")

    def run(self):
        self.setup()

        from topstepapi.market_data import MarketDataClient
        self.market_data = MarketDataClient(
            token=os.getenv("TOPSTEPX_SESSION_TOKEN"),
            contract_id=self.contract_id,
            on_trade_callback=self._handle_market_trade
        )

        self.market_data.start()
        logger.info("Trading bot started")

        try:
            while True:
                self.check_positions()
                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("Bot shutting down")
            self.market_data.stop()

    def _handle_market_trade(self, args: List):
        contract_id, trade_data_list = args
        if not trade_data_list or contract_id != self.contract_id:
            return

        last_trade = trade_data_list[-1]
        price = Decimal(str(last_trade['price']))
        self.latest_trade_price = price

        logger.info(f"Latest market price: {price}")
        self.strategy.on_price(price)

    def place_trade(self, side: str, entry_price: Decimal, size: Optional[int] = None):
        side_num = 0 if side == "buy" else 1
        order_id = self.order_api.place_order(
            account_id=self.account_id,
            contract_id=self.contract_id,
            type=2,
            side=side_num,
            size=size or self.position_size
        )
        self.current_position = size or self.position_size
        self.entry_price = entry_price
        logger.info(f"Placed {side.upper()} order at {entry_price}")
        self.log_trade_event("ENTRY", entry_price)

    def check_positions(self):
        positions = self.client.position.search_open_positions(self.account_id)
        open_position = next((p for p in positions if p["contractId"] == self.contract_id), None)

        if open_position:
            return

        if self.current_position != 0:
            last_price = self.latest_trade_price or Decimal("0")
            pnl = (last_price - self.entry_price) * Decimal(self.current_position) * Decimal("2")
            if self.entry_price > last_price:
                pnl = -abs(pnl)
            pnl_delta = pnl - self.realized_pnl
            self.realized_pnl = pnl
            self.log_trade_event("EXIT", last_price, pnl, pnl_delta)
            self.current_position = 0
            self.entry_price = None

    def log_trade_event(self, event_type: str, price: Decimal, pnl: Optional[Decimal] = None, pnl_delta: Optional[Decimal] = None):
        timestamp = datetime.utcnow().isoformat()
        message = f"{timestamp} | {event_type} | Price: {price}"
        if pnl is not None:
            message += f" | Realized PnL: ${pnl:.2f} | Change: ${pnl_delta:.2f}"
        logger.info(message)
        with open(TRADES_LOG, "a") as f:
            f.write(message + "\n")

    def send_email(self, subject: str, body: str):
        if not EMAIL_ENABLED:
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = TO_EMAIL
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email sent: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
