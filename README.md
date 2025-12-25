# Agent Bridge Service

A service that enables two voice agents to have real-time audio conversations by bridging their connections.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Bridge Service                         │
│                                                                  │
│   ┌─────────────┐      ┌──────────┐      ┌─────────────┐        │
│   │  Transport  │◄────►│  Bridge  │◄────►│  Transport  │        │
│   │  (WS/Twilio)│      │  (Core)  │      │  (WS/Twilio)│        │
│   └─────────────┘      └──────────┘      └─────────────┘        │
│         ▲                                       ▲                │
└─────────┼───────────────────────────────────────┼────────────────┘
          │                                       │
     ┌────▼────┐                             ┌────▼────┐
     │ Agent A │                             │ Agent B │
     └─────────┘                             └─────────┘
```

The bridge is **transport-agnostic**. It simply:
1. Receives audio from Transport A
2. Forwards it to Transport B
3. Receives audio from Transport B
4. Forwards it to Transport A

## Project Structure

```
agent_bridge/
├── api/
│   ├── app.py              # FastAPI app
│   └── routes/
│       ├── websocket.py    # WebSocket conversation routes
│       └── twilio.py       # Twilio conversation routes
├── transports/
│   ├── base.py             # AbstractTransport interface
│   ├── websocket.py        # WebSocket transport
│   └── twilio.py           # Twilio transport
├── bridge.py               # Core bridge logic (transport-agnostic)
├── audio_recorder.py       # Recording functionality
└── main.py                 # Entry point
```

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py                    # Default: 0.0.0.0:8080
python main.py --port 9000        # Custom port
python main.py --reload           # Dev mode
```

API docs: `http://localhost:8080/docs`

## API Endpoints

### WebSocket Conversations

```bash
# Start conversation
POST /conversations
{
  "backend_ws_url": "ws://localhost:8000",
  "agent_a_id": "agent_1",
  "agent_b_id": "agent_2",
  "recording_enabled": true
}

# Get status
GET /conversations/{id}

# Stop
POST /conversations/{id}/stop

# List all
GET /conversations
```

### Twilio Conversations

Requires environment variables:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `TWILIO_WEBHOOK_BASE_URL` (must be publicly accessible, for HTTP webhooks)
- `TWILIO_WEBSOCKET_BASE_URL` (must be publicly accessible, for WebSocket media streams, e.g., `wss://your-domain.com`)

```bash
# Start call
POST /twilio/calls
{
  "agent_a_number": "+1234567890",
  "agent_b_number": "+1987654321",
  "recording_enabled": true
}

# Get status
GET /twilio/calls/{session_id}

# Stop
POST /twilio/calls/{session_id}/stop

# List all
GET /twilio/calls
```

### Health

```bash
GET /health
```

## How It Works

1. **API layer** creates the appropriate transports (WebSocket or Twilio)
2. **Transports** are injected into the **Bridge**
3. **Bridge** calls `transport.receive()` and `transport.send()` to route audio
4. Bridge is completely unaware of transport implementation details

## Adding a New Transport

1. Create `transports/your_transport.py` implementing `AbstractTransport`
2. Create `api/routes/your_transport.py` with routes that:
   - Create your transport instances
   - Pass them to `AgentBridge`
3. Register the router in `api/app.py`

That's it. The bridge works with any transport that implements the interface.

## Requirements

- Python 3.10+
- For Twilio: `twilio` package and valid credentials
