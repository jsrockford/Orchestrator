# Web UI Integration Tasks

This document tracks the implementation of the web UI integration with the existing orchestrator system.

**Project Goal**: Connect the React/FastAPI web frontend to the tmux-based orchestrator backend, enabling browser-based control and monitoring of AI model sessions.

**Architecture Decision**: Keep tmux foundation, build WebSocket/REST bridge layer for web UI integration.

**Key Architectural Refinement**: Integrate FastAPI server INTO the orchestrator application rather than running as a separate process. This provides direct access to live controller instances and orchestrator state, eliminating the need for duplicate instances or sys.path hacks.

---

## Phase 0: Repository Setup & Architecture Integration

**Goal**: Set up feature branch and integrate FastAPI into orchestrator architecture.

- [x] **Task 0.1**: Create feature branch
  - [x] Create `feature/web-integration` branch from current main/development
  - [x] Verify branch is active before making changes
  - [x] Document branch purpose in commit message

- [x] **Task 0.2**: Create web API module
  - [x] Create new file: `src/orchestrator/web_api.py`
  - [x] Implement `create_app(orchestrator: DevelopmentTeamOrchestrator)` factory function
  - [x] FastAPI app should receive orchestrator instance as parameter
  - [x] Add CORS middleware for frontend communication
  - [x] Add basic health check endpoint: `GET /api/health`

- [x] **Task 0.3**: Integrate FastAPI into orchestrator
  - [x] Modify `src/orchestrator/orchestrator.py`:
    - [x] Add `api_server` attribute to `DevelopmentTeamOrchestrator.__init__()`
    - [x] Add `start_api_server(host, port)` method
    - [x] Method should run uvicorn in separate thread/async task
    - [x] Add `stop_api_server()` method for cleanup
  - [x] Update orchestrator startup script to optionally start API server
  - [x] Test that API server starts without errors

- [x] **Task 0.4**: Set up pytest infrastructure for API testing
  - [x] Create `tests/test_web_api.py`
  - [x] Add pytest fixtures for:
    - [x] Mock orchestrator instance
    - [x] Mock controller instances
    - [x] Mock FIFO pipe (using tempfile or mock)
    - [x] FastAPI TestClient
  - [x] Write basic smoke test (health endpoint)

---

## Phase 1: Control Plane (UI Buttons → Backend Actions)

**Goal**: Enable UI buttons to send commands to tmux sessions via the existing control channel.

### Backend Tasks

- [x] **Task 1.1**: Add control endpoint infrastructure to `src/orchestrator/web_api.py`
  - [x] Add helper function `write_to_control_channel(command: str)` that writes to `/tmp/orchestrator_control` FIFO
  - [x] Add error handling for FIFO not found/blocked (return 503 Service Unavailable)
  - [x] Add retry logic for FIFO write failures (3 attempts with 100ms delay)
  - [x] Test FIFO write with orchestrator_control.sh running

- [x] **Task 1.2**: Implement REST endpoints for control actions in `web_api.py`
  - [x] `POST /api/control/pause` - Send PAUSE to control channel
  - [x] `POST /api/control/resume` - Send RESUME to control channel
  - [x] `POST /api/control/{model_name}/key/{key_name}` - Send KEY command (e.g., Up, Down, Enter, Escape)
  - [x] `GET /api/control/status` - Query orchestrator state (read from orchestrator.conversation_manager or status file)
  - [x] Add request validation (valid model names, valid key names)
  - [x] Add error responses (404 for invalid model, 503 for FIFO unavailable)
  - [x] Added instruction file endpoints (GET/POST `/api/instructions/{model_name}`)
  - [x] Added filesystem endpoints (POST `/api/fs/browse`, POST `/api/fs/create-folder`)

- [x] **Task 1.3**: Write pytest tests for control endpoints
  - [x] Test pause endpoint sends "PAUSE" to mock FIFO
  - [x] Test resume endpoint sends "RESUME" to mock FIFO
  - [x] Test key endpoint formats command correctly: "KEY {model} {key}"
  - [x] Test error handling: invalid model name returns 404
  - [x] Test error handling: FIFO unavailable returns 503
  - [x] Run tests: `pytest tests/test_web_api.py -v`

- [x] **Task 1.4**: Integration test with live orchestrator
  - [x] Start orchestrator with control channel active
  - [x] Start integrated API server
  - [x] Test pause endpoint with curl/Postman (tested via UI, not formally via curl)
  - [x] Test resume endpoint (tested via UI, not formally via curl)
  - [ ] Test key commands for each model (tested via UI for some models)
  - [x] Verify commands appear in control channel logs
  - [x] Monitor `/tmp/orchestrator_control` FIFO with `tail -f logs/control_channel_history.log`
  - [x] Verified all 9 endpoints appear in `/docs`
  - [x] Tested instruction file GET/POST endpoints (via UI)
  - [x] Tested filesystem browse and create-folder endpoints (via UI)

### Frontend Tasks

- [x] **Task 1.5**: Update `ConversationWindow.tsx` to call control endpoints
  - [x] Modify `handleControlAction` to make API calls instead of console.log
  - [x] Map button actions to endpoint URLs:
    - [x] Esc → `POST /api/control/pause`
    - [x] Rsm → `POST /api/control/resume`
    - [x] Up → `POST /api/control/{model}/key/Up`
    - [x] Down → `POST /api/control/{model}/key/Down`
    - [x] Enter → `POST /api/control/{model}/key/Enter`
  - [x] Add error handling (try/catch blocks in App.tsx)
  - [ ] Add user feedback (toast notifications or UI error messages - currently only console warnings)
  - [x] Pass model name from conversation prop to API calls

- [ ] **Task 1.6**: Update `App.tsx` for global controls
  - [ ] Wire Start/Stop Project buttons to orchestrator lifecycle (currently only updates local state, see App.tsx:112,118 comments)
  - [x] Add visual feedback for button presses
  - [x] Handle disabled states appropriately

- [ ] **Task 1.7**: Test control flow end-to-end
  - [x] Start orchestrator with integrated API server
  - [x] Start frontend dev server
  - [ ] Click each button in UI, verify corresponding action in tmux sessions (partially tested)
  - [ ] Test with multiple models active (not fully verified)
  - [ ] Verify control channel history log shows correct commands (not formally verified)

---

## Phase 2: Data Plane (Tmux Sessions → UI Display)

**Goal**: Stream tmux session output to frontend conversation windows in real-time.

### Backend Tasks

- [ ] **Task 2.1**: Implement WebSocket endpoint for session streaming in `src/orchestrator/web_api.py`
  - [ ] Add WebSocket route: `GET /ws/session/{model_name}`
  - [ ] Accept WebSocket connection
  - [ ] Validate model_name exists in orchestrator.controllers
  - [ ] Get controller instance: `controller = orchestrator.controllers.get(model_name.lower())`
  - [ ] Create async polling loop (500ms interval)
  - [ ] Call `controller.capture_scrollback(lines=1000)` each iteration
  - [ ] Handle session not found errors (controller.session_exists())
  - [ ] Handle disconnection and cleanup

- [ ] **Task 2.2**: Implement diff algorithm for efficient updates
  - [ ] Track last output per WebSocket connection (use dict keyed by connection)
  - [ ] Compare current output with last output
  - [ ] Calculate diff: send only new lines that appeared since last check
  - [ ] Send updates as JSON: `{"type": "output", "content": "new lines...", "timestamp": "..."}`
  - [ ] Optimize: if output unchanged, don't send message (reduce bandwidth)

- [ ] **Task 2.3**: Add orchestrator state to WebSocket messages
  - [ ] Access orchestrator state directly: `orchestrator.conversation_manager.human_control_mode`
  - [ ] Or read from status file: `/tmp/orchestrator_status.txt`
  - [ ] Include state in messages: `{"type": "status", "state": "RUNNING|PAUSED", "active_model": "..."}`
  - [ ] Send status updates periodically (every 5s) or on state change detection

- [ ] **Task 2.4**: Implement in-memory buffer cache (optional optimization)
  - [ ] Store last N lines (e.g., 2000) per session in memory
  - [ ] Send full buffer to new WebSocket connections (initial sync)
  - [ ] Subsequent updates send only diffs
  - [ ] Maintain buffer across reconnections (client can request replay)

- [ ] **Task 2.5**: Write pytest tests for WebSocket streaming
  - [ ] Test WebSocket connection accepts successfully
  - [ ] Test polling loop fetches controller output
  - [ ] Test diff detection sends only new content
  - [ ] Test invalid model_name returns error and closes connection
  - [ ] Test session not found scenario (controller exists but session dead)
  - [ ] Use pytest-asyncio for async WebSocket testing

- [ ] **Task 2.6**: Integration test WebSocket streaming with live session
  - [ ] Start a single tmux session (e.g., claude)
  - [ ] Start orchestrator with integrated API server
  - [ ] Connect WebSocket client (browser console or wscat tool)
  - [ ] Send command to tmux session, verify output appears in WebSocket
  - [ ] Test reconnection behavior (disconnect and reconnect)
  - [ ] Check performance with multiple concurrent clients (4 connections)

### Frontend Tasks

- [ ] **Task 2.7**: Add WebSocket client to `ConversationWindow.tsx`
  - [ ] Create WebSocket connection on component mount: `new WebSocket("ws://localhost:8000/ws/session/{model}")`
  - [ ] Handle `onmessage` event: append new content to buffer state
  - [ ] Handle `onopen`, `onerror`, `onclose` events with logging/feedback
  - [ ] Implement reconnection logic with exponential backoff

- [ ] **Task 2.8**: Update UI to display streaming content
  - [ ] Replace hardcoded `sampleOutput` with state variable `outputBuffer`
  - [ ] Append incoming messages to `outputBuffer`
  - [ ] Render buffer in `<pre>` tag with proper formatting
  - [ ] Apply OutputParser or ANSI-to-HTML conversion if needed

- [ ] **Task 2.9**: Implement scroll management
  - [ ] Detect if user is scrolled to bottom (auto-scroll mode)
  - [ ] Only auto-scroll if user hasn't manually scrolled up
  - [ ] Add "Scroll to Bottom" button when user scrolls up
  - [ ] Preserve scroll position when new content arrives

- [ ] **Task 2.10**: Handle orchestrator state updates
  - [ ] Update UI based on received status messages
  - [ ] Disable "Resume" button when state is RUNNING
  - [ ] Disable "Pause" button when state is PAUSED
  - [ ] Show visual indicators (header color change?) based on state

- [ ] **Task 2.11**: Test streaming display end-to-end
  - [ ] Start orchestrator with active conversation
  - [ ] Open web UI and verify output appears
  - [ ] Verify auto-scroll works correctly
  - [ ] Test manual scrolling and "Scroll to Bottom" button
  - [ ] Test with multiple model windows simultaneously

---

## Phase 3: Enhancements & Polish (Optional)

**Goal**: Improve reliability, performance, and user experience.

### Backend Enhancements

- [ ] **Task 3.1**: Add REST endpoint for historical output
  - [ ] `GET /api/history/{model_name}?lines=1000` - Return last N lines of output
  - [ ] Use controller.capture_scrollback() to fetch data
  - [ ] Cache result to reduce tmux polling

- [ ] **Task 3.2**: Implement persistent logging
  - [ ] Parallel log output to disk: `/var/log/orchestrator/{model_name}.log`
  - [ ] Add log rotation (size-based or time-based)
  - [ ] Serve logs via history endpoint as fallback

- [ ] **Task 3.3**: Add authentication/authorization
  - [ ] Add API key or session-based auth
  - [ ] Protect control endpoints from unauthorized access
  - [ ] Add rate limiting to prevent abuse

- [ ] **Task 3.4**: Performance optimization
  - [ ] Benchmark capture_scrollback() performance with 4 concurrent sessions
  - [ ] Adjust polling interval based on activity level
  - [ ] Implement smart diffing (only poll when sessions are active)
  - [ ] Consider pipe-pane approach if polling overhead is excessive

### Frontend Enhancements

- [ ] **Task 3.5**: Add ANSI color/formatting support
  - [ ] Install ansi-to-html library or similar
  - [ ] Render colored output in conversation windows
  - [ ] Preserve formatting for code blocks and UI elements

- [ ] **Task 3.6**: Add search/filter functionality
  - [ ] Search within conversation history
  - [ ] Filter by message type or timestamp
  - [ ] Highlight search results

- [ ] **Task 3.7**: Add conversation export
  - [ ] Export conversation to text file
  - [ ] Export to JSON with metadata
  - [ ] Copy to clipboard functionality

- [ ] **Task 3.8**: Improve error handling and feedback
  - [ ] Toast notifications for errors
  - [ ] Reconnection status indicator
  - [ ] Session health status in UI

---

## Testing & Validation

### Integration Tests

- [ ] **Test 1**: Full workflow with single model
  - Start backend, frontend, orchestrator
  - Activate one model in UI
  - Send prompt via orchestrator
  - Verify output streams to UI
  - Test pause/resume controls
  - Test keyboard controls (arrows, enter)

- [ ] **Test 2**: Multi-model orchestration
  - Activate all 4 models
  - Start orchestrated discussion
  - Verify all windows stream output correctly
  - Test independent control of each model
  - Verify no cross-talk between sessions

- [ ] **Test 3**: Edge cases
  - Test with session not running (should show error)
  - Test rapid button clicks (no command queueing issues)
  - Test long scrollback (>2000 lines)
  - Test frontend reload during active session
  - Test backend restart while frontend connected
  - Test network interruption and reconnection

### Performance Tests

- [ ] **Test 4**: Measure latency
  - Measure time from tmux output to UI display
  - Target: <1 second end-to-end latency
  - Test with 1, 2, 4 concurrent sessions

- [ ] **Test 5**: Resource usage
  - Monitor backend CPU/memory with 4 active sessions
  - Monitor frontend memory over 1-hour session
  - Check for memory leaks in WebSocket connections

---

## Documentation

- [ ] **Doc 1**: Update README with web UI setup instructions
  - How to start backend server
  - How to start frontend dev server
  - How to access web UI
  - Troubleshooting common issues

- [ ] **Doc 2**: Create Web UI User Guide
  - Overview of UI layout
  - How to use control buttons
  - How to interpret status indicators
  - Keyboard shortcuts (if implemented)

- [ ] **Doc 3**: Update API documentation
  - Document all REST endpoints
  - Document WebSocket protocol
  - Include example requests/responses

---

## Dependencies

### Python Dependencies (backend)
- `fastapi` (already installed)
- `uvicorn` (already installed)
- `websockets` (included with FastAPI, no separate install needed)
- `pytest-asyncio` (for testing WebSocket endpoints)

### Node Dependencies (frontend)
- None required (browser native WebSocket API)
- Optional: `ansi-to-html` for colored output rendering

### System Dependencies
- Orchestrator running with control channel enabled
- Tmux sessions for AI models (claude, gemini, codex, qwen)
- Named pipe at `/tmp/orchestrator_control` (created by orchestrator)
- Git branch: `feature/web-integration`

---

## Notes

**IMPORTANT Architecture Changes:**
- FastAPI is now **integrated INTO the orchestrator**, not a separate process
- The orchestrator starts the API server when initialized
- API endpoints have direct access to `orchestrator.controllers` (single source of truth)
- No more `sys.path` hacks or duplicate controller instances needed

**Development Workflow:**
- All code changes should be in `/home/dgray/Projects/Orchestrator` (NOT TestOrch)
- Work in `feature/web-integration` branch
- Activate virtual environment: `source venv/bin/activate`
- Main API code goes in: `src/orchestrator/web_api.py`
- Orchestrator integration code goes in: `src/orchestrator/orchestrator.py`
- Tests go in: `tests/test_web_api.py`

**Running the System:**
- Start orchestrator with API server enabled (method to be added in Phase 0)
- Frontend dev server: `cd frontend && npm run dev`
- Run tests: `pytest tests/test_web_api.py -v`
- Monitor control channel: `tail -f logs/control_channel_history.log`

**Testing Strategy:**
- Test incrementally: complete and validate each task before moving to next
- Write pytest tests for all API endpoints (Phase 1 and Phase 2)
- Test with live orchestrator after unit tests pass
- Validate frontend integration after backend is stable

---

## Success Criteria

- ✅ All UI buttons send correct commands to orchestrator
- ✅ All model conversation windows display real-time output
- ✅ Auto-scroll works correctly
- ✅ Manual scroll preserves position
- ✅ Pause/resume controls work reliably
- ✅ System handles multiple concurrent sessions
- ✅ Reconnection after disconnect works
- ✅ No noticeable lag (<1s) in output display
- ✅ User can control orchestrator entirely from web UI
- ✅ Manual tmux control still works (doesn't conflict with web UI)

---

**Last Updated**: 2025-11-05
**Status**: Planning Complete - Architecture Refined - Ready for Implementation
**Key Change**: FastAPI integrated into orchestrator for direct controller access
