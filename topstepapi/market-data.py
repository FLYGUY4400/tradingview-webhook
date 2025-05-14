from signalrcore.hub_connection_builder import HubConnectionBuilder

class MarketDataClient:
    def __init__(self, token: str):
        base_url = "https://gateway-rtc-demo.s2f.projectx.com/hubs/"
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
        self.connection.start()

    def stop(self):
        self.connection.stop()

    def subscribe_quotes(self, contract_id: str):
        self.connection.send("SubscribeContractQuotes", [contract_id])

    def subscribe_trades(self, contract_id: str):
        self.connection.send("SubscribeContractTrades", [contract_id])

    def subscribe_depth(self, contract_id: str):
        self.connection.send("SubscribeContractMarketDepth", [contract_id])

    def unsubscribe_quotes(self, contract_id: str):
        self.connection.send("UnsubscribeContractQuotes", [contract_id])

    def unsubscribe_trades(self, contract_id: str):
        self.connection.send("UnsubscribeContractTrades", [contract_id])

    def unsubscribe_depth(self, contract_id: str):
        self.connection.send("UnsubscribeContractMarketDepth", [contract_id])

    def on_quote(self, handler):
        self.connection.on("GatewayQuote", handler)

    def on_trade(self, handler):
        self.connection.on("GatewayTrade", handler)

    def on_depth(self, handler):
        self.connection.on("GatewayDepth", handler)