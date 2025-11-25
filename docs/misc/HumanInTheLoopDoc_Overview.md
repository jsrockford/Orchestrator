# Human In The Loop - Feature Overview

## Introduction

The Human In The Loop (HitL) feature enables human participation in AI model discussions within the Orchestrator system. A human can be added as a participant alongside AI models (Claude, Codex, Gemini, Qwen), contributing to the conversation in round-robin fashion.

## Key Features

### 1. Human as Participant
- Human can be selected alongside AI models in the session setup
- Participates in round-robin turn rotation
- No tmux session or WebSocket stream required
- Fully integrated with existing discussion management

### 2. Interactive Turn-Based UI
- **Visual indicators**: Gradient banner displays "Your Turn!" when it's the human's turn
- **Button swap**: Input area changes from "Send to All" to "Submit" (green) and "Skip" (yellow)
- **Real-time updates**: WebSocket events provide immediate UI feedback
- **Keyboard shortcuts**: Enter key submits response during human turns

### 3. Bypass Mode
- Toggle to temporarily skip human turns without removing human from discussion
- Orange "Bypass: ON" / Gray "Bypass: OFF" indicator
- Persists until toggled or session ends
- Only visible when human is enabled but not currently waiting

### 4. Turn Management
- **Submit**: Human provides response text, advances to next speaker
- **Skip**: Human passes turn without responding (confirms if text present)
- **Timeout**: Auto-skip after configurable timeout (default: 5 minutes)
- Empty submission validation (configurable)

### 5. Control Channel Integration
- Headless operation via named pipe commands
- `HUMAN_SUBMIT <text>` - Submit response programmatically
- `HUMAN_SKIP` - Skip turn programmatically
- Enables automation and external control

## User Workflows

### Starting a Discussion with Human

1. **Select Models**
   - Check "Human" alongside desired AI models (Claude, Codex, etc.)
   - All models unchecked by default - must explicitly select
   - Cannot start with only Human selected (requires at least one AI model)

2. **Configure Discussion**
   - Set discussion topic, max turns, starting model
   - Human cannot be starting model (auto-selects first AI model)
   - Click "Start Models" - only AI models start tmux sessions

3. **Discussion Flow**
   - AI models take turns as normal
   - When human's turn arrives, UI automatically switches modes

### During Human Turn

**UI Changes:**
- Gradient banner appears: "Your Turn!"
- Participant name shown: "Human's turn" or specific name
- Buttons swap to: **Submit** (green) and **Skip** (yellow)
- Model selector checkboxes hidden
- Input textarea enabled (even if session was paused)

**Actions:**
1. **Submit Response**
   - Type response in textarea
   - Press Enter or click "Submit"
   - Response recorded with 👤 marker
   - Turn advances to next speaker
   - On error: text preserved, alert shown

2. **Skip Turn**
   - Click "Skip" button
   - If text present: confirmation dialog appears
   - Turn recorded as skipped
   - Turn advances to next speaker

3. **Timeout**
   - After 5 minutes (default), turn auto-skips
   - Alert shown: "⏰ Human turn timed out and was automatically skipped"
   - Turn recorded with timeout metadata

### Bypass Mode

**When to Use:**
- Temporarily disable human participation without stopping discussion
- Useful for automated runs or when human unavailable

**How to Use:**
1. Bypass toggle appears when:
   - Human is in participant list
   - Discussion is running
   - Not currently human's turn

2. Click toggle to enable/disable
   - **ON**: Orange button with ToggleRight icon
   - **OFF**: Gray button with ToggleLeft icon

3. While bypassed:
   - Human turns skipped automatically
   - No banner or Submit/Skip buttons shown
   - Discussion continues with AI models only

### UI Reload Resilience

**Behavior:**
- Refresh browser during human turn → UI immediately restores correct state
- Status polling (every 2 seconds) ensures state synchronization
- WebSocket reconnects automatically
- Correct buttons and banner restored on page load

## Turn Recording

All human turns recorded in conversation history with:
- **Response marker**: 👤 (configurable)
- **Metadata flags**: `human_turn: true`, `skipped: true/false`, `timeout: true/false`
- **Turn counter**: Incremented like AI turns
- **Timestamp**: When turn started/completed
- **Participant name**: "Human" or configured name

## Configuration

### config.yaml - Human Block

```yaml
human:
  turn_timeout: 300              # Seconds (0 to disable), default: 300 (5 minutes)
  allow_empty_submissions: false # Reject empty responses, default: false
  response_marker: "👤"          # Emoji/text for transcript, default: 👤
```

### Per-Session Settings

No additional session configuration needed - human behavior controlled by global config.yaml settings.

## Technical Architecture

### Backend Components

1. **ConversationManager**
   - Human participant registration (type="human", has_controller=False)
   - Turn rotation includes human via metadata check
   - Waiting loop during human turn (polls for submit/skip/timeout)
   - Auto-skip on timeout with turn recording

2. **API Endpoints**
   - `POST /api/discussion/human/submit` - Submit human response
   - `POST /api/discussion/human/skip` - Skip human turn
   - `POST /api/discussion/human/bypass/toggle` - Toggle bypass mode
   - `GET /api/discussion/status` - Returns human turn state

3. **WebSocket Events**
   - `/ws/discussion/events` - Real-time human turn notifications
   - Events: `human_turn_started`, `human_turn_completed`, `human_turn_skipped`, `human_turn_timeout`, `bypass_human_toggled`

4. **Control Channel**
   - `HUMAN_SUBMIT <response text>` - Submit via named pipe
   - `HUMAN_SKIP` - Skip via named pipe

### Frontend Components

1. **App.tsx**
   - Human turn state management
   - WebSocket connection to discussion events
   - API call handlers (submit, skip, bypass toggle)
   - Status polling with human fields

2. **PromptInput.tsx**
   - Conditional rendering based on `waitingOnHuman` flag
   - Submit/Skip buttons with action handlers
   - Bypass toggle component
   - Enter key triggers submit during human turns

3. **SessionModelSelector.tsx**
   - Human checkbox in model list
   - Validation: prevents Human-only selection
   - Filters Human from session start/stop API calls

## Limitations & Known Issues

### Current Limitations

1. **History Rendering (Phase 7.5 - Deferred)**
   - Human turns recorded in backend with 👤 marker
   - Not yet displayed in frontend conversation history UI
   - Requires additional work on history display system

2. **State Persistence (Phase 2.6 - Deferred)**
   - Human turn state (`waiting_on_human`, `pending_turn_participant`) not persisted on orchestrator restart
   - Timeout timer resets on restart
   - Workaround: Manual testing should avoid restarts during human turns

3. **No Multi-Human Support**
   - Only one "Human" participant supported per discussion
   - Multiple humans would require participant ID distinction

### Design Decisions

1. **Human counts toward max_turns**: Yes - prevents infinite sessions
2. **Human turns excluded from loop detection**: Yes - humans don't loop
3. **Human completion signals count toward consensus**: Yes - treated like AI
4. **Starting model cannot be Human**: Correct - always starts with AI
5. **Bypass state resets on session end**: Not implemented yet (deferred)

## Troubleshooting

### Human Turn UI Not Appearing

**Symptoms:**
- Discussion reaches human turn but UI doesn't change
- No banner, buttons don't swap

**Possible Causes:**
1. WebSocket connection failed - Check browser console for errors
2. Backend not sending events - Check orchestrator logs
3. Status polling not extracting fields - Verify `/api/discussion/status` response

**Solutions:**
- Refresh browser (UI should restore via status polling)
- Check WebSocket connection at `/ws/discussion/events`
- Verify `waiting_on_human` field in status API response

### Submit/Skip Buttons Not Re-enabling

**Symptoms:**
- Clicked Submit or Skip, but buttons stay disabled
- "Submitting..." or "Skipping..." text persists

**Possible Causes:**
1. API request failed silently
2. WebSocket event not received
3. `humanActionPending` state stuck

**Solutions:**
- Check browser console for API errors
- Wait for status poll (2 seconds) - should clear state
- Refresh browser if stuck

### Timeout Not Working

**Symptoms:**
- Human turn exceeds 5 minutes but doesn't auto-skip

**Possible Causes:**
1. Timeout disabled in config (`turn_timeout: 0`)
2. Backend waiting loop not checking timeout
3. Timer not started correctly

**Solutions:**
- Verify `config.yaml` has `human.turn_timeout: 300`
- Check orchestrator logs for timeout detection
- Restart orchestrator to reload config

### Empty Submission Accepted

**Symptoms:**
- Submitting blank response succeeds when it shouldn't

**Possible Causes:**
1. `allow_empty_submissions: true` in config
2. Frontend not trimming whitespace
3. Backend validation bypassed

**Solutions:**
- Set `allow_empty_submissions: false` in config.yaml
- Verify API request body contains trimmed text
- Check orchestrator logs for validation

## Best Practices

### For Users

1. **Always pair Human with AI models** - Human-only discussions not supported
2. **Use Bypass when unavailable** - Don't let discussion hang on timeout
3. **Confirm before Skip** - UI warns if text would be discarded
4. **Monitor timeout** - 5 minutes default, plan responses accordingly
5. **Refresh if UI desync** - Status polling will restore correct state

### For Developers

1. **Check WebSocket events** - Use browser DevTools to verify event delivery
2. **Monitor backend logs** - Human turn state changes logged clearly
3. **Test edge cases** - Timeout, empty submission, rapid skip, network errors
4. **Preserve user input** - Never clear textarea on API error
5. **Handle reconnect gracefully** - WebSocket may disconnect, must reconnect

## Future Enhancements

Potential improvements not yet implemented:

1. **Multiple Human Participants** - Support "Human1", "Human2", etc.
2. **History Rendering** - Display human turns in conversation history UI
3. **State Persistence** - Survive orchestrator restarts during human turns
4. **Custom Timeouts per Human** - Different timeout values per participant
5. **Turn Extension** - Allow human to request more time before timeout
6. **Rich Text Input** - Support markdown, code blocks in human responses
7. **Typing Indicators** - Show when human is typing
8. **Turn Notifications** - Audio/desktop notifications when human turn starts

## Related Documentation

- [API Reference](./HumanInTheLoopDoc_API_Reference.md) - Detailed endpoint documentation
- [Control Channel](./HumanInTheLoopDoc_Control_Channel.md) - Headless operation guide
- [Configuration](./HumanInTheLoopDoc_Configuration.md) - Config.yaml reference
- [Task List](./TaskList_HitL.md) - Implementation tracking
- [Architecture](./architecture.md) - System design overview
