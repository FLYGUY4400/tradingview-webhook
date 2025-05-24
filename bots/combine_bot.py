import logging
import numpy as np
from datetime import datetime
from your_topstep_api import OrderClient, MarketDataClient, HistoryAPI
from your_ml_model import TradeQualityClassifier
from levels import get_daily_levels

logger = logging.getLogger("TopstepBot")

class CombineSafeBot:
    def __init__(self, contract_id, max_daily_loss, max_position_size):
        self.contract_id = contract_id
        self.order_client = OrderClient()
        self.market_client = MarketDataClient()
        self.history_api = HistoryAPI()
        self.model = TradeQualityClassifier.load("trade_quality_model.joblib")  # Pretrained
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.daily_pnl = 0
        self.current_position = 0
        self.last_entry_price = None
        self.levels = {}

        self.market_client.subscribe_trades(contract_id, self.on_trade)

    def on_trade(self, price):
        if self.is_market_open():
            self.levels = get_daily_levels(self.history_api, self.contract_id)
            if self.daily_pnl < -self.max_daily_loss:
                logger.warning("Daily loss limit reached. Skipping trade.")
                return

            features = self.extract_features(price)
            confidence = self.model.predict_proba([features])[0][1]

            if confidence > 0.7 and self.current_position == 0:
                self.enter_trade(price, features)

            self.check_exit(price)

    def extract_features(self, price):
        bars = self.history_api.get_recent_bars(self.contract_id, lookback=30)
        prices = np.array([bar["price"] for bar in bars])
        volumes = np.array([bar["volume"] for bar in bars])

        return {
            "price_mean": prices.mean(),
            "price_std": prices.std(),
            "price_min": prices.min(),
            "price_max": prices.max(),
            "price_delta": float(prices[-1] - prices[0]),
            "price_slope": float((prices[-1] - prices[0]) / len(prices)),
            "volume_mean": volumes.mean(),
            "volume_sum": volumes.sum(),
            "volume_std": volumes.std(),
            "distance_to_poc": abs(price - self.levels.get("PDPOC", price)),
            "distance_to_val": abs(price - self.levels.get("PDVAL", price)),
            "distance_to_vah": abs(price - self.levels.get("PDVAH", price))
        }

    def enter_trade(self, price, features):
        tp = round(price + 10, 2)  # Static for now
        sl = round(price - 5, 2)
        lots = 1  # Can be dynamic based on confidence

        try:
            self.order_client.place_order(
                contract_id=self.contract_id,
                side="BUY",
                quantity=lots,
                entry_price=price,
                take_profit=tp,
                stop_loss=sl
            )
            self.last_entry_price = price
            self.current_position = lots
            logger.info(f"Entered long @ {price}, TP: {tp}, SL: {sl}")
        except Exception as e:
            logger.error(f"Order failed: {e}")

    def check_exit(self, price):
        if self.current_position == 0 or self.last_entry_price is None:
            return

        tp_hit = price >= self.last_entry_price + 10
        sl_hit = price <= self.last_entry_price - 5

        if tp_hit or sl_hit:
            pnl = (price - self.last_entry_price) * self.current_position
            self.daily_pnl += pnl
            logger.info(f"Exiting trade @ {price}, PnL: {pnl:.2f}, Daily PnL: {self.daily_pnl:.2f}")
            self.current_position = 0
            self.last_entry_price = None

    def is_market_open(self):
        now = datetime.utcnow()
        return now.weekday() < 5 and 13 <= now.hour <= 20  # 8am–3pm CT


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = CombineSafeBot(contract_id="MNQH2025", max_daily_loss=600, max_position_size=3)
    bot.market_client.start()
