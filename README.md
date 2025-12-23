# Backend Project for Messaging Service


---

## 🚀 Quick Start (For Running the Application)

```bash
# 1. Clone the repository:
git clone git@github.com:alexey-tyurin/messaging-service.git
cd messaging-service

# 2. Activate your conda environment
conda activate py311

# 3. Start Docker services (PostgreSQL & Redis)
docker compose up -d postgres redis

# 4. Run the application
make run

# 5. Stop the application
make stop

# 6. Restart the application
make restart-app
```

**📖 See [QUICK_START.md](./QUICK_START.md) to get started or [RUN_GUIDE.md](./RUN_GUIDE.md) for detailed operations and troubleshooting.**

**Application URLs:**
- 📚 API Docs: http://localhost:8080/docs
- 💚 Health: http://localhost:8080/health
- 📊 Metrics: http://localhost:8080/metrics

---

## Project Requirements

The service should implement:

- **Unified Messaging API**: HTTP endpoints to send and receive messages from both SMS/MMS and Email providers
  - Support sending messages through the appropriate provider based on message type
  - Handle incoming webhook messages from both providers
  - Conversations consist of messages from multiple providers
  - Provider may return HTTP error codes like 500, 429 and plan accordingly
  - All external resources should be mocked out by project
- **Conversation Management**: Messages should be automatically grouped into conversations based on participants (from/to addresses).
  Conversations consist of messages from multiple providers.
- **Data Persistence**: All conversations and messages must be stored in a relational database with proper relationships and indexing

### Providers

**SMS & MMS**

**Example outbound payload to send an SMS or MMS**

```json
{
    "from": "from-phone-number",
    "to": "to-phone-number",
    "type": "mms" | "sms",
    "body": "text message",
    "attachments": ["attachment-url"] | [] | null,
    "timestamp": "2024-11-01T14:00:00Z" // UTC timestamp
}
```

**Example inbound SMS**

```json
{
    "from": "+18045551234",
    "to": "+12016661234",
    "type": "sms",
    "messaging_provider_id": "message-1",
    "body": "text message",
    "attachments": null,
    "timestamp": "2024-11-01T14:00:00Z" // UTC timestamp
}
```

**Example inbound MMS**

```json
{
    "from": "+18045551234",
    "to": "+12016661234",
    "type": "mms",
    "messaging_provider_id": "message-2",
    "body": "text message",
    "attachments": ["attachment-url"] | [],
    "timestamp": "2024-11-01T14:00:00Z" // UTC timestamp
}
```

**Email Provider**

**Example Inbound Email**

```json
{
    "from": "[user@useapp.com](mailto:user@useapp.com)",
    "to": "[contact@gmail.com](mailto:contact@gmail.com)",
    "xillio_id": "message-2",
    "body": "<html><body>html is <b>allowed</b> here </body></html>",  "attachments": ["attachment-url"] | [],
    "timestamp": "2024-11-01T14:00:00Z" // UTC timestamp
}
```

**Example Email Payload**

```json
{
    "from": "[user@useapp.com](mailto:user@useapp.com)",
    "to": "[contact@gmail.com](mailto:contact@gmail.com)",
    "body": "text message with or without html",
    "attachments": ["attachment-url"] | [],
    "timestamp": "2024-11-01T14:00:00Z" // UTC timestamp
}
```
