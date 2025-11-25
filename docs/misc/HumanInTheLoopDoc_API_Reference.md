# Human In The Loop - API Reference

## Overview

This document describes the HTTP REST endpoints and WebSocket events for the Human In The Loop feature.

## Base URL

```
http://localhost:9100
```

## HTTP Endpoints

### 1. Submit Human Response

Submit a response for the current human turn.

**Endpoint:** `POST /api/discussion/human/submit`

**Request Body:**
```json
{
  "response": "string"  // Required: Human's response text
}
```

**Response - Success (200):**
```json
{
  "success": true,
  "turn": 5,                // Turn number recorded
  "speaker": "Human"        // Participant name
}
```

**Response - Error (400):**
```json
{
  "detail": "Empty responses not allowed"
}
```

**Response - Error (409):**
```json
{
  "detail": "Not currently waiting for human input"
}
```

**Behavior:**
- Validates non-empty if `human.allow_empty_submissions: false` in config
- Records turn in conversation history with 👤 marker
- Sets metadata: `human_turn: true`, `via_control_channel: false`
- Increments turn counter
- Clears `waiting_on_human` flag and advances to next speaker
- Emits `human_turn_completed` WebSocket event

**Example:**
```bash
curl -X POST http://localhost:9100/api/discussion/human/submit \
  -H "Content-Type: application/json" \
  -d '{"response": "I agree with the proposed solution"}'
```

---

### 2. Skip Human Turn

Skip the current human turn without providing a response.

**Endpoint:** `POST /api/discussion/human/skip`

**Request Body:** None

**Response - Success (200):**
```json
{
  "success": true,
  "turn": 5,
  "speaker": "Human"
}
```

**Response - Error (409):**
```json
{
  "detail": "Not currently waiting for human input"
}
```

**Behavior:**
- Records skipped turn with response: `"[Human turn skipped]"`
- Sets metadata: `human_turn: true`, `skipped: true`, `via_control_channel: false`
- Increments turn counter
- Clears `waiting_on_human` flag and advances to next speaker
- Emits `human_turn_skipped` WebSocket event

**Example:**
```bash
curl -X POST http://localhost:9100/api/discussion/human/skip
```

---

### 3. Toggle Bypass Mode

Enable or disable automatic skipping of human turns.

**Endpoint:** `POST /api/discussion/human/bypass/toggle`

**Request Body:** None

**Response - Success (200):**
```json
{
  "success": true,
  "bypass_human": false  // New bypass state
}
```

**Response - Error (404):**
```json
{
  "detail": "No active discussion"
}
```

**Behavior:**
- Toggles `bypass_human` flag (true ↔ false)
- When `bypass_human: true`, human turns automatically skipped in rotation
- Emits `bypass_human_toggled` WebSocket event with new state
- State persists until toggled again or session ends

**Example:**
```bash
curl -X POST http://localhost:9100/api/discussion/human/bypass/toggle
```

---

### 4. Get Discussion Status (Extended)

Get current discussion status including human turn fields.

**Endpoint:** `GET /api/discussion/status`

**Response - Success (200):**
```json
{
  "discussion_state": "running",
  "manager": {
    "turn_counter": 5,
    "current_agent": "Claude",
    "max_turns": 10,
    "awaiting_turn_extension": false
  },
  "config": {
    "discussion_topic": "Code review",
    "max_turns": 10
  },
  "error": null,

  // Human turn fields (Phase 3):
  "waiting_on_human": false,          // True when it's human's turn
  "bypass_human": false,              // True when bypass mode enabled
  "pending_turn_participant": null,   // Participant name when waiting (e.g., "Human")
  "human_enabled": true               // True if Human in participant list
}
```

**Behavior:**
- Polled every 2 seconds by frontend
- Provides fallback state synchronization if WebSocket disconnected
- Used for UI reload resilience (restores correct state on page refresh)

**Example:**
```bash
curl http://localhost:9100/api/discussion/status
```

---

### 5. Start Sessions (Extended)

Start tmux sessions for AI models (Human filtered).

**Endpoint:** `POST /api/sessions/start`

**Request Body:**
```json
{
  "project_directory": "/home/user/project",
  "models": ["claude", "codex", "human"]  // "human" accepted but filtered
}
```

**Behavior:**
- Accepts "human" in models list (normalized to lowercase)
- Filters out "human" before starting tmux sessions
- Only AI models get tmux sessions and WebSocket streams
- Human registered as participant with `has_controller: False`

---

## WebSocket Events

### Connection

**WebSocket URL:** `ws://localhost:9100/ws/discussion/events`

**Protocol:** WebSocket (RFC 6455)

**Connection Lifecycle:**
1. Client connects to WebSocket endpoint
2. Server sends events as JSON messages
3. Server sends periodic pings (every 30s) to keep connection alive
4. Client should handle ping frames (most libraries do automatically)
5. On disconnect, client should reconnect

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:9100/ws/discussion/events');

ws.onopen = () => {
  console.log('Connected to discussion events');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event received:', data);

  switch (data.type) {
    case 'human_turn_started':
      // Show "Your Turn!" UI
      break;
    case 'human_turn_completed':
      // Return to normal UI
      break;
    // ... handle other events
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from discussion events');
  // Reconnect logic here
};
```

---

### Event Types

All events have common fields:
```json
{
  "type": "event_type_name",
  "timestamp": 1234567890.123
}
```

#### 1. human_turn_started

Emitted when a human turn begins in the discussion.

**Fields:**
```json
{
  "type": "human_turn_started",
  "speaker": "Human",           // Participant name
  "turn": 5,                    // Turn number
  "timeout_seconds": 300,       // Timeout duration (null if disabled)
  "timestamp": 1234567890.123   // Unix timestamp
}
```

**Frontend Action:**
- Set `waitingOnHuman = true`
- Set `pendingTurnParticipant = speaker`
- Show "Your Turn!" banner
- Swap buttons to Submit/Skip

---

#### 2. human_turn_completed

Emitted when a human successfully submits a response.

**Fields:**
```json
{
  "type": "human_turn_completed",
  "speaker": "Human",
  "turn": 5,
  "via_control_channel": false,  // True if submitted via control channel
  "timestamp": 1234567890.123
}
```

**Frontend Action:**
- Set `waitingOnHuman = false`
- Set `pendingTurnParticipant = null`
- Set `humanActionPending = false`
- Hide banner, restore "Send to All" button

---

#### 3. human_turn_skipped

Emitted when a human skips their turn (manually or via control channel).

**Fields:**
```json
{
  "type": "human_turn_skipped",
  "speaker": "Human",
  "turn": 5,
  "via_control_channel": false,
  "timestamp": 1234567890.123
}
```

**Frontend Action:**
- Set `waitingOnHuman = false`
- Set `pendingTurnParticipant = null`
- Set `humanActionPending = false`
- Hide banner, restore "Send to All" button

---

#### 4. human_turn_timeout

Emitted when a human turn times out and is automatically skipped.

**Fields:**
```json
{
  "type": "human_turn_timeout",
  "speaker": "Human",
  "turn": 5,
  "elapsed_seconds": 301.5,      // Time elapsed before timeout
  "timestamp": 1234567890.123
}
```

**Frontend Action:**
- Set `waitingOnHuman = false`
- Set `pendingTurnParticipant = null`
- Set `humanActionPending = false`
- Show alert: "⏰ Human turn timed out and was automatically skipped"
- Hide banner, restore "Send to All" button

---

#### 5. bypass_human_toggled

Emitted when bypass mode is toggled on or off.

**Fields:**
```json
{
  "type": "bypass_human_toggled",
  "bypass_human": true,          // New bypass state
  "timestamp": 1234567890.123
}
```

**Frontend Action:**
- Set `bypassHuman = bypass_human`
- Update bypass toggle button appearance
  - `true`: Orange with "Bypass: ON"
  - `false`: Gray with "Bypass: OFF"

---

#### 6. ping

Keepalive ping sent by server every 30 seconds.

**Fields:**
```json
{
  "type": "ping",
  "timestamp": 1234567890.123
}
```

**Frontend Action:**
- Ignore (used to keep connection alive and detect dead connections)
- Most WebSocket libraries handle this automatically

---

## Error Responses

All endpoints may return these common errors:

### 404 Not Found
```json
{
  "detail": "No active discussion"
}
```

**Cause:** Discussion not started or already ended

**Solution:** Start a discussion first via `/api/discussion/configure` and `/api/control/resume`

---

### 409 Conflict
```json
{
  "detail": "Not currently waiting for human input"
}
```

**Cause:** Attempted human action when not human's turn

**Solution:** Check `waiting_on_human` field in `/api/discussion/status` before action

---

### 400 Bad Request
```json
{
  "detail": "Empty responses not allowed"
}
```

**Cause:** Submitted empty response when `allow_empty_submissions: false`

**Solution:** Provide non-empty response text

---

### 500 Internal Server Error
```json
{
  "detail": "Internal server error message"
}
```

**Cause:** Unexpected backend error

**Solution:** Check orchestrator logs for details

---

## State Machine

Human turn state transitions:

```
┌─────────────────┐
│  Discussion     │
│  Running        │
│  (AI turns)     │
└────────┬────────┘
         │
         │ Human's turn in rotation
         ▼
┌─────────────────┐
│  Waiting on     │◄─── waiting_on_human: true
│  Human          │     pending_turn_participant: "Human"
│  (Timer starts) │
└────────┬────────┘
         │
         │ One of three events:
         │
         ├─► Submit ───────┐
         │                  │
         ├─► Skip ──────────┤
         │                  │
         └─► Timeout ───────┤
                            │
                            ▼
                   ┌─────────────────┐
                   │  Turn Recorded  │
                   │  waiting_on_human: false
                   │  Advance to next│
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Discussion     │
                   │  Running        │
                   │  (Next speaker) │
                   └─────────────────┘
```

## Rate Limiting

No rate limiting currently implemented. API endpoints can be called as frequently as needed.

**Note:** Rapid repeated actions (e.g., clicking Submit 10 times) protected by `humanActionPending` flag in frontend.

## Authentication

No authentication currently required. All endpoints publicly accessible on localhost.

**Security Note:** Do not expose orchestrator API to untrusted networks without adding authentication.

## CORS

CORS enabled for frontend development:
- Default frontend: `http://localhost:9101`
- Configurable via environment variable

## API Versioning

Current version: **v1** (implicit, no version in URL)

Future versions may introduce `/api/v2/` prefix if breaking changes needed.

## Testing Endpoints

### cURL Examples

**Start a discussion with Human:**
```bash
# Configure discussion
curl -X POST http://localhost:9100/api/discussion/configure \
  -H "Content-Type: application/json" \
  -d '{
    "discussion_topic": "Test human participation",
    "max_turns": 5,
    "starting_model": "claude"
  }'

# Start sessions (Human filtered automatically)
curl -X POST http://localhost:9100/api/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_directory": "/home/user/project",
    "models": ["claude", "human"]
  }'

# Resume discussion
curl -X POST http://localhost:9100/api/control/resume
```

**Monitor status:**
```bash
# Poll status every 2 seconds
watch -n 2 'curl -s http://localhost:9100/api/discussion/status | jq .'
```

**Submit human response:**
```bash
curl -X POST http://localhost:9100/api/discussion/human/submit \
  -H "Content-Type: application/json" \
  -d '{"response": "This looks good to me"}'
```

**Skip turn:**
```bash
curl -X POST http://localhost:9100/api/discussion/human/skip
```

**Toggle bypass:**
```bash
curl -X POST http://localhost:9100/api/discussion/human/bypass/toggle
```

### Python Examples

```python
import requests
import json

BASE_URL = "http://localhost:9100"

# Submit human response
def submit_human_response(text):
    response = requests.post(
        f"{BASE_URL}/api/discussion/human/submit",
        json={"response": text}
    )
    return response.json()

# Skip human turn
def skip_human_turn():
    response = requests.post(f"{BASE_URL}/api/discussion/human/skip")
    return response.json()

# Toggle bypass
def toggle_bypass():
    response = requests.post(f"{BASE_URL}/api/discussion/human/bypass/toggle")
    return response.json()

# Get status
def get_status():
    response = requests.get(f"{BASE_URL}/api/discussion/status")
    return response.json()

# Check if waiting on human
status = get_status()
if status.get("waiting_on_human"):
    print(f"It's {status['pending_turn_participant']}'s turn!")
    # Submit response
    result = submit_human_response("I agree with this approach")
    print(f"Submitted turn {result['turn']}")
```

### WebSocket Testing (Python)

```python
import asyncio
import websockets
import json

async def listen_discussion_events():
    uri = "ws://localhost:9100/ws/discussion/events"

    async with websockets.connect(uri) as websocket:
        print("Connected to discussion events")

        async for message in websocket:
            data = json.loads(message)
            event_type = data.get("type")

            if event_type == "human_turn_started":
                print(f"Human turn started: {data['speaker']} (turn {data['turn']})")
            elif event_type == "human_turn_completed":
                print(f"Human turn completed: {data['speaker']}")
            elif event_type == "human_turn_timeout":
                print(f"Human turn timeout: {data['speaker']} after {data['elapsed_seconds']}s")
            elif event_type == "ping":
                print("Received keepalive ping")

# Run listener
asyncio.run(listen_discussion_events())
```

## Related Documentation

- [Overview](./HumanInTheLoopDoc_Overview.md) - Feature description and workflows
- [Control Channel](./HumanInTheLoopDoc_Control_Channel.md) - Headless operation
- [Configuration](./HumanInTheLoopDoc_Configuration.md) - Config reference
