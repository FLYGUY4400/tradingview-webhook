from collections import deque
from decimal import Decimal

class RealTimeMACrossover:
    def __init__(self, client, trader, contract_id, fast_period=10, slow_period=30, position_size=1):
        self.client = client
        self.trader = trader
        self.contract_id = contract_id
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.position_size = position_size

        self.fast_ma_window = deque(maxlen=fast_period)
        self.slow_ma_window = deque(maxlen=slow_period)

        self.current_position = 0
        self.entry_price = None

    def on_price(self, price: Decimal):
        self.fast_ma_window.append(price)
        self.slow_ma_window.append(price)

        if len(self.fast_ma_window) < self.fast_period or len(self.slow_ma_window) < self.slow_period:
            return  # Not enough data yet

        fast_ma = sum(self.fast_ma_window) / Decimal(len(self.fast_ma_window))
        slow_ma = sum(self.slow_ma_window) / Decimal(len(self.slow_ma_window))

        if self.current_position == 0:
            if fast_ma > slow_ma:
                self.trader.place_trade("buy", price)
                self.current_position = self.position_size
                self.entry_price = price
            elif fast_ma < slow_ma:
                self.trader.place_trade("sell", price)
                self.current_position = -self.position_size
                self.entry_price = price

        elif self.current_position > 0 and fast_ma < slow_ma:
            # Exit long
            self.trader.place_trade("sell", price)
            self.current_position = 0
            self.entry_price = None

        elif self.current_position < 0 and fast_ma > slow_ma:
            # Exit short
            self.trader.place_trade("buy", price)
            self.current_position = 0
            self.entry_price = None
