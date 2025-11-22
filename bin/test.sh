#!/bin/bash

# Test script for Messaging Service API
# Don't exit on first error - we want to see all test results
set +e

# Configuration
API_URL=${API_URL:-http://localhost:8080}
API_PREFIX="/api/v1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Messaging Service API Test Suite${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Function to make API calls
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_status=$4
    local use_api_prefix=${5:-true}
    
    echo -e "${YELLOW}Testing: $method $endpoint${NC}"
    
    # Construct URL with or without API prefix
    if [ "$use_api_prefix" = "true" ]; then
        url="$API_URL$API_PREFIX$endpoint"
    else
        url="$API_URL$endpoint"
    fi
    
    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X $method "$url" -H "Content-Type: application/json")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$url" -H "Content-Type: application/json" -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ Status: $http_code (Expected: $expected_status)${NC}"
        if [ ! -z "$body" ]; then
            echo "Response: $body" | jq '.' 2>/dev/null || echo "$body"
        fi
        echo ""
        return 0
    else
        echo -e "${RED}✗ Status: $http_code (Expected: $expected_status)${NC}"
        echo "Response: $body"
        echo ""
        return 1
    fi
}

# Health check
echo -e "${BLUE}1. Health Check Tests${NC}"
echo "------------------------"
api_call "GET" "/health" "" "200" "false"
api_call "GET" "/ready" "" "200" "false"

# Send SMS message
echo -e "${BLUE}2. Send SMS Message${NC}"
echo "------------------------"
SMS_DATA='{
    "from": "+15551234567",
    "to": "+15559876543",
    "type": "sms",
    "body": "Test SMS message from API test suite"
}'
SMS_RESPONSE=$(api_call "POST" "/messages/send" "$SMS_DATA" "201")

# Extract message ID from response (if needed for further tests)
MESSAGE_ID=$(echo "$SMS_RESPONSE" | grep -o '"id":"[^"]*' | grep -o '[^"]*$' | head -n1)

# Send MMS message
echo -e "${BLUE}3. Send MMS Message${NC}"
echo "------------------------"
MMS_DATA='{
    "from": "+15551234567",
    "to": "+15559876543",
    "type": "mms",
    "body": "Test MMS message with attachment",
    "attachments": ["https://example.com/image.jpg"]
}'
api_call "POST" "/messages/send" "$MMS_DATA" "201"

# Send email
echo -e "${BLUE}4. Send Email${NC}"
echo "------------------------"
EMAIL_DATA='{
    "from": "sender@example.com",
    "to": "recipient@example.com",
    "type": "email",
    "body": "<h1>Test Email</h1><p>This is a test email from the API test suite.</p>",
    "attachments": []
}'
api_call "POST" "/messages/send" "$EMAIL_DATA" "201"

# List messages
echo -e "${BLUE}5. List Messages${NC}"
echo "------------------------"
api_call "GET" "/messages/?limit=10" "" "200"

# Get specific message (if we have an ID)
if [ ! -z "$MESSAGE_ID" ]; then
    echo -e "${BLUE}6. Get Specific Message${NC}"
    echo "------------------------"
    api_call "GET" "/messages/$MESSAGE_ID" "" "200"
fi

# List conversations
echo -e "${BLUE}7. List Conversations${NC}"
echo "------------------------"
api_call "GET" "/conversations/?limit=10" "" "200"

# Search conversations
echo -e "${BLUE}8. Search Conversations${NC}"
echo "------------------------"
SEARCH_DATA='{
    "query": "test",
    "limit": 5
}'
api_call "POST" "/conversations/search" "$SEARCH_DATA" "200"

# Test webhook endpoints
echo -e "${BLUE}9. Webhook Tests${NC}"
echo "------------------------"
TWILIO_WEBHOOK='{
    "messaging_provider_id": "test_123",
    "from": "+15551234567",
    "to": "+15559876543",
    "type": "sms",
    "body": "Incoming SMS via webhook",
    "timestamp": "2024-01-01T12:00:00Z"
}'
api_call "POST" "/webhooks/twilio" "$TWILIO_WEBHOOK" "200"

# Test rate limiting (optional)
echo -e "${BLUE}10. Rate Limiting Test${NC}"
echo "------------------------"
echo "Sending multiple requests to test rate limiting..."
for i in {1..5}; do
    echo -n "Request $i: "
    curl -s -o /dev/null -w "%{http_code}\n" -X GET "$API_URL$API_PREFIX/messages/"
    sleep 0.5
done
echo ""

# Performance test with concurrent requests
echo -e "${BLUE}11. Performance Test${NC}"
echo "------------------------"
echo "Sending 10 concurrent requests..."
for i in {1..10}; do
    (curl -s -o /dev/null -w "Request $i: %{http_code} - Time: %{time_total}s\n" -X GET "$API_URL$API_PREFIX/messages/") &
done
wait
echo ""

# Metrics endpoint
echo -e "${BLUE}12. Metrics Check${NC}"
echo "------------------------"
echo "Checking metrics endpoint..."
curl -s "$API_URL/metrics" | head -20
echo "..."
echo ""

# Summary
echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}API Test Suite Complete!${NC}"
echo -e "${BLUE}=========================================${NC}"
