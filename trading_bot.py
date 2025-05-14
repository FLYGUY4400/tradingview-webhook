import os
import time
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List

from topstepapi import TopstepClient
from topstepapi.load_env import load_environment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        # Load environment variables
        load_environment()
        
        # Initialize Topstep client
        self.client = TopstepClient(
            username=os.getenv("TOPSTEPX_USERNAME"),
            api_key=os.getenv("TOPSTEPX_API_KEY")
        )
        
        # Trading parameters
        self.contract_id = "CON.F.US.MNQ.M25"  # Micro E-mini Nasdaq-100 Futures
        self.tp_points = 10  # Take profit in points
        self.sl_points = 5   # Stop loss in points
        self.position_size = 1  # Number of contracts
        
        # State management
        self.account_id: Optional[int] = None
        self.current_position = 0
        self.current_orders: Dict[str, dict] = {}
        self.last_price: Optional[Decimal] = None
        
    def setup(self):
        """Initialize trading setup"""
        # Get active trading account
        accounts = self.client.account.search_accounts(only_active=True)
        if not accounts:
            raise ValueError("No active trading accounts found")
        self.account_id = accounts[0]["id"]
        logger.info(f"Using account ID: {self.account_id}")
        
        # Using MNQ contract directly
        logger.info(f"Using contract: {self.contract_id}")
        
        # Check for existing positions
        positions = self.client.position.search_open_positions(self.account_id)
        for pos in positions:
            if pos["contractId"] == self.contract_id:
                self.current_position = pos["size"]
                logger.info(f"Found existing position: {self.current_position} contracts")
                
        # Cancel any existing orders
        open_orders = self.client.order.search_open_orders(self.account_id)
        for order in open_orders:
            if order["contractId"] == self.contract_id:
                self.client.order.cancel_order(self.account_id, order["id"])
                logger.info(f"Cancelled existing order: {order['id']}")

    def place_trade(self, side: str, entry_price: Decimal):
        """Place a trade with TP/SL orders"""
        if side not in ["buy", "sell"]:
            raise ValueError("Side must be 'buy' or 'sell'")
            
        # Calculate TP/SL prices
        if side == "buy":
            tp_price = entry_price + self.tp_points
            sl_price = entry_price - self.sl_points
        else:
            tp_price = entry_price - self.tp_points
            sl_price = entry_price + self.sl_points
            
        # Place entry order
        entry_order = self.client.order.place_market_order(
            account_id=self.account_id,
            contract_id=self.contract_id,
            side=side,
            quantity=self.position_size
        )
        logger.info(f"Placed {side} order: {entry_order['id']}")
        
        # Place TP order
        tp_order = self.client.order.place_limit_order(
            account_id=self.account_id,
            contract_id=self.contract_id,
            side="sell" if side == "buy" else "buy",
            quantity=self.position_size,
            price=tp_price
        )
        logger.info(f"Placed TP order at {tp_price}: {tp_order['id']}")
        
        # Place SL order
        sl_order = self.client.order.place_stop_order(
            account_id=self.account_id,
            contract_id=self.contract_id,
            side="sell" if side == "buy" else "buy",
            quantity=self.position_size,
            stop_price=sl_price
        )
        logger.info(f"Placed SL order at {sl_price}: {sl_order['id']}")
        
        # Track orders
        self.current_orders = {
            "entry": entry_order,
            "tp": tp_order,
            "sl": sl_order
        }

    def handle_quote(self, contract_id: str, data: dict):
        """Handle incoming market data quotes"""
        if contract_id != self.contract_id:
            return
            
        bid_price = Decimal(str(data.get("bidPrice", 0)))
        ask_price = Decimal(str(data.get("askPrice", 0)))
        self.last_price = (bid_price + ask_price) / 2
        
        # Implement your trading logic here
        # For example, simple moving average crossover, RSI, etc.
        # This is where you would call place_trade() when your conditions are met

    def run(self):
        """Main trading loop"""
        try:
            # Initial setup
            self.setup()
            
            # Connect to market data
            from tests.test_market_hub import MarketDataClient
            market_data = MarketDataClient(
                token=os.getenv("TOPSTEPX_SESSION_TOKEN"),
                contract_id=self.contract_id
            )
            
            # Register callbacks
            market_data.connection.on("GatewayQuote", self.handle_quote)
            
            # Start market data stream
            market_data.start()
            logger.info("Trading bot started")
            
            # Keep the main thread running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            if market_data:
                market_data.stop()
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            raise

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
