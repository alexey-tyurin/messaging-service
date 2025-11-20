#!/bin/bash

# Test script to demonstrate provider error handling (500, 429)
set +e

# Configuration
API_URL=${API_URL:-http://localhost:8000}
API_PREFIX="/api/v1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Provider Error Handling Test${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo -e "${YELLOW}Testing with error simulation enabled${NC}"
echo -e "${YELLOW}Provider 500 Rate: 5%, Provider 429 Rate: 5%${NC}"
echo ""

# Function to send message and check response
send_message() {
    local type=$1
    local from=$2
    local to=$3
    local body=$4
    local attempt=$5
    
    echo -e "${YELLOW}Attempt $attempt: Sending $type message${NC}"
    
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL$API_PREFIX/messages/send" \
        -H "Content-Type: application/json" \
        -d "{
            \"from\": \"$from\",
            \"to\": \"$to\",
            \"type\": \"$type\",
            \"body\": \"$body\"
        }")
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "201" ]; then
        status=$(echo "$body" | jq -r '.status' 2>/dev/null)
        provider=$(echo "$body" | jq -r '.provider' 2>/dev/null)
        message_id=$(echo "$body" | jq -r '.id' 2>/dev/null)
        echo -e "${GREEN}✓ Message sent successfully (Status: $status, Provider: $provider)${NC}"
        echo -e "  Message ID: $message_id"
    else
        error=$(echo "$body" | jq -r '.detail' 2>/dev/null)
        echo -e "${RED}✗ Failed with HTTP $http_code${NC}"
        echo -e "  Error: $error"
    fi
    echo ""
}

# Send multiple messages to trigger different error scenarios
echo -e "${BLUE}Sending 20 messages to demonstrate error handling...${NC}"
echo ""

for i in {1..20}; do
    # Alternate between SMS and Email
    if [ $((i % 2)) -eq 0 ]; then
        send_message "sms" "+15551234567" "+15559876543" "Test message $i with error handling" "$i"
    else
        send_message "email" "sender@example.com" "recipient@example.com" "Test email $i with error handling" "$i"
    fi
    
    # Small delay between requests
    sleep 0.5
done

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Checking message statuses${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Get recent messages
echo -e "${YELLOW}Fetching recent messages...${NC}"
response=$(curl -s "$API_URL$API_PREFIX/messages/?limit=20")
total=$(echo "$response" | jq -r '.total' 2>/dev/null)

echo "Total messages: $total"
echo ""

# Count messages by status
echo -e "${YELLOW}Message statuses:${NC}"
sent_count=$(echo "$response" | jq '[.messages[] | select(.status == "sent")] | length' 2>/dev/null)
retry_count=$(echo "$response" | jq '[.messages[] | select(.status == "retry")] | length' 2>/dev/null)
failed_count=$(echo "$response" | jq '[.messages[] | select(.status == "failed")] | length' 2>/dev/null)

echo -e "  ${GREEN}Sent: $sent_count${NC}"
echo -e "  ${YELLOW}Retry: $retry_count${NC}"
echo -e "  ${RED}Failed: $failed_count${NC}"
echo ""

echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}Error Handling Test Complete!${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo "Key Points:"
echo "  • 429 errors trigger rate limit backoff (60-120s)"
echo "  • 500 errors trigger exponential backoff (1.5x multiplier)"
echo "  • Messages retry up to 3 times before failing"
echo "  • Different error types are logged with appropriate context"
echo ""
echo "Check logs for detailed error handling:"
echo "  tail -f logs/app.log | grep -E 'rate_limit|server_error|retry'"

