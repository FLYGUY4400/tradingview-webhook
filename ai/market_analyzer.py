import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np
import pandas as pd

from topstepapi import TopstepClient
from .sentiment_analyzer import SentimentAnalysis

logger = logging.getLogger(__name__)

@dataclass
class SignalConfidence:
    """Data class to hold signal confidence scores"""
    base_signal_strength: float = 0.0
    volume_confirmation: float = 0.0
    momentum_alignment: float = 0.0
    support_resistance: float = 0.0
    overall_confidence: float = 0.0
    recommended_position_multiplier: float = 1.0

class MarketDataAnalyzer:
    """Analyzes market data to generate confidence scores"""
    
    def __init__(self, client: TopstepClient):
        self.client = client
        self.contract_id = "CON.F.US.MNQ.M25"
        
    def get_recent_bars(self, lookback_minutes: int = 60) -> List[dict]:
        """Get recent price bars for analysis"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=lookback_minutes)
            
            bars = self.client.history.retrieve_bars(
                contract_id=self.contract_id,
                live=True,
                start_time=start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                unit=1,  # 1 minute bars
                unit_number=1,
                limit=lookback_minutes,
                include_partial_bar=True
            )
            return bars or []
        except Exception as e:
            logger.error(f"Error fetching bars: {e}")
            return []
    
    def analyze_signal_confidence(self, trade_signal: dict, sentiment: SentimentAnalysis) -> SignalConfidence:
        """Analyze signal with technical indicators to generate confidence scores"""
        try:
            current_price = float(trade_signal['price'])
            
            # Get recent market data
            bars = self.get_recent_bars(60)
            
            # Calculate individual confidence scores
            volume_score = self.calculate_volume_profile_score(bars, current_price)
            momentum_score = self.calculate_momentum_score(bars)
            sr_score = self.calculate_support_resistance_score(bars, current_price)
            
            # Base signal strength (from TradingView)
            base_strength = 0.7  # Assume TradingView signals are decent quality
            
            # Calculate overall confidence (weighted average)
            weights = {
                'base': 0.3,
                'volume': 0.25,
                'momentum': 0.25,
                'sr': 0.2
            }
            
            overall = (
                base_strength * weights['base'] +
                volume_score * weights['volume'] +
                momentum_score * weights['momentum'] +
                sr_score * weights['sr']
            )
            
            # Adjust based on sentiment alignment
            signal_action = trade_signal.get('action', '').upper()
            sentiment_boost = self._calculate_sentiment_boost(signal_action, sentiment)
            overall += sentiment_boost
            
            # Calculate position multiplier based on confidence
            multiplier = self._calculate_position_multiplier(overall, sentiment)
            
            confidence = SignalConfidence(
                base_signal_strength=base_strength,
                volume_confirmation=volume_score,
                momentum_alignment=momentum_score,
                support_resistance=sr_score,
                overall_confidence=min(1.0, max(0.0, overall)),
                recommended_position_multiplier=multiplier
            )
            
            logger.debug(f"Signal confidence analysis: {confidence}")
            return confidence
            
        except Exception as e:
            logger.error(f"Error analyzing signal confidence: {e}")
            return SignalConfidence()  # Return default values
    
    def calculate_volume_profile_score(self, bars: List[dict], current_price: float) -> float:
        """Calculate volume profile confidence score"""
        if not bars:
            return 0.5
            
        try:
            # Create price-volume distribution
            prices = [float(bar.get('c', 0)) for bar in bars if bar.get('c')]
            volumes = [int(bar.get('v', 0)) for bar in bars if bar.get('v')]
            
            if len(prices) < 5 or len(volumes) < 5:
                return 0.5
                
            # Calculate VWAP
            vwap = np.average(prices, weights=volumes)
            
            # Calculate volume at different price levels
            price_range = max(prices) - min(prices)
            if price_range == 0:
                return 0.5
                
            price_levels = np.linspace(min(prices), max(prices), 10)
            volume_profile = []
            
            for level in price_levels:
                volume_at_level = sum(v for p, v in zip(prices, volumes) 
                                    if abs(p - level) < price_range / 20)
                volume_profile.append(volume_at_level)
            
            # Find POC (Point of Control - highest volume)
            if not volume_profile:
                return 0.5
                
            max_volume_idx = np.argmax(volume_profile)
            poc_price = price_levels[max_volume_idx]
            
            # Score based on proximity to POC and VWAP
            vwap_distance = abs(current_price - vwap) / vwap if vwap > 0 else 1.0
            poc_distance = abs(current_price - poc_price) / poc_price if poc_price > 0 else 1.0
            
            # Higher score if closer to key levels
            score = max(0, 1 - (vwap_distance + poc_distance))
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Error calculating volume profile score: {e}")
            return 0.5
    
    def calculate_momentum_score(self, bars: List[dict]) -> float:
        """Calculate momentum alignment score"""
        if len(bars) < 20:
            return 0.5
            
        try:
            closes = [float(bar.get('c', 0)) for bar in bars if bar.get('c')]
            
            if len(closes) < 20:
                return 0.5
            
            # Calculate EMAs
            ema_9 = self._calculate_ema(closes, 9)
            ema_21 = self._calculate_ema(closes, 21)
            
            # Calculate RSI
            rsi = self._calculate_rsi(closes, 14)
            
            # Momentum alignment score
            ema_alignment = 1.0 if len(ema_9) > 0 and len(ema_21) > 0 and ema_9[-1] > ema_21[-1] else 0.0
            rsi_momentum = abs((rsi - 50) / 50) if 0 <= rsi <= 100 else 0.0  # 0 to 1 scale
            
            score = (ema_alignment + rsi_momentum) / 2
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Error calculating momentum score: {e}")
            return 0.5
    
    def calculate_support_resistance_score(self, bars: List[dict], current_price: float) -> float:
        """Calculate support/resistance proximity score"""
        if len(bars) < 10:
            return 0.5
            
        try:
            highs = [float(bar.get('h', 0)) for bar in bars if bar.get('h')]
            lows = [float(bar.get('l', 0)) for bar in bars if bar.get('l')]
            
            if len(highs) < 10 or len(lows) < 10:
                return 0.5
            
            # Find recent swing highs and lows
            resistance_levels = self._find_swing_highs(highs)
            support_levels = self._find_swing_lows(lows)
            
            # Calculate proximity to key levels
            all_levels = resistance_levels + support_levels
            if not all_levels:
                return 0.5
                
            min_distance = min(abs(current_price - level) / current_price for level in all_levels if level > 0)
            
            # Higher score if closer to key levels (good for breakout/bounce)
            score = 1 - min(min_distance * 10, 1.0)  # Scale distance
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Error calculating S/R score: {e}")
            return 0.5
    
    def _calculate_sentiment_boost(self, signal_action: str, sentiment: SentimentAnalysis) -> float:
        """Calculate sentiment alignment boost"""
        try:
            # Check if signal aligns with sentiment
            if signal_action == "BUY" and sentiment.sentiment_score > 0.2:
                return 0.1 * sentiment.confidence
            elif signal_action == "SELL" and sentiment.sentiment_score < -0.2:
                return 0.1 * sentiment.confidence
            elif abs(sentiment.sentiment_score) < 0.2:  # Neutral sentiment
                return 0.0
            else:  # Signal conflicts with sentiment
                return -0.05 * sentiment.confidence
                
        except Exception as e:
            logger.error(f"Error calculating sentiment boost: {e}")
            return 0.0
    
    def _calculate_position_multiplier(self, confidence: float, sentiment: SentimentAnalysis) -> float:
        """Calculate position multiplier based on confidence and sentiment"""
        try:
            # Base multiplier from confidence
            if confidence > 0.8:
                base_multiplier = 2.0
            elif confidence > 0.6:
                base_multiplier = 1.5
            elif confidence > 0.4:
                base_multiplier = 1.0
            else:
                base_multiplier = 0.5
            
            # Adjust based on sentiment confidence
            sentiment_factor = 0.5 + (sentiment.confidence * 0.5)  # 0.5 to 1.0
            
            # Adjust based on risk level
            risk_factors = {
                'LOW': 1.2,
                'MEDIUM': 1.0,
                'HIGH': 0.7
            }
            risk_factor = risk_factors.get(sentiment.risk_level, 1.0)
            
            final_multiplier = base_multiplier * sentiment_factor * risk_factor
            
            # Apply sentiment position adjustment
            final_multiplier *= sentiment.position_adjustment
            
            # Clamp to reasonable bounds
            return max(0.5, min(3.0, final_multiplier))
            
        except Exception as e:
            logger.error(f"Error calculating position multiplier: {e}")
            return 1.0
    
    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return []
            
        ema = [prices[0]]
        multiplier = 2 / (period + 1)
        
        for price in prices[1:]:
            ema.append((price * multiplier) + (ema[-1] * (1 - multiplier)))
        
        return ema
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
            
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [max(0, delta) for delta in deltas]
        losses = [abs(min(0, delta)) for delta in deltas]
        
        if len(gains) < period or len(losses) < period:
            return 50
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _find_swing_highs(self, highs: List[float], window: int = 3) -> List[float]:
        """Find swing high levels"""
        if len(highs) < window * 2 + 1:
            return []
            
        swing_highs = []
        for i in range(window, len(highs) - window):
            if all(highs[i] >= highs[j] for j in range(i-window, i+window+1) if j != i):
                swing_highs.append(highs[i])
        return swing_highs
    
    def _find_swing_lows(self, lows: List[float], window: int = 3) -> List[float]:
        """Find swing low levels"""
        if len(lows) < window * 2 + 1:
            return []
            
        swing_lows = []
        for i in range(window, len(lows) - window):
            if all(lows[i] <= lows[j] for j in range(i-window, i+window+1) if j != i):
                swing_lows.append(lows[i])
        return swing_lows

if __name__ == "__main__":
    # Test the market analyzer
    from topstepapi.load_env import load_environment
    
    load_environment()
    client = TopstepClient(
        username=os.getenv("TOPSTEPX_USERNAME"),
        api_key=os.getenv("TOPSTEPX_API_KEY")
    )
    
    analyzer = MarketDataAnalyzer(client)
    
    # Test signal
    test_signal = {
        'action': 'BUY',
        'symbol': 'MNQ',
        'price': 21250.0,
        'quantity': 2
    }
    
    # Mock sentiment
    from .sentiment_analyzer import SentimentAnalysis
    sentiment = SentimentAnalysis(
        sentiment_score=0.3,
        market_bias="BULLISH",
        confidence=0.7,
        key_factors=["Test analysis"],
        risk_level="MEDIUM",
        position_adjustment=1.2
    )
    
    confidence = analyzer.analyze_signal_confidence(test_signal, sentiment)
    print(f"Signal Confidence: {confidence}")