from signalrcore.hub_connection_builder import HubConnectionBuilder
import signal
import sys
import time

class MarketDataClient:
    def __init__(self, token: str, contract_id: str):
        base_url = "https://gateway-rtc-demo.s2f.projectx.com/hubs/"
        self.contract_id = contract_id
        self.hub_url = f"{base_url}market?access_token={token}"
        self.connection = HubConnectionBuilder()\
            .with_url(self.hub_url)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5
            })\
            .build()

    def start(self):
        self.connection.on_open(lambda: print("Connection opened"))
        self.connection.on_close(lambda: print("Connection closed"))
        self.connection.on_error(lambda error: print("Connection error:", error))

        self.connection.on("GatewayQuote", self.handle_quote)
        self.connection.on("GatewayTrade", self.handle_trade)
        self.connection.on("GatewayDepth", self.handle_depth)

        self.connection.start()
        self.subscribe_all()

    def stop(self):
        self.unsubscribe_all()
        self.connection.stop()

    def subscribe_all(self):
        print("Subscribing to market data...")
        self.connection.send("SubscribeContractQuotes", [self.contract_id])
        self.connection.send("SubscribeContractTrades", [self.contract_id])
        self.connection.send("SubscribeContractMarketDepth", [self.contract_id])

    def unsubscribe_all(self):
        print("Unsubscribing from market data...")
        self.connection.send("UnsubscribeContractQuotes", [self.contract_id])
        self.connection.send("UnsubscribeContractTrades", [self.contract_id])
        self.connection.send("UnsubscribeContractMarketDepth", [self.contract_id])

    def handle_quote(self, args):
        contract_id, data = args
        print("[QUOTE]", contract_id, data)

    def handle_trade(self, args):
        contract_id, data = args
        print("[TRADE]", contract_id, data)

    def handle_depth(self, args):
        contract_id, data = args
        print("[DEPTH]", contract_id, data)


# Replace these with your actual credentials and contract
JWT_TOKEN = "your_bearer_token"
CONTRACT_ID = "CON.F.US.RTY.H25"

client = MarketDataClient(JWT_TOKEN, CONTRACT_ID)

def signal_handler(sig, frame):
    print("\nShutting down...")
    client.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print("Starting market data stream...")
    client.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)