import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, List, Set
from topstepapi import TopstepClient
from topstepapi.order import OrderAPI
from topstepapi.load_env import load_environment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TVBot:
    def __init__(self):
        load_environment()
        
        # Initialize Topstep client and order API
        self.client = TopstepClient(
            username=os.getenv("TOPSTEPX_USERNAME"),
            api_key=os.getenv("TOPSTEPX_API_KEY")
        )
        self.order_api = OrderAPI(
            token=os.getenv("TOPSTEPX_SESSION_TOKEN"),
            base_url=os.getenv("TOPSTEP_BASE_URL")
        )
        
        # File paths
        self.trades_file = Path("trades.json")
        self.processed_trades: Set[str] = set()
        
        # Trading parameters
        self.account_id = None
        self.contract_id = "CON.F.US.MNQ.M25"  # Default contract
        self.position_size = 1
        self.tp_percent = Decimal("0.0025")  # 0.25%
        self.sl_percent = Decimal("0.0025")  # 0.25%
        
        # Track active orders
        self.active_trades: Dict[str, Dict] = {}  # {trade_id: {entry_order_id, tp_order_id, sl_order_id, ...}}
        
        # Initialize account
        self._initialize_account()
        
        # Load processed trades if file exists
        self._load_processed_trades()
    
    def _load_processed_trades(self):
        """Load already processed trades from file"""
        if os.path.exists('processed_trades.json'):
            try:
                with open('processed_trades.json', 'r') as f:
                    self.processed_trades = set(json.load(f))
                logger.info(f"Loaded {len(self.processed_trades)} processed trades")
            except Exception as e:
                logger.error(f"Error loading processed trades: {e}")
    
    def _save_processed_trades(self):
        """Save processed trades to file"""
        try:
            with open('processed_trades.json', 'w') as f:
                json.dump(list(self.processed_trades), f)
        except Exception as e:
            logger.error(f"Error saving processed trades: {e}")
    
    def read_trades_file(self) -> List[dict]:
        """Read and parse trades from trades.json"""
        try:
            if not self.trades_file.exists():
                logger.warning(f"Trades file not found: {self.trades_file}")
                return []
                
            with open(self.trades_file, 'r') as f:
                trades = json.load(f)
                
            if not isinstance(trades, list):
                logger.error("Invalid trades format: expected a list")
                return []
                
            return trades
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing trades.json: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading trades file: {e}")
            return []
    
    def has_active_trades(self) -> bool:
        """Check if there are any active trades"""
        return any(trade["status"] == "OPEN" for trade in self.active_trades.values())

    def process_new_trades(self):
        """Process new trades from trades.json"""
        if self.has_active_trades():
            logger.info("Active trade found. Skipping new trades until current trade is closed.")
            return
            
        trades = self.read_trades_file()
        
        for trade in trades:
            try:
                # Handle both old and new trade formats
                timestamp = trade.get('timestamp', trade.get('time', str(datetime.now().timestamp())))
                action = trade.get('action', '').upper()
                symbol = trade.get('symbol', '')
                price = trade.get('price', 0)
                quantity = float(trade.get('qty', trade.get('quantity', 1)))
                
                # Create a unique ID for the trade
                trade_id = f"{symbol}_{action}_{price}_{timestamp}"
                
                # Skip if already processed
                if trade_id in self.processed_trades:
                    continue
                
                # Validate required fields
                required_fields = ['action', 'price', 'symbol', 'qty', 'tp', 'sl']
                if not all(field in trade for field in required_fields):
                    logger.error(f"Invalid trade format, missing required fields: {trade}")
                    continue
                
                # Check again for active trades right before placing (race condition protection)
                if self.has_active_trades():
                    logger.info("Active trade detected. Skipping new trade.")
                    continue
                
                logger.info(f"Processing new trade: {trade_id}")
                
                # Place the trade
                self.place_trade(
                    side=trade['action'],
                    price=Decimal(str(trade['price'])),
                    symbol=trade['symbol'],
                    qty=trade['qty'],
                    tp=trade['tp'],
                    sl=trade['sl']
                )
                
                # Mark as processed
                self.processed_trades.add(trade_id)
                self._save_processed_trades()
                logger.info(f"Successfully processed trade: {trade_id}")
                
                # Only process one trade at a time
                break
                
            except Exception as e:
                logger.error(f"Error processing trade {trade}: {e}", exc_info=True)

    def _initialize_account(self):
        """Initialize trading account"""
        accounts = self.client.account.search_accounts(only_active=True)
        if not accounts:
            raise ValueError("No active trading accounts found")
        self.account_id = accounts[0]["id"]
        logger.info(f"Initialized with account ID: {self.account_id}")

    def place_trade(self, side: str, price: Decimal, symbol: Optional[str] = None, qty: Optional[int] = None, tp: Optional[Decimal] = None, sl: Optional[Decimal] = None) -> Dict:
        """
        Place a new trade with TP/SL orders
        
        Args:
            side: 'BUY' or 'SELL'
            price: Entry price
            symbol: Trading symbol (defaults to self.contract_id)
            
        Returns:
            Dictionary with trade details
            
        Raises:
            ValueError: If side is invalid or trade placement fails
        """
        symbol = symbol or self.contract_id
        side = side.upper()
        
        if side not in ["BUY", "SELL"]:
            raise ValueError("Side must be either 'BUY' or 'SELL'")
            
        # Final check for active trades (defensive programming)
        if self.has_active_trades():
            raise ValueError("Cannot place new trade: Another trade is already active")
        
        # Convert to Decimal if they're not already
        tp_price = Decimal(str(tp)) if tp is not None else None
        sl_price = Decimal(str(sl)) if sl is not None else None 
        # Calculate TP/SL prices
        if side == "BUY":
            tp_side = "SELL"
            sl_side = "SELL"
        else:  # SELL
            tp_side = "BUY"
            sl_side = "BUY"

        # Place entry order (Market order)
        entry_order_id = self.order_api.place_order(
            account_id=self.account_id,
            contract_id=symbol,
            type=2,  # Market order
            side=0 if side == "BUY" else 1,  # 0=Buy, 1=Sell
            size=qty or self.position_size
        )
        
        # Place TP order (Limit order)
        tp_order_id = self.order_api.place_order(
            account_id=self.account_id,
            contract_id=symbol,
            type=1,  # Limit order
            side=0 if tp_side == "BUY" else 1,
            size=qty or self.position_size,
            linked_order_id=entry_order_id,
            limit_price=tp_price
        )
        
        # Place SL order (Stop order)
        sl_order_id = self.order_api.place_order(
            account_id=self.account_id,
            contract_id=symbol,
            type=4,  # Stop order
            side=0 if sl_side == "BUY" else 1,
            size=qty or self.position_size,
            linked_order_id=entry_order_id,
            stop_price=sl_price
        )
        
        # Store trade info
        trade_id = f"{symbol}_{int(time.time())}"
        self.active_trades[trade_id] = {
            "symbol": symbol,
            "side": side,
            "entry_price": price,
            "entry_order_id": entry_order_id,
            "tp_order_id": tp_order_id,
            "sl_order_id": sl_order_id,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "status": "OPEN"
        }
        
        logger.info(f"Placed {side} trade: {trade_id} @ {price}, TP: {tp_price}, SL: {sl_price}")
        return self.active_trades[trade_id]

    def check_and_cancel_orders(self):
        """Check if TP or SL was hit and cancel the other order"""
        for trade_id, trade in list(self.active_trades.items()):
            if trade["status"] != "OPEN":
                continue
                
            try:
                # Check TP order status
                tp_status = self._get_order_status(trade["tp_order_id"])
                sl_status = self._get_order_status(trade["sl_order_id"])
                
                if tp_status == "FILLED":
                    # TP was hit, cancel SL
                    self._cancel_order(trade["sl_order_id"])
                    trade["status"] = "TP_HIT"
                    logger.info(f"TP hit for trade {trade_id}")
                    
                elif sl_status == "FILLED":
                    # SL was hit, cancel TP
                    self._cancel_order(trade["tp_order_id"])
                    trade["status"] = "SL_HIT"
                    logger.info(f"SL hit for trade {trade_id}")
                    
                elif tp_status in ["CANCELLED", "REJECTED"] or sl_status in ["CANCELLED", "REJECTED"]:
                    # One of the orders was cancelled/rejected, clean up
                    self._cancel_order(trade["tp_order_id"])
                    self._cancel_order(trade["sl_order_id"])
                    trade["status"] = "ERROR"
                    logger.error(f"Order error for trade {trade_id}")
                    
            except Exception as e:
                logger.error(f"Error checking orders for trade {trade_id}: {e}")

    def _get_order_status(self, order_id: str) -> str:
        """Get order status by ID"""
        # This is a simplified version - adjust based on your OrderAPI implementation
        orders = self.order_api.search_orders(
            account_id=self.account_id,
            start_timestamp=(datetime.utcnow().isoformat() + "Z")
        )
        for order in orders:
            if order["id"] == order_id:
                return order["status"]
        return "UNKNOWN"

    def _cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID"""
        try:
            # Adjust based on your OrderAPI implementation
            self.order_api.cancel_order(
                account_id=self.account_id,
                order_id=order_id
            )
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    def run(self):
        """Main execution loop"""
        logger.info("Starting TVBot...")
        logger.info("Press Ctrl+C to exit")
        
        try:
            while True:
                # Process new trades from trades.json
                self.process_new_trades()
                
                # Check and manage existing orders
                self.check_and_cancel_orders()
                
                # Wait before next check
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            logger.info("Shutting down TVBot...")
            # Save processed trades before exiting
            self._save_processed_trades()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            self._save_processed_trades()
            raise  # Re-raise to see full traceback in logs

if __name__ == "__main__":
    bot = TVBot()
    bot.run()