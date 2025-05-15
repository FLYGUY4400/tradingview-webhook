from utils.email import send_email



class MicroScalper:
    def __init__(self, client, trader, contract_id):
        self.client = client
        self.trader = trader
        self.contract_id = contract_id
        self.last_prices = []
        self.window_size = 5  # Number of ticks to observe
        self.threshold = 1.0  # Tick movement to trigger trades
        self.position = None  # Track position state

    def start(self):
        self.client.on_trade(self.handle_trade)
        self.client.subscribe_trades(self.contract_id)

    def stop(self):
        self.client.unsubscribe_trades(self.contract_id)

    def handle_trade(self, args):
        contract_id, trade_data = args
        price = trade_data['price']
        self.last_prices.append(price)

        if len(self.last_prices) > self.window_size:
            self.last_prices.pop(0)
            self.check_signal()

    def check_signal(self):
        if self.position:
            return  # Already in trade

        delta = self.last_prices[-1] - self.last_prices[0]
        if delta > self.threshold:
            self.place_order("SELL")
        elif delta < -self.threshold:
            self.place_order("BUY")

    def place_order(self, side):
        print(f"Placing {side} order at {self.last_prices[-1]}")
        self.trader.place_market_order(contract_id=self.contract_id, side=side, quantity=1)
        self.position = side

        # Email summary
        subject = f"Trade Placed: {side}"
        body = (
            f"Entry: {self.last_prices[-1]} at {datetime.now().strftime('%H:%M:%S')}\n"
        )
        send_email(subject, body)


    def close_position(self):
        if self.position:
            opposite = "SELL" if self.position == "BUY" else "BUY"
            self.trader.place_market_order(contract_id=self.contract_id, side=opposite, quantity=1)
            self.position = None
        # Email summary
        subject = f"Trade Closed: {self.position} | PnL: {pnl:.2f}"
        body = (
            f"Entry: {self.entry_price} at {self.entry_time.strftime('%H:%M:%S')}\n"
            f"Exit: {price} at {datetime.now().strftime('%H:%M:%S')}\n"
            f"PnL: {pnl:.2f}"
        )
        send_email(subject, body)

