# Human In The Loop - Implementation Task List

This task list tracks the implementation of Human participant support in the Orchestrator system.

## Phase 1: Configuration & Data Models ✅ COMPLETE

- [x] **1.1** Add `human` block to `config.yaml`
  - [x] Add `turn_timeout: 300` (5 minutes)
  - [x] Add `allow_empty_submissions: false`
  - [x] Add `response_marker: "👤"`

- [x] **1.2** Update conversation state data structures
  - [x] Add `human` participant type to conversation manager
  - [x] Add `waiting_on_human` boolean flag (_waiting_on_human)
  - [x] Add `bypass_human` boolean toggle (_bypass_human)
  - [x] Add `pending_turn_participant` to track whose turn it is (_pending_turn_participant)
  - [x] Add `human_turn_started_at` for timeout tracking (_human_turn_started_at)
  - [x] Ensure human participant has no controller object (metadata: has_controller=False)
  - [x] Participant metadata detection logic (case-insensitive "human" → type="human")

**Implementation Notes:**
- Committed in de119c8
- Config validated and loads correctly
- ConversationManager tested with human-only and mixed participants
- All Phase 1 tests passing

## Phase 2: Backend - Conversation Logic ✅ COMPLETE (except 2.6 deferred)

- [x] **2.1** Extend `ConversationManager.determine_next_speaker()`
  - [x] Include human in round-robin rotation when enabled (checks metadata type="human")
  - [x] Skip human when `bypass_human` is true
  - [x] Handle human timeout logic (waiting loop with timeout detection)
  - [x] Set `waiting_on_human` flag when human turn begins

- [x] **2.2** Update loop detection
  - [x] Exclude human turns from loop detection logic (check metadata in _update_loop_state)
  - [x] Verify loop detection still works correctly with human in rotation

- [x] **2.3** Update completion detection
  - [x] Decide whether human completion signals count toward consensus (YES - counts same as AI)
  - [x] Document the decision in code comments

- [x] **2.4** Add human turn timeout handling ✅ COMPLETE
  - [x] Implement timeout timer when human turn starts (_human_turn_started_at timestamp)
  - [x] Timeout detection in wait loop (elapsed time check)
  - [x] Log timeout events clearly
  - [x] Auto-skip human turn on timeout (calls _record_human_skip() with timeout=True)
  - [ ] Emit timeout event via WebSocket (deferred to Phase 4)

- [x] **2.5** Implement human turn recording and rendering ✅ COMPLETE
  - [x] Use `response_marker: "👤"` when recording human turns to history
  - [x] Ensure human participant name/type is clearly marked in turn records (metadata: human_turn=True)
  - [x] Backend should tag human turns distinctly for frontend rendering
  - Note: Implemented in Phase 3 via submit/skip endpoints and _record_human_skip() helper

- [ ] **2.6** Add state persistence for human turns (DEFERRED to later)
  - [ ] Persist `waiting_on_human` flag (survives orchestrator restart)
  - [ ] Persist `pending_turn_participant` (recovers whose turn it is)
  - [ ] Persist human turn timeout start time (can resume timeout after restart)
  - [ ] Reset `bypass_human` to false when session ends
  - [ ] Ensure ContextManager saves/restores these fields

**Implementation Notes:**
- Committed in 3a197f7 (initial), ac48dcf (waiting loop fix), 6a99284 (timeout recording fix)
- Core turn rotation works: human included in round-robin, bypass respected
- Wait loop implemented: polls every 0.5s, checks timeout/stop/control commands
- Timeout auto-skip complete: calls _record_human_skip() helper to record turn and increment counter
- _record_human_skip() helper used by both timeout and skip endpoint (eliminates duplication)
- State persistence deferred as it requires context manager integration

## Phase 3: Backend - API Endpoints ✅ COMPLETE

- [x] **3.1** Create new API endpoints in `web_api.py`
  - [x] `POST /api/discussion/human/submit` - Submit human response
    - [x] Validate non-empty if `allow_empty_submissions: false`
    - [x] Record turn in conversation history
    - [x] Clear `waiting_on_human` flag
    - [x] Advance to next speaker (turn_counter incremented in submit logic)
    - [x] Return success/error response
  - [x] `POST /api/discussion/human/skip` - Skip human turn
    - [x] Record skipped turn in history (uses _record_human_skip helper)
    - [x] Clear `waiting_on_human` flag
    - [x] Advance to next speaker (turn_counter incremented in helper)
    - [x] Skip counter tracked via metadata (skipped flag in turn record)
  - [x] `POST /api/discussion/human/bypass/toggle` - Toggle bypass state
    - [x] Set/unset `bypass_human` flag
    - [ ] Emit state change event (deferred to Phase 4 WebSocket)

- [x] **3.2** Update existing `/api/discussion/status` endpoint
  - [x] Add `waiting_on_human` to response
  - [x] Add `bypass_human` to response
  - [x] Add `pending_turn_participant` to response
  - [x] Add `human_enabled` (whether human is in participant list)

- [x] **3.3** Update `/api/sessions/start` endpoint
  - [x] Accept "human" in models list
  - [x] Validate: grey out logic if only "human" selected (frontend responsibility)
  - [x] Initialize human participant state (registers with None controller)

**Implementation Notes:**
- Committed in 8ef0523 (initial), 6a99284 (timeout recording refactor)
- All three endpoints functional: submit validates empty responses, records with 👤 marker
- Skip endpoint refactored to use _record_human_skip() helper (matches timeout behavior)
- Bypass toggle endpoint working (WebSocket event deferred to Phase 4)
- Status endpoint returns all human turn fields for real-time UI updates
- Sessions can start with "human" in models list (registered with None controller)
- normalize_model_names() updated to allow "human" as valid participant

## Phase 4: Backend - WebSocket Events ✅ COMPLETE

- [x] **4.1** Add new WebSocket event types
  - [x] `human_turn_started` - Emitted when human turn begins
  - [x] `human_turn_completed` - Emitted after successful submit
  - [x] `human_turn_skipped` - Emitted after skip
  - [x] `human_turn_timeout` - Emitted when turn times out
  - [x] `bypass_human_toggled` - Emitted when bypass state changes

- [x] **4.2** Ensure real-time state synchronization
  - [x] Created DiscussionEventManager for connection management
  - [x] Handle race conditions (broadcast errors logged but don't block flow)
  - [ ] Test WebSocket delivery under various network conditions (deferred to Phase 8 testing)

**Implementation Notes:**
- Committed in a4d38b5
- Created DiscussionEventManager class with connect/disconnect/broadcast methods
- Added /ws/discussion/events WebSocket endpoint for client subscriptions
- All human turn endpoints emit appropriate events (submit, skip, bypass toggle)
- Conversation manager emits human_turn_started and human_turn_timeout events
- broadcast_event_sync() helper handles thread-safe broadcasting from sync code
- All events include timestamp and relevant context fields (speaker, turn, etc.)
- Broadcast errors are logged but don't interrupt discussion flow
- WebSocket disconnections handled gracefully with automatic cleanup

## Phase 5: Backend - Control Channel ✅ COMPLETE

- [x] **5.1** Add control channel commands
  - [x] `HUMAN_SUBMIT <text>` - Submit human turn via control channel
  - [x] `HUMAN_SKIP` - Skip human turn via control channel
  - [ ] Document commands in `docs/Human_Control_Guide.md` (deferred to Phase 9)

- [x] **5.2** Control channel integration
  - [x] Reuse same backend logic as API endpoints
  - [x] Log control channel human submissions
  - [x] Commands added to control channel command history (via existing infrastructure)

**Implementation Notes:**
- Committed in 4b5b75a
- Added HUMAN_SUBMIT and HUMAN_SKIP handlers to _handle_control_command()
- HUMAN_SUBMIT reconstructs response text from space-separated args
- Both commands validate state (waiting_on_human, pending_turn_participant)
- Reuse existing turn recording logic (_record_human_skip helper for skip)
- Set via_control_channel metadata flag for tracking submission source
- Emit WebSocket events with via_control_channel flag
- Status errors set on validation failure, cleared on success
- All operations logged for audit trail
- Usage: `echo "HUMAN_SUBMIT response text" > /tmp/orchestrator_control`
- Documentation of commands deferred to Phase 9 (will be added to docs/)

## Phase 6: Frontend - Model Selection UI ✅ PARTIAL (6.1 complete, 6.2 deferred to Phase 7)

- [x] **6.1** Update model selection interface
  - [x] Add "Human" checkbox to model selector (added to allConversations)
  - [x] Default ALL models to unchecked (changed activeModels initial state to [])
  - [x] Disable "Start Models" button if only "Human" is selected
  - [x] Show helpful tooltip/message when only Human is selected
  - [x] Prevent Human from being starting_model in discussions
  - [x] Filter Human from conversation windows display (no tmux session)

- [ ] **6.2** Add bypass toggle to active session UI (deferred to Phase 7)
  - [ ] Add "Bypass Human" toggle/checkbox
  - [ ] Only show when Human is in participant list
  - [ ] Only enable when discussion is running
  - [ ] Wire to `/api/discussion/human/bypass/toggle` endpoint

**Implementation Notes:**
- Committed in 031c081
- Added Human as 5th conversation (id: 5, title: 'Human')
- Default activeModels changed from all selected to empty array
- "Start Models" button disabled with tooltip when only Human selected
- configureDiscussion() ensures starting_model is never Human
- Human filtered from activeConversations (no window to display)
- Bypass toggle deferred to Phase 7 where human turn UI is implemented

## Phase 7: Frontend - Human Turn UI ✅ COMPLETE (except 7.5 deferred)

- [x] **7.1** Implement conditional rendering for human turns
  - [x] Detect `waiting_on_human === true` from status/WebSocket
  - [x] Show "Your Turn" banner (prominent, clear visual indicator)
  - [x] Swap button set from "Send to model(s)" to "Submit" + "Skip"
  - [x] Disable "Send to model(s)" during human turn
  - [x] Re-enable "Send to model(s)" after turn completes

- [x] **7.2** Wire Submit button
  - [x] Call `POST /api/discussion/human/submit` with textarea content
  - [x] Clear textarea on successful submit
  - [x] Preserve textarea content on error
  - [x] Show error toast/message if submission fails
  - [x] Disable button during API call (prevent double-submit)

- [x] **7.3** Wire Skip button
  - [x] Call `POST /api/discussion/human/skip`
  - [x] Clear textarea (optional: ask user to confirm if text is present)
  - [x] Show confirmation if text would be discarded
  - [x] Disable button during API call

- [x] **7.4** Handle WebSocket events
  - [x] Listen for `human_turn_started` → update UI state
  - [x] Listen for `human_turn_completed` → return to normal mode
  - [x] Listen for `human_turn_skipped` → return to normal mode
  - [x] Listen for `human_turn_timeout` → show timeout notification
  - [x] Listen for `bypass_human_toggled` → update toggle state

- [ ] **7.5** Render human turns in conversation history (DEFERRED)
  - [ ] Display human turns with `👤` icon/marker
  - [ ] Visually distinguish human turns from AI turns in transcript
  - [ ] Ensure participant name shows as "Human" or similar
  - Note: Deferred as conversation history rendering requires additional API endpoint work

- [x] **7.6** UI reload resilience (anti-desync)
  - [x] On component mount/reload, fetch current discussion status
  - [x] If `waiting_on_human === true`, immediately show human turn UI
  - [x] Restore correct button set and banner on page refresh
  - [x] Test: refresh browser during human turn → UI recovers correctly

**Implementation Notes:**
- Committed in 1c69f87
- PromptInput.tsx fully refactored with human turn handlers and conditional UI
- App.tsx has WebSocket connection to /ws/discussion/events for real-time updates
- Handler functions for submit, skip, and bypass toggle all working
- Status polling extracts human turn fields and updates UI state
- UI resilience achieved via status polling (restores state on page refresh)
- Submit preserves text on error, skip confirms if text present
- Banner shows gradient background with "Your Turn!" message
- Bypass toggle shows when human enabled but not waiting (orange when ON)
- All WebSocket events handled: human_turn_started, completed, skipped, timeout, bypass_toggled
- Frontend builds successfully with no TypeScript errors

## Phase 8: Testing

- [ ] **8.1** Unit tests - Backend
  - [ ] Test `determine_next_speaker()` with human in rotation
  - [ ] Test `determine_next_speaker()` with human bypassed
  - [ ] Test human turn timeout logic
  - [ ] Test empty submission rejection
  - [ ] Test loop detection ignores human turns
  - [ ] Test max_turns includes human turns in count
  - [ ] Test state persistence (save/restore `waiting_on_human`, `pending_turn_participant`)
  - [ ] Test bypass state resets on session end
  - [ ] Test human turn recording uses correct response_marker

- [ ] **8.2** Unit tests - Frontend
  - [ ] Test model selection validation (only Human selected)
  - [ ] Test UI mode switching (normal ↔ human turn)
  - [ ] Test button state changes
  - [ ] Test bypass toggle functionality

- [ ] **8.3** Integration tests
  - [ ] Start session with Human enabled
  - [ ] Human submits response → advances to next model
  - [ ] Human skips turn → advances to next model
  - [ ] Human turn times out → auto-skips and advances
  - [ ] Bypass toggle skips human turns
  - [ ] "Send to model(s)" injection still works during AI turns
  - [ ] Human turn counted in max_turns limit
  - [ ] Control channel `human_submit` and `human_skip` work

- [ ] **8.4** Edge case testing
  - [ ] Human selected but never submits/skips (timeout)
  - [ ] Submit empty text (should be rejected)
  - [ ] Multiple rapid skip operations
  - [ ] Race condition: submit and timeout occur simultaneously
  - [ ] Network error during submit (textarea preserved)
  - [ ] Session with only Human selected (prevented by UI)
  - [ ] WebSocket disconnect/reconnect during human turn
  - [ ] Browser refresh during human turn (UI recovers)
  - [ ] Orchestrator restart during human turn (state persists)
  - [ ] Session end clears bypass state correctly

## Phase 9: Documentation

- [ ] **9.1** Update user-facing documentation
  - [ ] Add Human participant section to `docs/README.md`
  - [ ] Update `docs/onboarding.md` with Human feature
  - [ ] Add Human turn workflow to `docs/architecture.md`
  - [ ] Update `README.md` with Human feature description

- [ ] **9.2** Update API documentation
  - [ ] Add new endpoints to `docs/backend/api_reference.md`
  - [ ] Document WebSocket events
  - [ ] Update OpenAPI schema (`docs/openapi.json`)
  - [ ] Run `scripts/generate_openapi.py` to regenerate schema

- [ ] **9.3** Update control channel documentation
  - [ ] Add `human_submit` and `human_skip` to `docs/Human_Control_Guide.md`
  - [ ] Add examples of headless operation with Human participant

- [ ] **9.4** Configuration documentation
  - [ ] Document `human` config block in relevant guides
  - [ ] Add config examples to documentation

## Phase 10: Finalization

- [ ] **10.1** Code review
  - [ ] Review all changes for consistency
  - [ ] Ensure error handling is comprehensive
  - [ ] Verify logging is adequate
  - [ ] Check for race conditions

- [ ] **10.2** Performance testing
  - [ ] Test with multiple concurrent human turn waits
  - [ ] Verify WebSocket event delivery performance
  - [ ] Check timeout precision

- [ ] **10.3** User acceptance testing
  - [ ] Don tests the feature end-to-end
  - [ ] Verify UI/UX is intuitive
  - [ ] Check all edge cases in real usage

- [ ] **10.4** Final tasks
  - [ ] Update `Tasks.md` to mark HitL feature complete
  - [ ] Post completion summary to `MessageBoard.md`
  - [ ] Commit all changes with descriptive message
  - [ ] Update version/changelog if applicable

---

## Notes

- **Priority order**: Follow phases 1-10 in sequence
- **Testing**: Don will run tests in `/home/dgray/Projects/TestOrch` worktree
- **Virtual environment**: Activate `venv` before running any Python code
- **Model selection default**: All models (including Human) start unchecked
- **Turn timeout**: Default 300 seconds (5 minutes), configurable per session
- **Empty submissions**: Rejected by default, configurable in config.yaml

## Dependencies

- Existing WebSocket infrastructure in `web_api.py`
- Existing control channel in `control_channel.py`
- Existing conversation manager turn logic
- React frontend with state management

## Success Criteria

- [ ] Human can be selected alongside AI models
- [ ] Human participates in round-robin turn rotation
- [ ] Human turns have clear UI indicators and controls
- [ ] Human turns can be submitted, skipped, or timeout
- [ ] Bypass toggle allows temporarily skipping human turns
- [ ] All existing "Send to model(s)" functionality preserved
- [ ] Control channel supports human turn operations
- [ ] Full test coverage with all edge cases handled
- [ ] Documentation complete and accurate
