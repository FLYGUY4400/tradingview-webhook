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

import joblib
import numpy as np
import pandas as pd

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
TRADES_LOG = "trades.txt"

EMAIL_ENABLED = True
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "dawsonbremner4400@gmail.com"
EMAIL_PASSWORD = "hqqu suys gbdi otnr"
TO_EMAIL = "dawsonbremner0@gmail.com"

def round_to_tick(price, tick_size=Decimal('0.25')):
    if not isinstance(price, Decimal):
        price = Decimal(str(price))
    if not isinstance(tick_size, Decimal):
        tick_size = Decimal(str(tick_size))
    return (price / tick_size).to_integral_value(rounding='ROUND_HALF_UP') * tick_size

class MicroScalper:
    def __init__(self, bot):
        self.bot = bot
        self.last_prices = []
        self.last_volumes = []
        self.window_size = 5
        self.threshold = 1.0
        self.last_timestamp = None

    def on_trade(self, price: Decimal, volume: Optional[int] = None, timestamp: Optional[str] = None):
        self.last_prices.append(price)
        self.last_volumes.append(volume if volume is not None else 1)  # Default to 1 if no volume
        if timestamp:
            self.last_timestamp = timestamp
            
        if len(self.last_prices) > self.window_size:
            self.last_prices.pop(0)
            if self.last_volumes:  # Only pop if we have volumes
                self.last_volumes.pop(0)
            self.check_signal()

    def check_signal(self):
        if self.bot.current_position != 0:
            return

        delta = self.last_prices[-1] - self.last_prices[0]
        if delta > self.threshold:
            self.bot.place_trade("sell", self.last_prices[-1])
        elif delta < -self.threshold:
            self.bot.place_trade("buy", self.last_prices[-1])

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
        self.position_size = 1

        self.account_id = None
        self.current_position = 0
        self.latest_trade_price: Optional[Decimal] = None
        self.entry_price: Optional[Decimal] = None
        self.realized_pnl: Decimal = Decimal("0.0")
        
        # Track TP/SL orders
        self.active_tp_order_id: Optional[int] = None
        self.active_sl_order_id: Optional[int] = None
        self.main_order_id: Optional[int] = None

        self.scalper = MicroScalper(self)

        self.bot = joblib.load("../ml/model/trained_models/trade_param_model.joblib")

    def fetch_historical_volumes(self, lookback_minutes: int = 5):
        """Fetch historical bars with volume data"""
        try:
            end_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
            start_time = (datetime.utcnow() - timedelta(minutes=lookback_minutes)).strftime('%Y-%m-%dT%H:%M:%S')
            
            bars = self.client.history.retrieve_bars(
                contract_id=self.contract_id,
                live=True,
                start_time=start_time,
                end_time=end_time,
                unit=1,  # 1 minute bars
                unit_number=1,
                limit=lookback_minutes,
                include_partial_bar=True
            )
            
            if bars:
                # Sort by timestamp in case they're out of order
                bars.sort(key=lambda x: x['t'])
                # Update volumes in scalper
                for bar in bars:
                    if 'v' in bar and bar['v'] > 0:  # Only update if we have volume data
                        self.scalper.on_trade(
                            price=Decimal(str(bar['c'])),
                            volume=bar['v'],
                            timestamp=bar['t']
                        )
                logger.info(f"Fetched {len(bars)} historical bars with volume data")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error fetching historical volumes: {e}")
            return False

    def setup(self):
        accounts = self.client.account.search_accounts(only_active=True)
        if not accounts:
            raise ValueError("No active trading accounts found")
        self.account_id = accounts[0]["id"]
        logger.info(f"Using account ID: {self.account_id}")

        # Fetch historical volume data
        if not self.fetch_historical_volumes(lookback_minutes=15):
            logger.warning("Could not fetch historical volume data, using default values")

        positions = self.client.position.search_open_positions(self.account_id)
        for pos in positions:
            if pos["contractId"] == self.contract_id:
                self.current_position = pos["size"]
                self.entry_price = Decimal(str(pos["averageOpenPrice"]))
                logger.info(f"Found open position of size {self.current_position} at {self.entry_price}")

    def get_feature_columns(self):
        """Return the expected feature columns in the correct order"""
        return [
            'price_mean', 'price_std', 'price_min', 'price_max',
            'price_range', 'price_slope', 'mean_volume', 'sum_volume', 'volume_std'
        ]
        
    def extract_features(self) -> Optional[dict]:
        if len(self.scalper.last_prices) < self.scalper.window_size:
            return None

        prices = np.array(self.scalper.last_prices)
        volumes = np.array(self.scalper.last_volumes if hasattr(self.scalper, 'last_volumes') and len(self.scalper.last_volumes) > 0 else np.ones_like(prices))
        
        # Ensure we have enough data
        if len(volumes) < 2:
            volumes = np.ones_like(prices)
        
        # Calculate features in the same order as feature_columns
        features = {
            'price_mean': float(prices.mean()),
            'price_std': float(prices.std() if len(prices) > 1 else 0.0),
            'price_min': float(prices.min()),
            'price_max': float(prices.max()),
            'price_range': float(prices.ptp() if len(prices) > 1 else 0.0),
            'price_slope': float((prices[-1] - prices[0]) / len(prices)) if len(prices) > 1 else 0.0,
            'mean_volume': float(volumes.mean() if len(volumes) > 0 else 0.0),
            'sum_volume': float(volumes.sum() if len(volumes) > 0 else 0.0),
            'volume_std': float(volumes.std() if len(volumes) > 1 else 0.0)
        }
        
        # Ensure all expected features are present and in the right order
        return {col: features[col] for col in self.get_feature_columns()}
    
    
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
                try:
                    self.check_positions()
                    self.check_and_cancel_orders()
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(5)  # Wait before retrying
        except KeyboardInterrupt:
            logger.info("Bot shutting down")
            self.cancel_all_orders()  # Clean up any open orders
            self.market_data.stop()

    def _handle_market_trade(self, args: List):
        """Handle incoming market trade data"""
        try:
            contract_id, trades = args
            if contract_id != self.contract_id or not trades:
                return

            latest_trade = trades[-1]
            price = Decimal(str(latest_trade['price']))
            volume = latest_trade.get('size', 1)  # Default to 1 if size not available
            timestamp = latest_trade.get('time')
            self.latest_trade_price = price
            
            # Update scalper with latest price and volume
            self.scalper.on_trade(price=price, volume=volume, timestamp=timestamp)
            
            # Check if we should place a trade
            self.check_trade_conditions(price)
            
        except Exception as e:
            logger.error(f"Error in _handle_market_trade: {e}")

    def check_and_cancel_orders(self):
        """Check if either TP or SL was hit and cancel the other order."""
        if self.active_tp_order_id and self.active_sl_order_id:
            # Check TP order status
            try:
                tp_orders = self.order_api.search_orders(
                    account_id=self.account_id,
                    start_timestamp=str(datetime.utcnow().isoformat())
                )
                tp_active = any(order['orderId'] == self.active_tp_order_id and 
                              order['status'] == 'Filled' 
                              for order in tp_orders)
                
                # If TP was filled, cancel SL
                if tp_active:
                    self.order_api.cancel_order(
                        account_id=self.account_id,
                        order_id=self.active_sl_order_id
                    )
                    logger.info(f"TP hit at order {self.active_tp_order_id}, cancelled SL {self.active_sl_order_id}")
                    self.active_sl_order_id = None
                    self.active_tp_order_id = None
                    return
                
                # Check SL order status
                sl_orders = self.order_api.search_orders(
                    account_id=self.account_id,
                    start_timestamp=str(datetime.utcnow().isoformat())
                )
                sl_active = any(order['orderId'] == self.active_sl_order_id and 
                              order['status'] == 'Filled' 
                              for order in sl_orders)
                
                # If SL was filled, cancel TP
                if sl_active:
                    self.order_api.cancel_order(
                        account_id=self.account_id,
                        order_id=self.active_tp_order_id
                    )
                    logger.info(f"SL hit at order {self.active_sl_order_id}, cancelled TP {self.active_tp_order_id}")
                    self.active_sl_order_id = None
                    self.active_tp_order_id = None
            except Exception as e:
                logger.error(f"Error checking order status: {e}")


    def place_trade(self, side: str, entry_price: Decimal):
        features_dict = self.extract_features()
        if features_dict is None:
            logger.warning("Not enough data to place trade")
            return

        try:
            # Get feature columns in the correct order
            feature_columns = self.get_feature_columns()
            
            # Create a DataFrame with features in the expected order
            features_list = [[features_dict[col] for col in feature_columns]]
            
            # Convert to numpy array for prediction
            features_array = np.array(features_list, dtype=np.float32)
            
            # Make prediction using numpy array to avoid feature name issues
            predictions = self.bot.predict(features_array)
            
            if len(predictions) == 0:
                logger.warning("No predictions returned from model")
                return
                
            predicted = predictions[0]
            if len(predicted) < 3:
                logger.warning(f"Unexpected prediction format: {predicted}")
                return
                
            # Extract values safely
            predicted_tp = float(predicted[0])
            predicted_sl = float(predicted[1])
            lot_size = max(1, int(round(predicted[2])))  # Ensure at least 1 lot

            # Store predictions
            self.tp_points = Decimal(str(predicted_tp))
            self.sl_points = Decimal(str(predicted_sl))
            self.position_size = lot_size

            logger.info(f"Predicted TP: {self.tp_points}, SL: {self.sl_points}, Lot Size: {lot_size}")
            
            side_num = 0 if side == "buy" else 1
            
            # First, cancel any existing orders
            self.cancel_all_orders()
            
            # Place the main market order
            self.main_order_id = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=self.contract_id,
                type=2,  # Market order
                side=side_num,  # 0 for buy, 1 for sell
                size=self.position_size
            )
            
            if not self.main_order_id:
                raise Exception("Failed to place main order")

            # For BUY orders (0): TP is SELL LIMIT, SL is SELL STOP
            # For SELL orders (1): TP is BUY LIMIT, SL is BUY STOP
            tp_sl_side = 1 if side_num == 0 else 0  # Opposite side of the main order

            # Calculate TP/SL prices based on order direction and round to tick size
            if side_num == 0:  # BUY
                tp_price = round_to_tick(entry_price + self.tp_points)
                sl_price = round_to_tick(entry_price - self.sl_points)
            else:  # SELL
                tp_price = round_to_tick(entry_price - self.tp_points)
                sl_price = round_to_tick(entry_price + self.sl_points)

            # Place Take Profit order (LIMIT)
            self.active_tp_order_id = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=self.contract_id,
                type=1,  # LIMIT order
                side=tp_sl_side,
                size=self.position_size,
                linked_order_id=self.main_order_id,
                limit_price=tp_price
            )

            # Place Stop Loss order (STOP)
            self.active_sl_order_id = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=self.contract_id,
                type=4,  # STOP order
                side=tp_sl_side,
                size=self.position_size,
                linked_order_id=self.main_order_id,
                stop_price=sl_price
            )

            logger.info(f"Main Order Placed: {self.main_order_id}")
            logger.info(f"TP Order Placed: {self.active_tp_order_id} at {tp_price} (points: {self.tp_points})")
            logger.info(f"SL Order Placed: {self.active_sl_order_id} at {sl_price} (points: {self.sl_points})")
            
            # Update position state
            self.current_position = self.position_size if side == "buy" else -self.position_size
            self.entry_price = entry_price
            logger.info(f"Placed {side.upper()} order at {entry_price}")
            self.log_trade_event("ENTRY", entry_price)
            self.send_email("Trade Entry", f"{side.upper()} entry at {entry_price} | Order ID: {self.main_order_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error placing trade: {e}")
            # Clean up any partially placed orders
            self.cancel_all_orders()
            raise
            
    def cancel_all_orders(self):
        """Cancel all active TP/SL orders."""
        try:
            if self.active_tp_order_id:
                self.order_api.cancel_order(
                    account_id=self.account_id,
                    order_id=self.active_tp_order_id
                )
                logger.info(f"Cancelled TP order: {self.active_tp_order_id}")
                
            if self.active_sl_order_id:
                self.order_api.cancel_order(
                    account_id=self.account_id,
                    order_id=self.active_sl_order_id
                )
                logger.info(f"Cancelled SL order: {self.active_sl_order_id}")
                
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
        finally:
            self.active_tp_order_id = None
            self.active_sl_order_id = None
            self.main_order_id = None

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
            self.send_email("Trade Exit", f"Exited at {last_price}\nPnL: ${pnl:.2f}\nChange: ${pnl_delta:.2f}")
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
