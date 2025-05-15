from signalrcore.hub_connection_builder import HubConnectionBuilder
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logger.addHandler(logging.NullHandler()) # Add a null handler to prevent "No handlers found" warnings if not configured by consumer

class MarketDataClient:
    def __init__(self, token: str, contract_id: str, on_quote_callback=None, on_trade_callback=None, on_depth_callback=None):
        if not token:
            raise ValueError("Token cannot be empty")
            
        # Use wss:// for WebSocket connections
        base_url = "wss://rtc.topstepx.com/hubs/"
        self.contract_id = contract_id
        
        # URL encode the token to handle special characters
        encoded_token = quote(token)
        self.hub_url = f"{base_url}market?access_token={encoded_token}"
        
        self.on_quote_callback = on_quote_callback
        self.on_trade_callback = on_trade_callback
        self.on_depth_callback = on_depth_callback

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
        self.connection.on_open(lambda: logger.info(f"MarketDataClient: Connection opened for {self.contract_id}"))
        self.connection.on_close(lambda: logger.warning(f"MarketDataClient: Connection closed for {self.contract_id}"))
        self.connection.on_error(lambda error: logger.error(f"MarketDataClient: Connection error for {self.contract_id}: {error}"))

        self.connection.on("GatewayQuote", self.handle_quote)
        self.connection.on("GatewayTrade", self.handle_trade)
        self.connection.on("GatewayDepth", self.handle_depth)

        self.connection.start()
        self.subscribe_all()

    def stop(self):
        self.unsubscribe_all()
        self.connection.stop()

    def subscribe_all(self):
        logger.info(f"MarketDataClient: Subscribing to market data for {self.contract_id}...")
        self.connection.send("SubscribeContractQuotes", [self.contract_id])
        self.connection.send("SubscribeContractTrades", [self.contract_id])
        self.connection.send("SubscribeContractMarketDepth", [self.contract_id])

    def unsubscribe_all(self):
        logger.info(f"MarketDataClient: Unsubscribing from market data for {self.contract_id}...")
        self.connection.send("UnsubscribeContractQuotes", [self.contract_id])
        self.connection.send("UnsubscribeContractTrades", [self.contract_id])
        self.connection.send("UnsubscribeContractMarketDepth", [self.contract_id])

    def handle_quote(self, args):
        # contract_id, data = args # args is already a list/tuple
        if self.on_quote_callback:
            try:
                self.on_quote_callback(args)
            except Exception as e:
                logger.error(f"MarketDataClient: Error in on_quote_callback: {e}", exc_info=True)

    def handle_trade(self, args):
        # contract_id, data = args # args is already a list/tuple
        if self.on_trade_callback:
            try:
                self.on_trade_callback(args)
            except Exception as e:
                logger.error(f"MarketDataClient: Error in on_trade_callback: {e}", exc_info=True)

    def handle_depth(self, args):
        # contract_id, data = args # args is already a list/tuple
        if self.on_depth_callback:
            try:
                self.on_depth_callback(args)
            except Exception as e:
                logger.error(f"MarketDataClient: Error in on_depth_callback: {e}", exc_info=True)

    
