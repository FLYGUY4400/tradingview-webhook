#!/bin/bash

# Directory where this script is located, assuming .env is in the same directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# Fetch the new token
# Fetch the full JSON response
JSON_RESPONSE=$(curl -s -X POST "https://api.topstepx.com/api/Auth/loginKey" \
  -H "accept: text/plain" \
  -H "Content-Type: application/json" \
  -d '{"userName":"flyguy4400","apiKey":"6NvaohkyHCIpU2ximDfGi2iGdRoPUMD/xfAxMkRWoR8="}')

# Check if JSON_RESPONSE is empty or an error occurred
if [ -z "$JSON_RESPONSE" ]; then
  echo "Error: Failed to fetch API response or response is empty."
  exit 1
fi

# Try to extract token using jq (if available)
if command -v jq &> /dev/null; then
  EXTRACTED_TOKEN=$(echo "$JSON_RESPONSE" | jq -r '.token')
else
  # Fallback to sed if jq is not available (less robust)
  # This regex tries to find "token":"<value>" and extracts <value>
  EXTRACTED_TOKEN=$(echo "$JSON_RESPONSE" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
fi

# Check if token extraction was successful
if [ -z "$EXTRACTED_TOKEN" ] || [ "$EXTRACTED_TOKEN" == "null" ]; then
  echo "Error: Could not extract token from JSON response."
  echo "Response was: $JSON_RESPONSE"
  exit 1
fi

# Use the extracted token
NEW_TOKEN="$EXTRACTED_TOKEN"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: .env file not found at $ENV_FILE"
  # Optionally, create it if it doesn't exist and you want to add the token
  # echo "TOPSTEPX_SESSION_TOKEN=$NEW_TOKEN" > "$ENV_FILE"
  # echo ".env file created with new token."
  exit 1
fi

# Update TOPSTEPX_SESSION_TOKEN in .env file
# Check if the variable already exists in the .env file
if grep -q "^TOPSTEPX_SESSION_TOKEN=" "$ENV_FILE"; then
  # Variable exists, so replace its value, ensuring it's quoted
  # Note: Using | as a delimiter for sed to avoid issues if token contains /
  sed -i "s|^TOPSTEPX_SESSION_TOKEN=.*|TOPSTEPX_SESSION_TOKEN=\"$NEW_TOKEN\"|" "$ENV_FILE"
  echo "TOPSTEPX_SESSION_TOKEN updated in $ENV_FILE (as string)"
else
  # Variable does not exist, so append it, ensuring it's quoted
  echo -e "\nTOPSTEPX_SESSION_TOKEN=\"$NEW_TOKEN\"" >> "$ENV_FILE"
  echo "TOPSTEPX_SESSION_TOKEN added to $ENV_FILE (as string)"
fi

exit 0