import os
import json
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify
from topstepapi import TopstepClient
from topstepapi.load_env import load_environment
from topstepapi.order import OrderAPI

# Load environment variables
load_environment()

# Initialize Flask app
app = Flask(__name__)

# Initialize Topstep client
client = TopstepClient(
    username=os.getenv("TOPSTEPX_USERNAME"),
    api_key=os.getenv("TOPSTEPX_API_KEY")
)

# Initialize Order API with session token
order_api = OrderAPI(token=os.getenv("TOPSTEPX_SESSION_TOKEN"), base_url=os.getenv("TOPSTEP_BASE_URL"))

# Default contract
DEFAULT_CONTRACT = "CON.F.US.MNQ.M25"  # Micro E-mini Nasdaq-100 Futures

@app.route('/')
def index():
    """Render the main chart page"""
    return render_template('index.html')

@app.route('/api/test')
def test_api():
    """Test endpoint to verify API is working"""
    return jsonify({
        'success': True,
        'message': 'API is working',
        'time': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    })

@app.route('/api/bars/<contract_id>')
def get_bars(contract_id):
    """Get historical bars for a contract"""
    # Default to MNQ if no contract specified
    if not contract_id:
        contract_id = DEFAULT_CONTRACT
    
    print(f"API request for contract: {contract_id}")
    
    # Make sure we have a valid session token
    session_token = os.getenv("TOPSTEPX_SESSION_TOKEN")
    if not session_token:
        print("No session token found in environment variables")
        return jsonify({
            'success': False,
            'error': "No session token found. Please run get_token.sh first."
        }), 401
    
    print(f"Using session token: {session_token[:10]}...")
    
    # Calculate time range (last 24 hours)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)
    
    # Format times for API
    start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Time range: {start_time_str} to {end_time_str}")
    
    try:
        # Try to use the real API
        print(f"Attempting to call HistoryAPI.retrieve_bars for {contract_id}")
        
        # Check if client.history has the token set
        if not hasattr(client.history, 'token') or not client.history.token:
            print("Setting token on history API")
            client.history.token = session_token
        
        # Print the parameters being sent to the API
        print(f"API Parameters: contract_id={contract_id}, live=False, start_time={start_time_str}, end_time={end_time_str}")
        
        try:
            # Call the real API
            bars = client.history.retrieve_bars(
                contract_id=contract_id,
                live=False,
                start_time=start_time_str,
                end_time=end_time_str,
                unit=1,  # 1 = minute
                unit_number=5,  # 5-minute bars
                limit=100,
                include_partial_bar=True
            )
            print(f"API call successful, received {len(bars) if bars else 0} bars")
        except Exception as api_error:
            print(f"API call failed with error: {api_error}")
            print("Falling back to sample data")
            current_price = 21250.0
            bars = generate_sample_data(current_price, 20)
        
        # If no bars returned, generate some sample data
        if not bars:
            print(f"No data returned for {contract_id}, generating sample data")
            # Get current price from order book if possible
            current_price = 21250.0  # Default fallback price
            try:
                # Try to get a better price from the order book
                order_book = order_api.get_order_book(contract_id)
                if order_book and len(order_book.get('asks', [])) > 0:
                    current_price = order_book['asks'][0]['price']
                elif order_book and len(order_book.get('bids', [])) > 0:
                    current_price = order_book['bids'][0]['price']
            except Exception as e:
                print(f"Error getting order book: {e}")
            
            # Generate sample data
            bars = generate_sample_data(current_price, 20)
        
        # Format data for Chart.js
        formatted_bars = []
        for bar in bars:
            # Ensure we have all required fields with proper types
            try:
                # Handle both full names and single-letter keys (t, o, h, l, c, v)
                time_value = bar.get('timestamp', bar.get('time', bar.get('t')))
                if not time_value:
                    print(f"Warning: Bar missing time value: {bar}")
                    continue
                    
                open_value = float(bar.get('open', bar.get('o', 0)))
                high_value = float(bar.get('high', bar.get('h', 0)))
                low_value = float(bar.get('low', bar.get('l', 0)))
                close_value = float(bar.get('close', bar.get('c', 0)))
                volume_value = int(bar.get('volume', bar.get('v', 0)))
                
                formatted_bars.append({
                    'time': time_value,
                    'open': open_value,
                    'high': high_value,
                    'low': low_value,
                    'close': close_value,
                    'volume': volume_value
                })
                
                # Debug output
                if len(formatted_bars) <= 2:
                    print(f"Formatted bar: {formatted_bars[-1]}")
                    
            except (TypeError, ValueError) as e:
                print(f"Error formatting bar data: {e}, bar: {bar}")
                continue
        
        return jsonify({
            'success': True,
            'contract': contract_id,
            'bars': formatted_bars
        })
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def generate_sample_data(base_price, num_bars):
    """Generate sample price data for demo purposes"""
    import random
    
    bars = []
    current_time = datetime.utcnow() - timedelta(hours=num_bars)
    price = float(base_price)  # Ensure price is a float
    
    for i in range(num_bars):
        # Generate random price movement
        open_price = price
        close_price = open_price * (1 + (random.random() - 0.5) * 0.01)  # +/- 0.5%
        high_price = max(open_price, close_price) * (1 + random.random() * 0.005)  # Up to 0.5% higher
        low_price = min(open_price, close_price) * (1 - random.random() * 0.005)   # Up to 0.5% lower
        volume = int(random.random() * 1000) + 100  # Random volume between 100 and 1100
        
        # Create bar
        bar_time = current_time + timedelta(hours=i)
        time_str = bar_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Ensure all values are properly formatted
        bars.append({
            'time': time_str,
            'timestamp': time_str,
            'open': float(round(open_price, 2)),
            'high': float(round(high_price, 2)),
            'low': float(round(low_price, 2)),
            'close': float(round(close_price, 2)),
            'volume': int(volume)
        })
        
        # Update price for next bar
        price = close_price
    
    print(f"Generated {len(bars)} sample bars with base price {base_price}")
    return bars

if __name__ == '__main__':
    app.run(debug=True, port=5000)