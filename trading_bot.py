import os
import time
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List
import uuid 
import json

from topstepapi import TopstepClient
from topstepapi.load_env import load_environment
from topstepapi.order import OrderAPI

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
        self.order_api = OrderAPI(token=os.getenv("TOPSTEPX_SESSION_TOKEN"), base_url=os.getenv("TOPSTEP_BASE_URL"))
        # Trading parameters
        self.contract_id = "CON.F.US.MNQ.M25"  # Micro E-mini Nasdaq-100 Futures
        self.tp_points = Decimal("25")  # Take profit $50 / $2 per point
        self.sl_points = Decimal("12.5")   # Stop loss $25 / $2 per point
        self.position_size = 1  # Number of contracts
        
        # State management
        self.account_id: Optional[int] = None
        self.current_position = 0
        self.current_orders: Dict[str, dict] = {}
        self.latest_trade_price: Optional[Decimal] = None
        self.trade_placed_this_session: bool = False
        
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
            side_num = 0
        else:
            tp_price = entry_price - self.tp_points
            sl_price = entry_price + self.sl_points
            side_num = 1
      
        # Place entry order
        entry_order =self.order_api.place_order(
            account_id=self.account_id,
            contract_id=self.contract_id,
            type=2,
            side=side_num,
            size=self.position_size          
            
        )
        logger.info(f"Placed {side} for account {self.account_id} with order id {entry_order}")
        
        # Track orders
        self.current_orders = {
            "entry": entry_order,
            "tp": tp_order,
            "sl": sl_order
        }



    def run(self):
        """Main trading loop"""
        try:
            # Initial setup
            self.setup()
            
            # Connect to market data
            from topstepapi.market_data import MarketDataClient
            market_data = MarketDataClient(
                token=os.getenv("TOPSTEPX_SESSION_TOKEN"),
                contract_id=self.contract_id,
                on_trade_callback=self._handle_market_trade # Register our new trade handler
            )
            
            # Register callbacks
            # self.handle_quote is removed, using trade updates instead
            # market_data.connection.on("GatewayQuote", self.handle_quote)
            
            # Start market data stream
            market_data.start()
            logger.info("Trading bot started")
            
            # Keep the main thread running
            # The trade placement logic is now event-driven by _handle_market_trade
            while True:
                if self.trade_placed_this_session:
                    logger.info("Trade placed and bot is now idle. Monitoring position (manual). Press Ctrl+C to exit.")
                    # Bot will just idle here until manually stopped or further logic is added for position management
                    # For a real bot, you'd monitor self.current_orders, position status, etc.
                    while True:
                        time.sleep(60) # Sleep longer once trade is placed
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            if market_data:
                market_data.stop()
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            raise


    def _handle_market_trade(self, args: List):
        """Handle incoming trade data from MarketDataClient callback."""
        try:
            contract_id_from_stream, trade_data_list = args
            if contract_id_from_stream != self.contract_id or not trade_data_list:
                return

            # Assuming trade_data_list is a list of trades, get the last one
            # And that each trade is a dict with a 'price' key
            last_trade = trade_data_list[-1]
            if isinstance(last_trade, dict) and 'price' in last_trade:
                self.latest_trade_price = Decimal(str(last_trade['price']))
                logger.info(f"Latest MNQ trade price updated: {self.latest_trade_price}")

                # Attempt to place the trade if price is available and not already placed
                if self.latest_trade_price is not None and not self.trade_placed_this_session:
                    self._attempt_place_long_market_order()
            else:
                logger.warning(f"Received trade data in unexpected format: {last_trade}")

        except Exception as e:
            logger.error(f"Error in _handle_market_trade: {e}", exc_info=True)

    def _attempt_place_long_market_order(self):
        """Attempts to place a long market order with TP/SL if conditions are met."""
        if self.trade_placed_this_session:
            logger.info("Trade already attempted/placed this session.")
            return

        if self.account_id is None:
            logger.error("Account ID not set. Cannot place trade.")
            return

        if self.latest_trade_price is None:
            logger.warning("Latest market price not available. Cannot calculate TP/SL or place trade.")
            return

        logger.info(f"Attempting to place LONG market order for {self.contract_id} at observed price ~{self.latest_trade_price}")
        try:
            # Call the existing place_trade method which handles market entry and TP/SL placement
            self.place_trade(side="buy", entry_price=self.latest_trade_price) # entry_price here is for TP/SL calc
            self.trade_placed_this_session = True # Mark as placed to prevent re-triggering
            logger.info("Long market order with TP/SL successfully initiated.")
        except Exception as e:
            logger.error(f"Error placing long market order with TP/SL: {e}", exc_info=True)
            # Optionally, you might want to retry or handle this error more gracefully
            # For now, we'll still mark as attempted to avoid spamming orders if it's a persistent issue.
            self.trade_placed_this_session = True 

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
