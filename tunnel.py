from flask import Flask, request, jsonify, make_response
import ssl
import os
import hmac
import hashlib
import json
from datetime import datetime, timedelta

app = Flask(__name__)

# Get secret from environment variable
#WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-secret-key')

# Simple in-memory trade log
trades = []

#def verify_signature(payload, signature):
 #   """Verify the webhook signature"""
  #  digest = hmac.new(
   #     WEBHOOK_SECRET.encode('utf-8'),
    #    msg=payload.encode('utf-8'),
     #   digestmod=hashlib.sha256
    #).hexdigest()
    #return hmac.compare_digest(digest, signature)

@app.route('/')
def home():
    return "TradingView Webhook Server is running! Use POST /webhook endpoint."

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        print("\n=== New Webhook Request ===")
        print(f"Method: {request.method}")
        print(f"Content-Type: {request.content_type}")
        print(f"Headers: {dict(request.headers)}")
        
        # Initialize variables with default values
        action = ''
        symbol = ''
        price = 0.0
        quantity = 1.0  # Default quantity if not provided
        tp = 0.0
        sl = 0.0
        timestamp = None
        
        if request.is_json:
            data = request.get_json()
            # Handle new format with timestamp and qty
            if 'time' in data:
                action = str(data.get('action', '')).upper()
                symbol = str(data.get('symbol', ''))
                price = float(data.get('price', 0))
                quantity = float(data.get('qty', 1))  # Using qty instead of quantity
                tp = float(data.get('tp', 0))
                sl = float(data.get('sl', 0))
                timestamp = data.get('time')
            else:
                # Handle old format for backward compatibility
                action = str(data.get('action', '')).upper()
                symbol = str(data.get('symbol', ''))
                price = float(data.get('price', 0))
                quantity = float(data.get('quantity', 1))
                tp = float(data.get('tp', 0))
                sl = float(data.get('sl', 0))
        else:
            # Handle raw form data (action=buy&symbol=...)
            raw_data = request.get_data(as_text=True)
            print(f"Raw form data: {raw_data}")
            
            # Parse the form data
            params = {}
            for pair in raw_data.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = value
            
            action = str(params.get('action', '')).upper()
            symbol = str(params.get('symbol', ''))
            try:
                price = float(params.get('price', 0))
                quantity = float(params.get('qty', 1))  # Using qty as per new format
                tp = float(params.get('tp', 0))
                sl = float(params.get('sl', 0))
            except (ValueError, TypeError) as e:
                print(f"Error parsing numeric values: {e}")
                price = 0.0
                quantity = 1.0
                tp = 0.0
                sl = 0.0
        
        print(f"TradingView Webhook: {action} {quantity} {symbol} @ {price}")
        
        # Log the trade
        trade = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'symbol': symbol,
            'price': price,
            'quantity': quantity,
            'tp': tp,
            'sl': sl
        }
        trades.append(trade)
        
        # Save trades to file (optional)
        try:
            with open('trades.json', 'w') as f:
                json.dump(trades, f, indent=2)
            
            return jsonify({
                'status': 'success',
                'message': 'Trade processed',
                'trade': trade
            }), 200
            
        except Exception as e:
            print(f"Error saving trade to file: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Error saving trade to file',
                'error': str(e)
            }), 500
            
    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Error processing request',
            'error': str(e)
        }), 400

def generate_self_signed_cert():
    """Generate a self-signed certificate if it doesn't exist"""
    cert_file = 'cert.pem'
    key_file = 'key.pem'
    
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
        
        # Generate private key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        # Generate self-signed certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"My Company"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .sign(key, hashes.SHA256())
        )
        
        # Save certificate
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(Encoding.PEM))
        
        # Save private key
        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
    
    return cert_file, key_file

def main():
    try:
        # Load existing trades if any
        global trades
        try:
            if os.path.exists('trades.json'):
                with open('trades.json', 'r') as f:
                    trades = json.load(f)
                print(f"Loaded {len(trades)} existing trades")
        except Exception as e:
            print(f"Warning: Could not load trades: {e}")
        
        # Generate self-signed certificate
        cert_file, key_file = generate_self_signed_cert()
        
        # Create SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        
        print(" * Starting HTTPS server on https://localhost:5000")
        print(" * Note: Your browser will show a security warning for the self-signed certificate")
        print(" * TradingView Webhook URL: https://localhost:5000/webhook")
        print(" * Test with: curl -X POST https://localhost:5000/webhook -d 'action=BUY&symbol=BTCUSD&price=50000&quantity=0.01'")
        print(" * Press Ctrl+C to stop the server")
        print("\n=== Waiting for requests ===\n")
        
        # Enable debug and request logging
        app.config['DEBUG'] = True
        app.run(host='0.0.0.0', port=5000, ssl_context=context, debug=True, use_reloader=False)
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\nPress Enter to exit...")
        input()

if __name__ == '__main__':
    # No SSL needed - ngrok will handle HTTPS
    print("Starting webhook server for ngrok...")
    print("Run this command in a new terminal:")
    print("ngrok http 5000")
    print("\nThen use the https:// URL from ngrok in TradingView")
    print("Press Ctrl+C to stop the server\n")
    
    # Run on port 5000 (default Flask port)
    app.run(host='0.0.0.0', port=5000, debug=True)