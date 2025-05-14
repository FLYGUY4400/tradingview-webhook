from signalrcore.hub_connection_builder import HubConnectionBuilder
from urllib.parse import quote
import signal
import sys
import time
import os
import logging
from load_env import load_environment

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_environment()

# Get credentials from environment
JWT_TOKEN = os.getenv("TOPSTEPX_SESSION_TOKEN")

CONTRACT_ID = "CON.F.US.MNQ.M25"

class MarketDataClient:
    def __init__(self, token: str, contract_id: str):
        if not token:
            raise ValueError("Token cannot be empty")
            
        # Use wss:// for WebSocket connections
        base_url = "wss://rtc.topstepx.com/hubs/"
        self.contract_id = contract_id
        
        # URL encode the token to handle special characters
        encoded_token = quote(token)
        self.hub_url = f"{base_url}market?access_token={encoded_token}"
        
        self.connection = HubConnectionBuilder()\
            .with_url(self.hub_url)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
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