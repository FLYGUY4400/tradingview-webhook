import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List, Set, Any
from dataclasses import dataclass

from topstepapi import TopstepClient
from topstepapi.order import OrderAPI
from topstepapi.load_env import load_environment

# Import AI components (we'll create these)
try:
    from ai.sentiment_analyzer import OpenAISentimentAnalyzer, SentimentAnalysis
    from ai.market_analyzer import MarketDataAnalyzer, SignalConfidence
    AI_ENABLED = True
    print("AI components loaded successfully")
except ImportError as e:
    print(f"AI components not available: {e}")
    print("Running in basic mode without AI enhancements")
    AI_ENABLED = False
    
    # Create dummy classes for backward compatibility
    @dataclass
    class SentimentAnalysis:
        sentiment_score: float = 0.0
        market_bias: str = "NEUTRAL"
        confidence: float = 0.5
        key_factors: List[str] = None
        risk_level: str = "MEDIUM"
        position_adjustment: float = 1.0
        
        def __post_init__(self):
            if self.key_factors is None:
                self.key_factors = []
    
    @dataclass
    class SignalConfidence:
        base_signal_strength: float = 0.7
        volume_confirmation: float = 0.5
        momentum_alignment: float = 0.5
        support_resistance: float = 0.5
        overall_confidence: float = 0.6
        recommended_position_multiplier: float = 1.0

# Configure enhanced logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / 'tvbot_enhanced.log'),
        logging.FileHandler(log_dir / 'ai_analysis.log')  # Separate AI analysis log
    ]
)
logger = logging.getLogger(__name__)

class EnhancedTVBot:
    """Enhanced TradingView Bot with AI Analysis"""
    
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
        
        # Initialize AI components if available
        self.ai_enabled = AI_ENABLED and os.getenv("OPENAI_API_KEY")
        if self.ai_enabled:
            try:
                self.sentiment_analyzer = OpenAISentimentAnalyzer()
                self.market_analyzer = MarketDataAnalyzer(self.client)
                logger.info("AI components initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize AI components: {e}")
                self.ai_enabled = False
        else:
            logger.warning("AI components disabled - running in basic mode")
        
        # File paths
        self.trades_file = Path("trades.json")
        self.processed_trades_file = Path("processed_trades.json")
        self.ai_analysis_file = Path("logs/ai_analysis.json")
        self.processed_trades: Set[str] = set()
        
        # Trading parameters
        self.account_id = None
        self.contract_id = "CON.F.US.MNQ.M25"
        self.base_position_size = 1
        self.max_position_multiplier = 3.0
        self.min_confidence_threshold = 0.4  # Minimum confidence to execute trade
        
        # AI enhancement settings
        self.ai_influence_factor = 0.8  # How much AI affects decisions (0.0 to 1.0)
        self.enable_dynamic_sizing = True
        self.enable_sentiment_filter = True
        self.enable_risk_adjustment = True
        
        # Track active orders and trades
        self.active_orders = {
            'tp': None,
            'sl': None,
            'entry': None
        }
        
        # Performance tracking
        self.trade_history = []
        self.ai_performance_stats = {
            'total_trades': 0,
            'ai_enhanced_trades': 0,
            'ai_boost_wins': 0,
            'ai_boost_losses': 0
        }
        
        # Initialize account
        self._initialize_account()
        
        # Load processed trades if file exists
        self._load_processed_trades()
        
        logger.info(f"Enhanced TradingView Bot initialized (AI: {'Enabled' if self.ai_enabled else 'Disabled'})")
    
    def _initialize_account(self):
        """Initialize trading account"""
        accounts = self.client.account.search_accounts(only_active=True)
        if not accounts:
            raise ValueError("No active trading accounts found")
        self.account_id = accounts[0]["id"]
        logger.info(f"Using account ID: {self.account_id}")
    
    def _load_processed_trades(self):
        """Load already processed trades from file"""
        if self.processed_trades_file.exists():
            try:
                with open(self.processed_trades_file, 'r') as f:
                    self.processed_trades = set(json.load(f))
                logger.info(f"Loaded {len(self.processed_trades)} processed trades")
            except Exception as e:
                logger.error(f"Error loading processed trades: {e}")
    
    def _save_processed_trades(self):
        """Save processed trades to file"""
        try:
            with open(self.processed_trades_file, 'w') as f:
                json.dump(list(self.processed_trades), f)
        except Exception as e:
            logger.error(f"Error saving processed trades: {e}")
    
    def _save_ai_analysis(self, trade_id: str, analysis_data: Dict):
        """Save AI analysis data for review"""
        if not self.ai_enabled:
            return
            
        try:
            # Load existing analyses
            analyses = {}
            if self.ai_analysis_file.exists():
                with open(self.ai_analysis_file, 'r') as f:
                    analyses = json.load(f)
            
            # Add new analysis
            analyses[trade_id] = {
                'timestamp': datetime.now().isoformat(),
                'analysis': analysis_data
            }
            
            # Save updated analyses
            with open(self.ai_analysis_file, 'w') as f:
                json.dump(analyses, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Error saving AI analysis: {e}")
    
    def analyze_signal_with_ai(self, trade_signal: dict) -> Dict[str, Any]:
        """Analyze TradingView signal with AI enhancement"""
        
        if not self.ai_enabled:
            # Return basic analysis without AI
            return {
                'ai_enabled': False,
                'confidence': SignalConfidence(),
                'sentiment': SentimentAnalysis(),
                'recommended_action': 'PROCEED',
                'position_multiplier': 1.0,
                'risk_adjustment': {
                    'tp_multiplier': 1.0,
                    'sl_multiplier': 1.0
                }
            }
        
        try:
            current_price = float(trade_signal['price'])
            
            # 1. Get market sentiment analysis
            sentiment = self.sentiment_analyzer.analyze_market_sentiment(
                current_price=current_price,
                price_change_24h=0.0,  # Could calculate from historical data
                volume_ratio=1.0,
                include_news=True
            )
            
            # 2. Get technical confidence analysis
            confidence = self.market_analyzer.analyze_signal_confidence(
                trade_signal, sentiment
            )
            
            # 3. Determine recommended action
            recommended_action = self._get_recommended_action(
                trade_signal, sentiment, confidence
            )
            
            # 4. Calculate position multiplier
            position_multiplier = self._calculate_position_multiplier(
                sentiment, confidence
            )
            
            # 5. Calculate risk adjustments
            risk_adjustment = self._calculate_risk_adjustments(
                sentiment, confidence
            )
            
            analysis = {
                'ai_enabled': True,
                'confidence': confidence,
                'sentiment': sentiment,
                'recommended_action': recommended_action,
                'position_multiplier': position_multiplier,
                'risk_adjustment': risk_adjustment,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            # Log AI analysis
            logger.info("=== AI SIGNAL ANALYSIS ===")
            logger.info(f"Signal: {trade_signal['action']} {trade_signal['symbol']} @ {current_price}")
            logger.info(f"Sentiment: {sentiment.market_bias} ({sentiment.sentiment_score:.2f})")
            logger.info(f"Confidence: {confidence.overall_confidence:.2f}")
            logger.info(f"Recommendation: {recommended_action}")
            logger.info(f"Position Multiplier: {position_multiplier:.2f}x")
            logger.info(f"Key Factors: {', '.join(sentiment.key_factors)}")
            logger.info("========================")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in AI signal analysis: {e}")
            # Return safe defaults on error
            return {
                'ai_enabled': False,
                'confidence': SignalConfidence(),
                'sentiment': SentimentAnalysis(),
                'recommended_action': 'PROCEED',
                'position_multiplier': 1.0,
                'risk_adjustment': {
                    'tp_multiplier': 1.0,
                    'sl_multiplier': 1.0
                }
            }
    
    def _get_recommended_action(self, signal: dict, sentiment: SentimentAnalysis, confidence: SignalConfidence) -> str:
        """Determine recommended action based on AI analysis"""
        
        signal_action = signal['action'].upper()
        
        # Check sentiment alignment
        sentiment_aligned = (
            (signal_action == "BUY" and sentiment.sentiment_score > -0.2) or
            (signal_action == "SELL" and sentiment.sentiment_score < 0.2)
        )
        
        # Check confidence thresholds
        high_confidence = confidence.overall_confidence > 0.7
        low_confidence = confidence.overall_confidence < self.min_confidence_threshold
        
        # Determine recommendation
        if low_confidence:
            return 'SKIP'
        elif not sentiment_aligned and sentiment.confidence > 0.7:
            return 'CAUTION'
        elif high_confidence and sentiment_aligned:
            return 'STRONG_PROCEED'
        else:
            return 'PROCEED'
    
    def _calculate_position_multiplier(self, sentiment: SentimentAnalysis, confidence: SignalConfidence) -> float:
        """Calculate position size multiplier based on AI analysis"""
        
        if not self.enable_dynamic_sizing:
            return 1.0
        
        # Base multiplier from confidence
        base_multiplier = confidence.recommended_position_multiplier
        
        # Adjust based on sentiment confidence
        sentiment_factor = 0.5 + (sentiment.confidence * 0.5)  # 0.5 to 1.0
        
        # Adjust based on risk level
        risk_factors = {
            'LOW': 1.2,
            'MEDIUM': 1.0,
            'HIGH': 0.7
        }
        risk_factor = risk_factors.get(sentiment.risk_level, 1.0)
        
        # Apply AI influence factor
        final_multiplier = 1.0 + (base_multiplier - 1.0) * self.ai_influence_factor
        final_multiplier *= sentiment_factor * risk_factor
        
        # Clamp to reasonable bounds
        return max(0.5, min(self.max_position_multiplier, final_multiplier))
    
    def _calculate_risk_adjustments(self, sentiment: SentimentAnalysis, confidence: SignalConfidence) -> Dict[str, float]:
        """Calculate TP/SL adjustments based on AI analysis"""
        
        if not self.enable_risk_adjustment:
            return {'tp_multiplier': 1.0, 'sl_multiplier': 1.0}
        
        # Adjust based on market risk level
        if sentiment.risk_level == "HIGH":
            tp_multiplier = 1.2  # Wider TP in volatile conditions
            sl_multiplier = 0.8  # Tighter SL
        elif sentiment.risk_level == "LOW":
            tp_multiplier = 0.9  # Closer TP in stable conditions
            sl_multiplier = 1.2  # Wider SL
        else:
            tp_multiplier = 1.0
            sl_multiplier = 1.0
        
        # Fine-tune based on confidence
        confidence_factor = confidence.overall_confidence
        tp_multiplier *= (0.8 + confidence_factor * 0.4)  # 0.8 to 1.2 range
        
        return {
            'tp_multiplier': tp_multiplier,
            'sl_multiplier': sl_multiplier
        }
    
    def process_new_trades(self):
        """Process new trades from trades.json with AI enhancement"""
        
        # Check for active trades first
        if self.has_active_trades():
            logger.info("Active trade found. Clearing trades.json and skipping new trades.")
            self.clear_trades_file()
            return
            
        trades = self.read_trades_file()
        if not trades:
            return
            
        for trade in trades[:]:  # Create a copy for safe iteration
            try:
                # Handle both old and new trade formats
                timestamp = trade.get('timestamp', trade.get('time', str(datetime.now().timestamp())))
                action = trade.get('action', '').upper()
                symbol = trade.get('symbol', '')
                price = trade.get('price', 0)
                quantity = float(trade.get('quantity', trade.get('qty', 1)))
                tp = trade.get('tp', 0)
                sl = trade.get('sl', 0)
                
                # Create unique trade ID
                trade_id = f"{symbol}_{action}_{price}_{timestamp}"
                
                # Skip if already processed
                if trade_id in self.processed_trades:
                    trades.remove(trade)
                    continue
                
                # Validate required fields
                required_fields = ['action', 'price', 'symbol', 'quantity', 'tp', 'sl']
                if not all(field in trade for field in required_fields):
                    logger.error(f"Invalid trade format: {trade}")
                    trades.remove(trade)
                    self._save_trades(trades)
                    continue
                
                logger.info(f"Processing trade: {trade_id}")
                
                # AI ENHANCEMENT: Analyze signal
                ai_analysis = self.analyze_signal_with_ai(trade)
                
                # Check AI recommendation
                if ai_analysis['recommended_action'] == 'SKIP':
                    logger.warning(f"AI recommends SKIP for trade {trade_id} - insufficient confidence")
                    trades.remove(trade)
                    self.processed_trades.add(trade_id)
                    self._save_processed_trades()
                    self._save_trades(trades)
                    continue
                
                if ai_analysis['recommended_action'] == 'CAUTION':
                    logger.warning(f"AI flags CAUTION for trade {trade_id} - sentiment misalignment")
                    # Reduce position size for cautionary trades
                    ai_analysis['position_multiplier'] *= 0.7
                
                # Execute enhanced trade
                success = self.place_enhanced_trade(
                    trade=trade,
                    ai_analysis=ai_analysis
                )
                
                if success:
                    # Mark as processed and remove from active trades
                    self.processed_trades.add(trade_id)
                    self._save_processed_trades()
                    trades.remove(trade)
                    self._save_trades(trades)
                    self._save_ai_analysis(trade_id, ai_analysis)
                    
                    # Update performance stats
                    self.ai_performance_stats['total_trades'] += 1
                    if ai_analysis['ai_enabled']:
                        self.ai_performance_stats['ai_enhanced_trades'] += 1
                    
                    logger.info(f"Successfully processed enhanced trade: {trade_id}")
                    break  # Only process one trade at a time
                    
            except Exception as e:
                logger.error(f"Error processing trade {trade}: {str(e)}")
                continue
    
    def place_enhanced_trade(self, trade: dict, ai_analysis: Dict[str, Any]) -> bool:
        """Place trade with AI enhancements"""
        
        try:
            side = trade['action'].upper()
            if side not in ["BUY", "SELL"]:
                raise ValueError("Side must be either 'BUY' or 'SELL'")
            
            # Calculate enhanced parameters
            base_quantity = int(trade.get('quantity', self.base_position_size))
            position_multiplier = ai_analysis['position_multiplier']
            enhanced_quantity = max(1, int(base_quantity * position_multiplier))
            
            # Calculate enhanced TP/SL
            entry_price = Decimal(str(trade['price']))
            base_tp = Decimal(str(trade['tp']))
            base_sl = Decimal(str(trade['sl']))
            
            risk_adj = ai_analysis['risk_adjustment']
            
            if side == "BUY":
                enhanced_tp = entry_price + ((base_tp - entry_price) * Decimal(str(risk_adj['tp_multiplier'])))
                enhanced_sl = entry_price - ((entry_price - base_sl) * Decimal(str(risk_adj['sl_multiplier'])))
            else:  # SELL
                enhanced_tp = entry_price - ((entry_price - base_tp) * Decimal(str(risk_adj['tp_multiplier'])))
                enhanced_sl = entry_price + ((base_sl - entry_price) * Decimal(str(risk_adj['sl_multiplier'])))
            
            # Round to appropriate precision
            enhanced_tp = enhanced_tp.quantize(Decimal('0.25'))
            enhanced_sl = enhanced_sl.quantize(Decimal('0.25'))
            
            # Place the enhanced trade
            success = self.place_trade(
                side=side,
                price=entry_price,
                qty=enhanced_quantity,
                tp=enhanced_tp,
                sl=enhanced_sl
            )
            
            if success:
                logger.info("=== ENHANCED TRADE EXECUTED ===")
                logger.info(f"Original: {side} {base_quantity} @ {entry_price}")
                logger.info(f"Enhanced: {side} {enhanced_quantity} @ {entry_price}")
                logger.info(f"AI Multiplier: {position_multiplier:.2f}x")
                logger.info(f"Original TP/SL: {base_tp}/{base_sl}")
                logger.info(f"Enhanced TP/SL: {enhanced_tp}/{enhanced_sl}")
                logger.info(f"Sentiment: {ai_analysis['sentiment'].market_bias}")
                logger.info(f"Confidence: {ai_analysis['confidence'].overall_confidence:.2f}")
                logger.info("==============================")
            
            return success
            
        except Exception as e:
            logger.error(f"Error placing enhanced trade: {e}")
            return False
    
    def place_trade(self, side: str, price: Decimal, qty: int, tp: Decimal, sl: Decimal) -> bool:
        """Place trade with TP/SL orders (enhanced from original)"""
        
        # Final check for active trades
        if self.has_active_trades():
            raise ValueError("Cannot place new trade: Another trade is already active")
        
        side_num = 0 if side == "BUY" else 1
        tp_sl_side = 1 if side == "BUY" else 0
        
        try:
            # Place entry order (Market order)
            entry_order = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=self.contract_id,
                type=2,  # Market order
                side=side_num,
                size=qty
            )
            
            if not entry_order:
                raise Exception("Failed to place entry order")
            
            self.active_orders['entry'] = entry_order
            logger.info(f"Entry order placed: {entry_order}")
            
            # Place TP order (Limit order)
            tp_order = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=self.contract_id,
                type=1,  # Limit order
                side=tp_sl_side,
                size=qty,
                linked_order_id=entry_order,
                limit_price=tp
            )
            
            # Place SL order (Stop order)
            sl_order = self.order_api.place_order(
                account_id=self.account_id,
                contract_id=self.contract_id,
                type=4,  # Stop order
                side=tp_sl_side,
                size=qty,
                linked_order_id=entry_order,
                stop_price=sl
            )
            
            # Update active orders
            self.active_orders.update({
                'tp': tp_order,
                'sl': sl_order
            })
            
            logger.info(f"TP order placed: {tp_order} at {tp}")
            logger.info(f"SL order placed: {sl_order} at {sl}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error placing trade: {e}")
            # Clean up any partially placed orders
            self._cleanup_failed_orders()
            return False
    
    def _cleanup_failed_orders(self):
        """Clean up orders if trade placement fails"""
        try:
            for order_type, order_id in self.active_orders.items():
                if order_id:
                    try:
                        self.order_api.cancel_order(self.account_id, order_id)
                        logger.info(f"Cleaned up {order_type} order: {order_id}")
                    except:
                        pass  # Order might already be cancelled or filled
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            self.active_orders = {'tp': None, 'sl': None, 'entry': None}
    
    # Keep existing methods from original tvBot.py
    def has_active_trades(self) -> bool:
        """Check if there are active trades"""
        return any(self.active_orders.values())
    
    def clear_trades_file(self):
        """Clear the trades.json file"""
        try:
            with open('trades.json', 'w') as f:
                json.dump([], f)
            logger.info("Cleared trades.json")
        except Exception as e:
            logger.error(f"Error clearing trades.json: {e}")
    
    def read_trades_file(self) -> List[dict]:
        """Read and parse trades from trades.json"""
        try:
            if not self.trades_file.exists():
                return []
            
            with open(self.trades_file, 'r') as f:
                trades = json.load(f)
            
            return trades if isinstance(trades, list) else []
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing trades.json: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading trades file: {e}")
            return []
    
    def _save_trades(self, trades):
        """Save trades to the trades.json file"""
        try:
            with open('trades.json', 'w') as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving trades: {str(e)}")
    
    def check_and_cancel_orders(self):
        """Check and cancel orders (from original tvBot.py)"""
        if not any(self.active_orders.values()):
            return
            
        try:
            open_orders = self.order_api.search_open_orders(self.account_id)
            open_order_ids = {str(o.get('id')) for o in open_orders}
            
            # Check TP order
            if self.active_orders['tp']:
                tp_id = str(self.active_orders['tp'])
                if tp_id not in open_order_ids:
                    logger.info(f"TP order {tp_id} filled")
                    if self.active_orders['sl']:
                        self.order_api.cancel_order(self.account_id, self.active_orders['sl'])
                        logger.info(f"Cancelled SL order {self.active_orders['sl']}")
                    self.active_orders = {'tp': None, 'sl': None, 'entry': None}
                    return
            
            # Check SL order
            if self.active_orders['sl']:
                sl_id = str(self.active_orders['sl'])
                if sl_id not in open_order_ids:
                    logger.info(f"SL order {sl_id} filled")
                    if self.active_orders['tp']:
                        self.order_api.cancel_order(self.account_id, self.active_orders['tp'])
                        logger.info(f"Cancelled TP order {self.active_orders['tp']}")
                    self.active_orders = {'tp': None, 'sl': None, 'entry': None}
                    return
                    
        except Exception as e:
            logger.error(f"Error checking orders: {e}")
            self.active_orders = {'tp': None, 'sl': None, 'entry': None}
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get enhanced performance statistics"""
        stats = {
            'basic_stats': self.ai_performance_stats.copy(),
            'ai_enabled': self.ai_enabled,
            'ai_influence_factor': self.ai_influence_factor,
            'settings': {
                'dynamic_sizing': self.enable_dynamic_sizing,
                'sentiment_filter': self.enable_sentiment_filter,
                'risk_adjustment': self.enable_risk_adjustment,
                'min_confidence': self.min_confidence_threshold
            }
        }
        
        if stats['basic_stats']['total_trades'] > 0:
            stats['ai_enhancement_rate'] = (
                stats['basic_stats']['ai_enhanced_trades'] / 
                stats['basic_stats']['total_trades']
            )
        
        return stats
    
    def run(self):
        """Main execution loop with enhanced logging"""
        logger.info("=" * 50)
        logger.info("ENHANCED TRADINGVIEW BOT STARTING")
        logger.info(f"AI Status: {'ENABLED' if self.ai_enabled else 'DISABLED'}")
        logger.info(f"Account: {self.account_id}")
        logger.info(f"Contract: {self.contract_id}")
        logger.info("=" * 50)
        
        try:
            while True:
                # Process new trades with AI enhancement
                self.process_new_trades()
                
                # Check and manage existing orders
                self.check_and_cancel_orders()
                
                # Wait before next check
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Shutting down Enhanced TradingView Bot...")
            logger.info(f"Final Stats: {self.get_performance_stats()}")
            self._save_processed_trades()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            self._save_processed_trades()
            raise

if __name__ == "__main__":
    bot = EnhancedTVBot()
    bot.run()