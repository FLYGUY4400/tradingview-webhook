import os
from decimal import Decimal
from topstepapi.load_env import load_environment
from topstepapi.order import OrderAPI

# Load environment variables
load_environment()

# Initialize OrderAPI
order_api = OrderAPI(
    token=os.getenv("TOPSTEPX_SESSION_TOKEN"),
    base_url=os.getenv("TOPSTEP_BASE_URL")
)

# --- Hardcoded Values (Change These) ---
account_id = "7049129"
order_id = "1134487627"
new_price = Decimal("21425.00")  # New limit/stop price if applicable
new_tp = Decimal("21370.00")     # Take Profit level
new_sl = Decimal("21330.00")     # Stop Loss level

# --- Modify the Order ---
try:
    response = order_api.modify_order(
        account_id=account_id,
        order_id=order_id,
        take_profit=new_tp,
        stop_loss=new_sl
    )
    print("Order modified successfully.")
    print(response)
except Exception as e:
    print("Error modifying order:", e)
