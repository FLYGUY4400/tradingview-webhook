import requests
from decimal import Decimal 

class OrderAPI:
    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url

    def search_orders(self, account_id: int, start_timestamp: str, end_timestamp: str = None):
        url = f"{self.base_url}/api/Order/search"
        headers = {
            "accept": "text/plain",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        payload = {
            "accountId": account_id,
            "startTimestamp": start_timestamp
        }
        if end_timestamp:
            payload["endTimestamp"] = end_timestamp

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("errorCode") == 0:
                return data.get("orders", [])
            else:
                raise Exception(f"API Error: {data.get('errorMessage')}")
        else:
            raise Exception(f"HTTP Error: {response.status_code} {response.text}")

    def search_open_orders(self, account_id: int):
        url = f"{self.base_url}/api/Order/searchOpen"
        headers = {
            "accept": "text/plain",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        payload = {
            "accountId": account_id
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("errorCode") == 0:
                return data.get("orders", [])
            else:
                raise Exception(f"API Error: {data.get('errorMessage')}")
        else:
            raise Exception(f"HTTP Error: {response.status_code} {response.text}")

    def place_order(
        self,
        account_id: int,
        contract_id: str,
        type: int,
        side: int,
        size: int,
        limit_price: Decimal = None,
        stop_price: Decimal = None,
        trail_price: Decimal = None,
        custom_tag: str = None,
        linked_order_id: int = None
    ):
        url = f"{self.base_url}/api/Order/place"
        headers = {
            "accept": "text/plain",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        # Build the request data, converting Decimal to string for JSON serialization
        data = {
            "accountId": account_id,
            "contractId": contract_id,
            "type": type,
            "side": side,
            "size": size
        }
        
        # Only add the optional parameters if they are not None
        if limit_price is not None:
            data["limitPrice"] = str(limit_price)
        if stop_price is not None:
            data["stopPrice"] = str(stop_price)
        if trail_price is not None:
            data["trailPrice"] = str(trail_price)
        if custom_tag is not None:
            data["customTag"] = custom_tag
        if linked_order_id is not None:
            data["linkedOrderId"] = linked_order_id
            
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("errorCode") == 0:
                return data.get("orderId")
            else:
                raise Exception(f"API Error: {data.get('errorMessage')}")
        else:
            raise Exception(f"HTTP Error: {response.status_code} {response.text}")

    def cancel_order(self, account_id: int, order_id: int):
        url = f"{self.base_url}/api/Order/cancel"
        headers = {
            "accept": "text/plain",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        payload = {
            "accountId": account_id,
            "orderId": order_id
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("errorCode") == 0:
                return True
            else:
                raise Exception(f"API Error: {data.get('errorMessage')}")
        else:
            raise Exception(f"HTTP Error: {response.status_code} {response.text}")

    def modify_order(
        self,
        account_id: int,
        order_id: int,
        size=None,
        limit_price=None,
        stop_price=None,
        trail_price=None,
        linked_order_id: int = None
    ):
        url = f"{self.base_url}/api/Order/modify"
        headers = {
            "accept": "text/plain",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        # Build the payload with only provided parameters
        payload = {
            "accountId": account_id,
            "orderId": order_id
        }
        
        # Add optional parameters if they are not None
        if size is not None:
            payload["size"] = size
        if limit_price is not None:
            payload["limitPrice"] = str(limit_price) if isinstance(limit_price, Decimal) else limit_price
        if stop_price is not None:
            payload["stopPrice"] = str(stop_price) if isinstance(stop_price, Decimal) else stop_price
        if trail_price is not None:
            payload["trailPrice"] = str(trail_price) if isinstance(trail_price, Decimal) else trail_price
        if linked_order_id is not None:
            payload["linkedOrderId"] = linked_order_id
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("errorCode") == 0:
                return True
            else:
                raise Exception(f"API Error: {data.get('errorMessage')}")
        else:
            raise Exception(f"HTTP Error: {response.status_code} {response.text}")