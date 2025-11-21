# Human In The Loop - Implementation Task List

This task list tracks the implementation of Human participant support in the Orchestrator system.

## Phase 1: Configuration & Data Models

- [ ] **1.1** Add `human` block to `config.yaml`
  - [ ] Add `turn_timeout: 300` (5 minutes)
  - [ ] Add `allow_empty_submissions: false`
  - [ ] Add `response_marker: "👤"`

- [ ] **1.2** Update conversation state data structures
  - [ ] Add `human` participant type to conversation manager
  - [ ] Add `waiting_on_human` boolean flag
  - [ ] Add `bypass_human` boolean toggle
  - [ ] Add `pending_turn_participant` to track whose turn it is
  - [ ] Ensure human participant has no controller object (None/null)

## Phase 2: Backend - Conversation Logic

- [ ] **2.1** Extend `ConversationManager.determine_next_speaker()`
  - [ ] Include human in round-robin rotation when enabled
  - [ ] Skip human when `bypass_human` is true
  - [ ] Handle human timeout logic
  - [ ] Set `waiting_on_human` flag when human turn begins

- [ ] **2.2** Update loop detection
  - [ ] Exclude human turns from loop detection logic
  - [ ] Verify loop detection still works correctly with human in rotation

- [ ] **2.3** Update completion detection
  - [ ] Decide whether human completion signals count toward consensus
  - [ ] Document the decision in code comments

- [ ] **2.4** Add human turn timeout handling
  - [ ] Implement timeout timer when human turn starts
  - [ ] Auto-skip human turn on timeout
  - [ ] Log timeout events clearly
  - [ ] Emit timeout event via WebSocket

- [ ] **2.5** Implement human turn recording and rendering
  - [ ] Use `response_marker: "👤"` when recording human turns to history
  - [ ] Ensure human participant name/type is clearly marked in turn records
  - [ ] Backend should tag human turns distinctly for frontend rendering

- [ ] **2.6** Add state persistence for human turns
  - [ ] Persist `waiting_on_human` flag (survives orchestrator restart)
  - [ ] Persist `pending_turn_participant` (recovers whose turn it is)
  - [ ] Persist human turn timeout start time (can resume timeout after restart)
  - [ ] Reset `bypass_human` to false when session ends
  - [ ] Ensure ContextManager saves/restores these fields

## Phase 3: Backend - API Endpoints

- [ ] **3.1** Create new API endpoints in `web_api.py`
  - [ ] `POST /api/discussion/human/submit` - Submit human response
    - [ ] Validate non-empty if `allow_empty_submissions: false`
    - [ ] Record turn in conversation history
    - [ ] Clear `waiting_on_human` flag
    - [ ] Advance to next speaker
    - [ ] Return success/error response
  - [ ] `POST /api/discussion/human/skip` - Skip human turn
    - [ ] Record skipped turn in history
    - [ ] Clear `waiting_on_human` flag
    - [ ] Advance to next speaker
    - [ ] Increment skip counter (optional metric)
  - [ ] `POST /api/discussion/human/bypass/toggle` - Toggle bypass state
    - [ ] Set/unset `bypass_human` flag
    - [ ] Emit state change event

- [ ] **3.2** Update existing `/api/discussion/status` endpoint
  - [ ] Add `waiting_on_human` to response
  - [ ] Add `bypass_human` to response
  - [ ] Add `pending_turn_participant` to response
  - [ ] Add `human_enabled` (whether human is in participant list)

- [ ] **3.3** Update `/api/sessions/start` endpoint
  - [ ] Accept "human" in models list
  - [ ] Validate: grey out logic if only "human" selected (frontend responsibility)
  - [ ] Initialize human participant state

## Phase 4: Backend - WebSocket Events

- [ ] **4.1** Add new WebSocket event types
  - [ ] `human_turn_started` - Emitted when human turn begins
  - [ ] `human_turn_completed` - Emitted after successful submit
  - [ ] `human_turn_skipped` - Emitted after skip
  - [ ] `human_turn_timeout` - Emitted when turn times out
  - [ ] `bypass_human_toggled` - Emitted when bypass state changes

- [ ] **4.2** Ensure real-time state synchronization
  - [ ] Test WebSocket delivery under various network conditions
  - [ ] Handle race conditions (submit vs timeout)

## Phase 5: Backend - Control Channel

- [ ] **5.1** Add control channel commands
  - [ ] `human_submit <text>` - Submit human turn via control channel
  - [ ] `human_skip` - Skip human turn via control channel
  - [ ] Document commands in `docs/Human_Control_Guide.md`

- [ ] **5.2** Control channel integration
  - [ ] Reuse same backend logic as API endpoints
  - [ ] Log control channel human submissions
  - [ ] Add to control channel history

## Phase 6: Frontend - Model Selection UI

- [ ] **6.1** Update model selection interface
  - [ ] Add "Human" checkbox to model selector
  - [ ] Default ALL models to unchecked (not just Human)
  - [ ] Disable "Start Models" button if only "Human" is selected
  - [ ] Show helpful tooltip/message when only Human is selected

- [ ] **6.2** Add bypass toggle to active session UI
  - [ ] Add "Bypass Human" toggle/checkbox
  - [ ] Only show when Human is in participant list
  - [ ] Only enable when discussion is running
  - [ ] Wire to `/api/discussion/human/bypass/toggle` endpoint

## Phase 7: Frontend - Human Turn UI

- [ ] **7.1** Implement conditional rendering for human turns
  - [ ] Detect `waiting_on_human === true` from status/WebSocket
  - [ ] Show "Your Turn" banner (prominent, clear visual indicator)
  - [ ] Swap button set from "Send to model(s)" to "Submit" + "Skip"
  - [ ] Disable "Send to model(s)" during human turn
  - [ ] Re-enable "Send to model(s)" after turn completes

- [ ] **7.2** Wire Submit button
  - [ ] Call `POST /api/discussion/human/submit` with textarea content
  - [ ] Clear textarea on successful submit
  - [ ] Preserve textarea content on error
  - [ ] Show error toast/message if submission fails
  - [ ] Disable button during API call (prevent double-submit)

- [ ] **7.3** Wire Skip button
  - [ ] Call `POST /api/discussion/human/skip`
  - [ ] Clear textarea (optional: ask user to confirm if text is present)
  - [ ] Show confirmation if text would be discarded
  - [ ] Disable button during API call

- [ ] **7.4** Handle WebSocket events
  - [ ] Listen for `human_turn_started` → update UI state
  - [ ] Listen for `human_turn_completed` → return to normal mode
  - [ ] Listen for `human_turn_skipped` → return to normal mode
  - [ ] Listen for `human_turn_timeout` → show timeout notification
  - [ ] Listen for `bypass_human_toggled` → update toggle state

- [ ] **7.5** Render human turns in conversation history
  - [ ] Display human turns with `👤` icon/marker
  - [ ] Visually distinguish human turns from AI turns in transcript
  - [ ] Ensure participant name shows as "Human" or similar

- [ ] **7.6** UI reload resilience (anti-desync)
  - [ ] On component mount/reload, fetch current discussion status
  - [ ] If `waiting_on_human === true`, immediately show human turn UI
  - [ ] Restore correct button set and banner on page refresh
  - [ ] Test: refresh browser during human turn → UI recovers correctly

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
