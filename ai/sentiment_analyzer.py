import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import openai

logger = logging.getLogger(__name__)

@dataclass
class SentimentAnalysis:
    """Data class for sentiment analysis results"""
    sentiment_score: float  # -1 to 1 scale
    market_bias: str  # "BULLISH", "BEARISH", "NEUTRAL"
    confidence: float  # 0 to 1 scale
    key_factors: List[str]
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    position_adjustment: float  # Multiplier for position size

class NewsDataCollector:
    """Collects market news and data for sentiment analysis"""
    
    def __init__(self):
        # You can add news API keys here (Alpha Vantage, News API, etc.)
        self.news_sources = {
            'market_watch': 'https://www.marketwatch.com/rss/markets',
            'yahoo_finance': 'https://finance.yahoo.com/rss/headline',
            'cnbc': 'https://www.cnbc.com/id/100003114/device/rss/rss.html'
        }
    
    def get_recent_market_news(self, hours_back: int = 2) -> List[str]:
        """Get recent market news headlines"""
        # Mock headlines for demo - replace with real API calls
        mock_headlines = [
            "Federal Reserve hints at potential rate cuts amid economic uncertainty",
            "Tech stocks rally as AI investments surge",
            "Nasdaq futures show strength in pre-market trading",
            "Economic data suggests continued market volatility",
            "Institutional investors increase positions in index futures"
        ]
        
        # In production, implement real news API integration:
        # 1. News API: https://newsapi.org/
        # 2. Alpha Vantage News: https://www.alphavantage.co/
        # 3. Financial Modeling Prep: https://financialmodelingprep.com/
        
        return mock_headlines
    
    def get_economic_calendar_events(self) -> List[Dict]:
        """Get upcoming economic events"""
        # Mock economic events
        events = [
            {
                "time": "14:30",
                "event": "Employment Data Release",
                "importance": "HIGH",
                "expected_impact": "VOLATILE"
            },
            {
                "time": "16:00", 
                "event": "Fed Speech",
                "importance": "MEDIUM",
                "expected_impact": "MODERATE"
            }
        ]
        return events

class OpenAISentimentAnalyzer:
    """OpenAI-powered sentiment analysis for trading decisions"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = openai.OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY")
        )
        self.news_collector = NewsDataCollector()
        
        # Model configuration
        self.model = "gpt-4o"  # Latest model for best analysis
        self.max_tokens = 500
        
    def analyze_market_sentiment(self, 
                               current_price: float,
                               price_change_24h: float,
                               volume_ratio: float = 1.0,
                               include_news: bool = True) -> SentimentAnalysis:
        """Analyze current market sentiment using OpenAI"""
        
        try:
            # Collect market data
            market_data = {
                "current_price": current_price,
                "price_change_24h": price_change_24h,
                "volume_ratio": volume_ratio,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Get news headlines if requested
            news_headlines = []
            economic_events = []
            
            if include_news:
                news_headlines = self.news_collector.get_recent_market_news()
                economic_events = self.news_collector.get_economic_calendar_events()
            
            # Create analysis prompt
            prompt = self._create_sentiment_prompt(
                market_data, news_headlines, economic_events
            )
            
            # Get OpenAI analysis
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert financial analyst specializing in futures trading sentiment analysis. Provide precise, actionable insights for trading decisions."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=0.3  # Lower temperature for more consistent analysis
            )
            
            # Parse response
            analysis_text = response.choices[0].message.content
            sentiment_analysis = self._parse_openai_response(analysis_text)
            
            logger.info(f"OpenAI Sentiment Analysis: {sentiment_analysis}")
            return sentiment_analysis
            
        except Exception as e:
            logger.error(f"Error in OpenAI sentiment analysis: {e}")
            # Return neutral sentiment on error
            return SentimentAnalysis(
                sentiment_score=0.0,
                market_bias="NEUTRAL",
                confidence=0.5,
                key_factors=["Analysis error - using neutral sentiment"],
                risk_level="MEDIUM",
                position_adjustment=1.0
            )
    
    def _create_sentiment_prompt(self, 
                               market_data: Dict, 
                               news_headlines: List[str],
                               economic_events: List[Dict]) -> str:
        """Create the analysis prompt for OpenAI"""
        
        prompt = f"""
Analyze the current market sentiment for MNQ (Micro E-mini Nasdaq-100) futures trading.

MARKET DATA:
- Current Price: ${market_data['current_price']}
- 24h Price Change: {market_data['price_change_24h']:+.2f}%
- Volume Ratio: {market_data['volume_ratio']:.2f}x average
- Analysis Time: {market_data['timestamp']}

"""
        
        if news_headlines:
            prompt += "RECENT NEWS HEADLINES:\n"
            for i, headline in enumerate(news_headlines[:5], 1):
                prompt += f"{i}. {headline}\n"
            prompt += "\n"
        
        if economic_events:
            prompt += "UPCOMING ECONOMIC EVENTS:\n"
            for event in economic_events:
                prompt += f"- {event['time']}: {event['event']} (Impact: {event['expected_impact']})\n"
            prompt += "\n"
        
        prompt += """
Please provide your analysis in the following JSON format:

{
    "sentiment_score": <number between -1 and 1, where -1 is extremely bearish, 0 is neutral, 1 is extremely bullish>,
    "market_bias": <"BULLISH" or "BEARISH" or "NEUTRAL">,
    "confidence": <number between 0 and 1 indicating confidence in analysis>,
    "key_factors": [<list of 2-4 key factors influencing sentiment>],
    "risk_level": <"LOW" or "MEDIUM" or "HIGH">,
    "position_adjustment": <number between 0.5 and 2.0 - multiplier for position sizing based on sentiment>
}

Consider:
1. Overall market momentum and trend
2. News impact on tech/futures markets
3. Volume patterns and market participation
4. Economic event timing and potential impact
5. Risk-reward ratio for current market conditions

Focus on actionable insights for short-term futures trading (1-4 hour holding periods).
"""
        
        return prompt
    
    def _parse_openai_response(self, response_text: str) -> SentimentAnalysis:
        """Parse OpenAI response into SentimentAnalysis object"""
        
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = response_text[json_start:json_end]
                analysis_data = json.loads(json_str)
                
                return SentimentAnalysis(
                    sentiment_score=float(analysis_data.get('sentiment_score', 0.0)),
                    market_bias=analysis_data.get('market_bias', 'NEUTRAL'),
                    confidence=float(analysis_data.get('confidence', 0.5)),
                    key_factors=analysis_data.get('key_factors', []),
                    risk_level=analysis_data.get('risk_level', 'MEDIUM'),
                    position_adjustment=float(analysis_data.get('position_adjustment', 1.0))
                )
            else:
                raise ValueError("No JSON found in response")
                
        except Exception as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            logger.debug(f"Response text: {response_text}")
            
            # Fallback to text analysis
            return self._fallback_text_analysis(response_text)
    
    def _fallback_text_analysis(self, text: str) -> SentimentAnalysis:
        """Fallback analysis when JSON parsing fails"""
        
        # Simple keyword-based sentiment analysis
        bullish_words = ['bullish', 'positive', 'upward', 'rally', 'strong', 'buy', 'growth']
        bearish_words = ['bearish', 'negative', 'downward', 'decline', 'weak', 'sell', 'drop']
        
        text_lower = text.lower()
        bullish_count = sum(1 for word in bullish_words if word in text_lower)
        bearish_count = sum(1 for word in bearish_words if word in text_lower)
        
        if bullish_count > bearish_count:
            sentiment_score = min(0.7, bullish_count * 0.2)
            market_bias = "BULLISH"
        elif bearish_count > bullish_count:
            sentiment_score = max(-0.7, -bearish_count * 0.2)
            market_bias = "BEARISH"
        else:
            sentiment_score = 0.0
            market_bias = "NEUTRAL"
        
        return SentimentAnalysis(
            sentiment_score=sentiment_score,
            market_bias=market_bias,
            confidence=0.6,
            key_factors=["Fallback text analysis"],
            risk_level="MEDIUM",
            position_adjustment=1.0
        )

if __name__ == "__main__":
    # Test the sentiment analyzer
    analyzer = OpenAISentimentAnalyzer()
    
    sentiment = analyzer.analyze_market_sentiment(
        current_price=21250.0,
        price_change_24h=1.2,
        volume_ratio=1.5
    )
    
    print(f"Sentiment Analysis: {sentiment}")