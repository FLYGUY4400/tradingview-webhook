import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List, Set, Any
from topstepapi import TopstepClient
from topstepapi.order import OrderAPI
from topstepapi.load_env import load_environment

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see all messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('tvbot_debug.log')
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure logger captures all levels

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
        
        # Track active orders and trades
        self.active_trades: Dict[str, Dict] = {}  # {trade_id: {entry_order_id, tp_order_id, sl_order_id, ...}}
        self.active_orders = {
            'tp': None,  # TP order ID
            'sl': None,  # SL order ID
            'entry': None  # Entry order ID
        }
        
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
        with open('processed_trades.json', 'w') as f:
            json.dump(list(self.processed_trades), f)
            
    def cancel_other_order(self, filled_order_id):
        """Cancel the other order when one is filled"""
        if not self.active_orders:
            return
            
        try:
            # Determine which order was filled and cancel the other one
            if filled_order_id == self.active_orders.get('tp'):
                other_order_id = self.active_orders.get('sl')
                order_type = 'SL'
            elif filled_order_id == self.active_orders.get('sl'):
                other_order_id = self.active_orders.get('tp')
                order_type = 'TP'
            else:
                return
                
            if other_order_id:
                try:
                    self.order_api.cancel_order(
                        account_id=self.account_id,
                        order_id=other_order_id
                    )
                    logger.info(f"Cancelled {order_type} order: {other_order_id}")
                except Exception as e:
                    logger.error(f"Error cancelling {order_type} order {other_order_id}: {e}")
            
            # Clear active orders
            self.active_orders = {}
            
        except Exception as e:
            logger.error(f"Error in cancel_other_order: {e}")
            # Clear active orders even if there was an error
            self.active_orders = {}
    
    def _save_trades(self, trades):
        """Save trades to the trades.json file"""
        try:
            with open('trades.json', 'w') as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving trades: {str(e)}")
    
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

    def clear_trades_file(self):
        """Clear the trades.json file"""
        try:
            with open('trades.json', 'w') as f:
                json.dump([], f)
            logger.info("Cleared trades.json")
        except Exception as e:
            logger.error(f"Error clearing trades.json: {e}")
            
    def process_new_trades(self):
        """Process new trades from trades.json"""
        if self.has_active_trades():
            logger.info("Active trade found. Clearing trades.json and skipping new trades until current trade is closed.")
            self.clear_trades_file()
            return
            
        trades = self.read_trades_file()
        if not trades:
            return
            
        for trade in trades[:]:  # Create a copy of the list for safe iteration
            try:
                # Handle both old and new trade formats
                timestamp = trade.get('timestamp', trade.get('time', str(datetime.now().timestamp())))
                action = trade.get('action', '').upper()
                symbol = trade.get('symbol', '')
                price = trade.get('price', 0)
                quantity = float(trade.get('quantity', trade.get('qty', 1)))
                
                # Create a unique ID for the trade
                trade_id = f"{symbol}_{action}_{price}_{timestamp}"
                
                # Skip if already processed
                if trade_id in self.processed_trades:
                    trades.remove(trade)  # Remove already processed trade
                    continue
                
                # Validate required fields
                required_fields = ['action', 'price', 'symbol', 'quantity', 'tp', 'sl']
                if not all(field in trade for field in required_fields):
                    logger.error(f"Invalid trade format, missing required fields: {trade}")
                    trades.remove(trade)  # Remove invalid trade
                    self._save_trades(trades)
                    continue
                
                logger.info(f"Processing new trade: {trade_id}")
                
                # Place the trade
                self.place_trade(
                    side=trade['action'],
                    price=Decimal(str(trade['price'])),
                    qty=trade['quantity'],
                    tp=trade['tp'],
                    sl=trade['sl']
                )
                
                # Mark as processed and remove from active trades
                self.processed_trades.add(trade_id)
                self._save_processed_trades()
                trades.remove(trade)  # Remove processed trade
                self._save_trades(trades)  # Save updated trades list
                logger.info(f"Successfully processed and removed trade: {trade_id}")
                
                # Only process one trade at a time
                break
                
            except Exception as e:
                logger.error(f"Error processing trade {trade}: {str(e)}")
                continue
                
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

        try:
            # Place entry order (Market order)
            entry_order = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=symbol,
                type=2,  # Market order
                side=0 if side == "BUY" else 1,  # 0=Buy, 1=Sell
                size=int(qty or self.position_size)
            )
            self.active_orders['entry'] = entry_order
            logger.info(f"Placed entry order: {entry_order}")
            
            # Place TP order (Limit order)
            tp_order = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=symbol,
                type=1,  # Limit order
                side=0 if tp_side == "BUY" else 1,
                size=int(qty or self.position_size),
                linked_order_id=entry_order,
                limit_price=tp_price
            )
            self.active_orders['tp'] = tp_order
            logger.info(f"Placed TP order: {tp_order} at {tp_price}")
            
            # Place SL order (Stop order)
            sl_order = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=symbol,
                type=4,  # Stop order
                side=0 if sl_side == "BUY" else 1,
                size=int(qty or self.position_size),
                linked_order_id=entry_order,
                stop_price=sl_price
            )
            self.active_orders['sl'] = sl_order
            logger.info(f"Placed SL order: {sl_order} at {sl_price}")
            
            # Update main order with TP/SL order IDs (if supported by API)
            #try:
                #self.order_api.modify_order(
                 #   account_id=self.account_id,
                  #  order_id=entry_order,
                  #  take_profit_order_id=tp_order,
                #    stop_loss_order_id=sl_order
              #  )
           # except Exception as e:
             #   logger.warning(f"Could not link TP/SL orders to main order (this might be expected): {e}")
            
            # Track both orders to manage them together
            logger.info(f"Tracking orders - TP: {tp_order}, SL: {sl_order}")
            if tp_order and sl_order:
                self.active_orders = {
                    'tp': tp_order,
                    'sl': sl_order
                }
                logger.info(f"Tracking orders - TP: {tp_order}, SL: {sl_order}")
            else:
                logger.warning("Failed to track one or both orders")
                
        except Exception as e:
            logger.error(f"Error in place_trade: {str(e)}")
            raise
        
        # Store trade info
        trade_id = f"{symbol}_{int(time.time())}"
        self.active_trades[trade_id] = {
            "symbol": symbol,
            "side": side,
            "entry_price": price,
            "entry_order_id": entry_order,
            "tp_order_id": tp_order if 'tp_order' in locals() else None,
            "sl_order_id": sl_order if 'sl_order' in locals() else None,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "status": "OPEN"
        }
        
        logger.info(f"Placed {side} trade: {trade_id} @ {price}, TP: {tp_price}, SL: {sl_price}")
        return self.active_trades[trade_id]

    def check_and_cancel_orders(self):
        """
        Check if either TP or SL order is no longer in open orders,
        which would indicate it was filled, then cancel the other order.
        """
        if not any(self.active_orders.values()):
            return
            
        try:
            # Get all currently open orders
            open_orders = self.order_api.search_open_orders(
                account_id=self.account_id
            )
            
            logger.debug(f"Found {len(open_orders)} open orders")
            open_order_ids = {str(o.get('id')) for o in open_orders}
            logger.debug(f"Open order IDs: {open_order_ids}")
            
            # Check TP order
            if self.active_orders['tp']:
                tp_id = str(self.active_orders['tp'])
                logger.info(f"Checking TP order {tp_id}")
                
                if tp_id not in open_order_ids:
                    logger.info(f"TP order {tp_id} is no longer open (likely filled)")
                    # Cancel SL order if TP was hit
                    if self.active_orders['sl']:
                        logger.info(f"Attempting to cancel SL order {self.active_orders['sl']}")
                        try:
                            self.order_api.cancel_order(
                                account_id=self.account_id,
                                order_id=self.active_orders['sl']
                            )
                            logger.info(f"Cancelled SL order {self.active_orders['sl']} after TP was hit")
                        except Exception as e:
                            logger.error(f"Error cancelling SL order: {e}")
                    # Clear all orders
                    self.active_orders = {'tp': None, 'sl': None, 'entry': None}
                    return
            
            # Check SL order
            if self.active_orders['sl']:
                sl_id = str(self.active_orders['sl'])
                logger.info(f"Checking SL order {sl_id}")
                
                if sl_id not in open_order_ids:
                    logger.info(f"SL order {sl_id} is no longer open (likely filled)")
                    # Cancel TP order if SL was hit
                    if self.active_orders['tp']:
                        logger.info(f"Attempting to cancel TP order {self.active_orders['tp']}")
                        try:
                            self.order_api.cancel_order(
                                account_id=self.account_id,
                                order_id=self.active_orders['tp']
                            )
                            logger.info(f"Cancelled TP order {self.active_orders['tp']} after SL was hit")
                        except Exception as e:
                            logger.error(f"Error cancelling TP order: {e}")
                    # Clear all orders
                    self.active_orders = {'tp': None, 'sl': None, 'entry': None}
                    return
                    
        except Exception as e:
            logger.error(f"Error in check_and_cancel_orders: {e}", exc_info=True)
            # If there's an error, try to clean up orders to prevent stuck state
            self.active_orders = {'tp': None, 'sl': None, 'entry': None}

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