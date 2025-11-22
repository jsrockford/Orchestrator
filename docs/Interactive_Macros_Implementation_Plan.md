# Interactive Macros Implementation Plan

**Status:** In Progress — Phase 1 & 2 implemented, Phase 3 UI wired, Phase 4 docs pending
**Created:** 2025-11-21
**Objective:** Enable human operators to trigger model-specific interactive modes (YOLO, permission cycling, etc.) via tmux key injection without disrupting current orchestration flows.

---

## Design Summary

### Core Concept
Config-driven macro system that extends the existing control channel to send keyboard shortcuts and slash commands to specific AI CLI sessions via tmux.

### Key Design Decisions
- ✅ Config-driven macros in `config.yaml` (no custom user macros initially)
- ✅ No confirmation dialogs (trust human operator intent)
- ✅ No context-aware hiding or state detection
- ✅ Optional debouncing per-macro (default: 0 seconds)
- ✅ Leverage existing control channel infrastructure
- ✅ Support both keyboard shortcuts (`keys`) and text commands (`command`)

### UI Design
Three icon-based dropdowns on each AI's conversation window title bar:
1. **"/" icon** → Slash commands
2. **"Ctrl" icon** → Ctrl-based shortcuts
3. **"⇧" icon** → Shift-based shortcuts

Dropdowns are dynamically populated from the config based on macro `category` field.

---

## Phase 1: Backend Implementation

**Goal:** Core macro functionality via control channel and shell script.
**Status:** Implemented (config + control channel + tmux + CLI); needs validation coverage.

### Task 1.1: Add Interactive Macros Config Section
**File:** `config.yaml`

Add new top-level section:
```yaml
interactive_macros:
  claude:
    cycle_permission_mode:
      keys: ["S-Tab"]
      description: "Cycle: Auto-Accept → Plan → Normal"
      category: "shift"
      debounce_seconds: 1  # Optional: ignore repeats within 1 second
    toggle_verbose:
      keys: ["C-o"]
      description: "Toggle verbose output"
      category: "ctrl"
    toggle_thinking:
      keys: ["Tab"]
      description: "Toggle extended thinking"
      category: "other"

  gemini:
    toggle_yolo:
      keys: ["C-y"]
      description: "Toggle YOLO mode (auto-approve all)"
      category: "ctrl"
    toggle_auto_edit:
      keys: ["S-Tab"]
      description: "Toggle Auto-Edit mode"
      category: "shift"
    toggle_todo:
      keys: ["C-t"]
      description: "Toggle TODO list display"
      category: "ctrl"

  codex:
    set_approvals:
      command: "/approvals"
      description: "Open approval policy picker"
      category: "slash"
    switch_model:
      command: "/model"
      description: "Switch active model"
      category: "slash"

  qwen:
    toggle_yolo:
      keys: ["C-y"]
      description: "Toggle YOLO mode"
      category: "ctrl"
    toggle_auto_edit:
      keys: ["S-Tab"]
      description: "Toggle Auto-Edit mode"
      category: "shift"
```

**Acceptance Criteria:**
- [ ] Config file parses without errors
- [ ] Schema documented with field descriptions (keys vs command, category, description)
- [ ] Config validation updated in `config_loader.py` to recognize `interactive_macros` section
- [ ] Schema validation errors surface early with helpful messages

---

### Task 1.2: Extend Control Channel for Macro Commands
**File:** `src/orchestrator/control_channel.py`

Add parsing logic for new `macro` command:
```python
# Command format: macro <agent> <macro_name>
# Example: macro gemini toggle_yolo
```

**Implementation Steps:**
1. Add `handle_macro_command()` method to `ControlChannel` class
2. Parse command: extract agent name and macro name
3. Validate agent exists in orchestrator controllers
4. Look up macro config from `config.interactive_macros[agent][macro_name]`
5. Validate macro exists (error message if not found)
6. Route to appropriate controller's `send_macro()` method
7. Log to `logs/control_channel_history.log` in format:
   ```
   2025-11-21 14:32:15 [MACRO] agent=gemini macro=toggle_yolo keys=["C-y"]
   ```

**Acceptance Criteria:**
- [ ] `macro` command parsed correctly from control pipe
- [ ] Invalid agent/macro names produce clear error messages
- [ ] Command is logged before execution
- [ ] Routing to tmux controller works

---

### Task 1.3: Add send_macro() to TmuxController
**File:** `src/controllers/tmux_controller.py`

Add new method to send macros:
```python
def send_macro(self, macro_config: dict) -> None:
    """
    Send a macro (keyboard shortcut or text command) to the tmux session.

    Args:
        macro_config: Dict with 'keys' (list) or 'command' (str)

    Example configs:
        {"keys": ["C-y"], "description": "Toggle YOLO"}
        {"command": "/approvals", "description": "Set approvals"}
    """
```

**Implementation Logic:**
```python
if "keys" in macro_config:
    # Keyboard shortcut - use tmux send-keys
    for key in macro_config["keys"]:
        self.send_keys(key)
elif "command" in macro_config:
    # Text command - send as literal text + Enter
    self.send_text(macro_config["command"])
    self.send_enter()
else:
    raise ValueError("Macro config must have 'keys' or 'command' field")
```

**Special Considerations:**
- Start with tmux notation (`S-Tab`, `C-y`)
- **Shift+Tab Fallback:** Some CLIs may not respond to `S-Tab` and require ANSI escape `\033[Z`. Implement compatibility check:
  ```python
  # Try tmux notation first
  self.send_keys("S-Tab")
  # If testing shows issues, add fallback:
  # self.send_keys("Escape", "[", "Z")  # Sends \033[Z
  ```
- Add debug logging for each key sent with exact escape sequence used
- **Debouncing (optional):** Add per-macro `debounce_seconds` config field (default: 0)
  - If set, track last execution time and ignore repeats within window
  - Example: `debounce_seconds: 1` ignores macro if executed within last 1 second

**Acceptance Criteria:**
- [ ] Method handles both `keys` and `command` paradigms
- [ ] Keyboard shortcuts are sent correctly via `send_keys()`
- [ ] Text commands are sent with Enter appended
- [ ] Error handling for malformed macro configs
- [ ] Debug logging shows what was sent (including exact escape sequences)
- [ ] Debouncing logic implemented if `debounce_seconds` > 0 in config
- [ ] Shift+Tab fallback path documented (implement if testing reveals issues)

---

### Task 1.4: Extend orchestrator_control.sh Script
**File:** `scripts/orchestrator_control.sh`

Add `macro` subcommand:
```bash
# Usage: scripts/orchestrator_control.sh macro <agent> <macro_name>
# Example: scripts/orchestrator_control.sh macro gemini toggle_yolo
```

**Implementation:**
1. Add case statement for `macro` command
2. Validate arguments (require agent and macro_name)
3. Write to control pipe: `echo "macro $AGENT_NAME $MACRO_NAME" > "$PIPE_PATH"`
4. Add help text for new command

**Example Usage:**
```bash
scripts/orchestrator_control.sh macro claude cycle_permission_mode
scripts/orchestrator_control.sh macro gemini toggle_yolo
scripts/orchestrator_control.sh macro codex set_approvals
```

**Acceptance Criteria:**
- [ ] `macro` subcommand is recognized
- [ ] Help text documents the new command
- [ ] Arguments are validated (error if missing)
- [ ] Command writes correctly to control pipe
- [ ] Compatible with existing control channel infrastructure

---

### Task 1.5: Manual Testing & Validation
**Goal:** Verify macros work with each CLI in live tmux sessions.

**Test Matrix:**

| Agent   | Macro                  | Expected Behavior                                |
|---------|------------------------|--------------------------------------------------|
| Claude  | cycle_permission_mode  | Permission mode cycles (visual indicator changes)|
| Claude  | toggle_verbose         | Verbose output toggles on/off                    |
| Gemini  | toggle_yolo            | YOLO mode indicator appears/disappears           |
| Gemini  | toggle_auto_edit       | Auto-Edit indicator appears/disappears           |
| Codex   | set_approvals          | Interactive approval picker dialog appears       |
| Codex   | switch_model           | Model selection dialog appears                   |
| Qwen    | toggle_yolo            | YOLO mode indicator appears/disappears           |

**Testing Procedure:**
1. Start each AI CLI in tmux session (use existing startup scripts)
2. Run macro command via `orchestrator_control.sh`
3. Attach to tmux session (read-only) to verify visual change
4. Check `logs/control_channel_history.log` for correct logging
5. Test invalid macro names (should fail gracefully)
6. **Document exact tmux send-keys strings used** - capture the working escape sequences for each macro in test log

**Acceptance Criteria:**
- [ ] All macros tested with their respective CLIs
- [ ] Visual confirmation of mode changes in tmux
- [ ] No crashes or errors during execution
- [ ] Logging format is consistent and readable
- [ ] Invalid inputs produce helpful error messages
- [ ] Shift+Tab works correctly (may require ANSI escape testing)
- [ ] **Test log created** documenting exact tmux send-keys strings that worked for each agent/macro

---

## Phase 2: API Integration

**Goal:** Expose macro functionality via REST API for Web UI consumption.
**Status:** Implemented (GET /api/macros, POST /api/macro, macro_executed event broadcast); manual testing pending.

### Task 2.1: Add GET /api/macros Endpoint
**File:** `src/orchestrator/web_api.py`

**Endpoint:** `GET /api/macros`
**Response:** JSON object with full macro configuration
```json
{
  "claude": {
    "cycle_permission_mode": {
      "keys": ["S-Tab"],
      "description": "Cycle: Auto-Accept → Plan → Normal",
      "category": "shift"
    },
    "toggle_verbose": {...}
  },
  "gemini": {...},
  "codex": {...},
  "qwen": {...}
}
```

**Implementation:**
- Read from `orchestrator.config["interactive_macros"]`
- Return as JSON response
- Cache config at startup (no need to re-read on every request)

**Acceptance Criteria:**
- [ ] Endpoint returns correct JSON structure
- [ ] All agents and macros are included
- [ ] Response includes all fields (keys/command, description, category)
- [ ] Fast response time (cached config)

---

### Task 2.2: Add POST /api/macro Endpoint
**File:** `src/orchestrator/web_api.py`

**Endpoint:** `POST /api/macro`
**Request Body:**
```json
{
  "agent": "gemini",
  "macro_name": "toggle_yolo"
}
```
**Response:**
```json
{
  "success": true,
  "message": "Macro 'toggle_yolo' sent to agent 'gemini'"
}
```

**Implementation:**
1. Validate request body (agent and macro_name required)
2. Look up macro config from orchestrator.config
3. Call `orchestrator.controllers[agent].send_macro(macro_config)`
4. Return success/error response
5. Emit WebSocket event for live UI updates

**Error Handling:**
- 400: Missing agent or macro_name
- 404: Agent or macro not found in config
- 500: Tmux/controller errors

**Acceptance Criteria:**
- [ ] Endpoint accepts POST requests with JSON body
- [ ] Validation errors return 400 status
- [ ] Unknown agent/macro returns 404
- [ ] Successful macro sends return 200
- [ ] WebSocket event emitted on success

---

### Task 2.3: WebSocket Event for Macro Execution
**File:** `src/orchestrator/web_api.py`

**Event Type:** `macro_executed`
**Payload:**
```json
{
  "event": "macro_executed",
  "agent": "gemini",
  "macro_name": "toggle_yolo",
  "description": "Toggle YOLO mode (auto-approve all)",
  "timestamp": "2025-11-21T14:32:15Z"
}
```

**Purpose:** Notify connected Web UI clients when a macro is executed (allows for toast notifications or live status updates).

**Acceptance Criteria:**
- [ ] WebSocket event sent after successful macro execution
- [ ] Event includes all relevant fields
- [ ] Multiple connected clients all receive event

---

## Phase 3: Frontend Web UI

**Goal:** Add interactive macro controls to the Web UI conversation windows.
**Status:** Implemented (macro fetch, dropdowns, event toasts); verify in-browser once backend running.

### Task 3.1: Fetch Macro Config on App Load
**File:** `frontend/src/App.tsx`

**Implementation:**
1. Add state: `const [macroConfig, setMacroConfig] = useState(null)`
2. Fetch `/api/macros` on component mount
3. Store config in state for consumption by conversation windows

**Acceptance Criteria:**
- [ ] API call made on app load
- [ ] Config stored in state
- [ ] Error handling if API fails

---

### Task 3.2: Create MacroDropdown Component
**File:** `frontend/src/components/MacroDropdown.tsx`

**Props:**
```typescript
interface MacroDropdownProps {
  agent: string;           // "claude", "gemini", etc.
  category: string;        // "slash", "ctrl", "shift", "other"
  macros: MacroConfig[];   // Filtered list for this category
  onMacroSelect: (macroName: string) => void;
}
```

**UI Design:**
- Icon button (/, Ctrl, ⇧ based on category)
- Dropdown menu with macro list
- Each item shows: `{description} ({shortcut})`
- Example: "Toggle YOLO mode (Ctrl+Y)"

**Behavior:**
- Click icon to open dropdown
- Click menu item to execute macro
- Show toast notification after execution

**Acceptance Criteria:**
- [ ] Component renders correct icon based on category
- [ ] Dropdown menu shows all macros for category
- [ ] Click handler calls `onMacroSelect` with macro name
- [ ] Styling matches existing UI (Tailwind classes)

---

### Task 3.3: Integrate MacroDropdowns into ConversationWindow
**File:** `frontend/src/components/ConversationWindow.tsx`

**Implementation:**
1. Filter macro config by agent
2. Group macros by category (slash/ctrl/shift/other)
3. Render one `MacroDropdown` per category in title bar
4. Implement `handleMacroSelect()`:
   - POST to `/api/macro` with agent and macro_name
   - Show toast notification on success
   - Handle errors

**UI Layout (Title Bar):**
```
[Agent Name]           [/] [Ctrl] [⇧]  [Pause] [Esc] [KB]
```

**Acceptance Criteria:**
- [ ] Dropdowns appear in title bar for each agent
- [ ] Only relevant dropdowns shown (if no slash commands, hide "/" icon)
- [ ] Clicking macro sends API request
- [ ] Toast notification appears: "Sent: Toggle YOLO mode (Gemini)"
- [ ] Error messages shown if API fails

---

### Task 3.4: WebSocket Listener for macro_executed Events
**File:** `frontend/src/App.tsx` or `ConversationWindow.tsx`

**Implementation:**
- Add WebSocket listener for `macro_executed` events
- Show toast notification when event received (even if triggered from CLI)
- Update UI if needed (status indicator, etc.)

**Acceptance Criteria:**
- [ ] Listener registered on WebSocket connection
- [ ] Toast shown when macro event received
- [ ] Works for macros triggered via CLI (not just UI)

---

## Phase 4: Documentation

**Goal:** Document the new macro system for human operators and future developers.

### Task 4.1: Update Human Control Guide
**File:** `docs/Human_Control_Guide.md`

**New Section:** "Interactive Macros"

**Content:**
- Overview of macro system
- CLI usage examples
- List of available macros per agent
- How to add new macros to config
- Troubleshooting tips

**Acceptance Criteria:**
- [ ] Section added with clear examples
- [ ] All control channel commands documented
- [ ] Web UI usage explained

---

### Task 4.2: Update Onboarding Guide
**File:** `docs/onboarding.md`

**Updates:**
- Add macro system to collaboration protocol section
- Mention interactive controls in "Typical Workflow"
- Link to Human Control Guide for details

**Acceptance Criteria:**
- [ ] Brief mention of macros added
- [ ] Link to detailed docs provided

---

### Task 4.3: Update README.md
**File:** `README.md`

**Updates:**
- Add macro example to "Human Intervention & Control" section
- Update feature list to include "Interactive Mode Macros"

**Example Addition:**
```markdown
### Interactive Mode Macros

Trigger model-specific modes via control channel or Web UI:

```bash
# Toggle Gemini YOLO mode
scripts/orchestrator_control.sh macro gemini toggle_yolo

# Cycle Claude permission modes
scripts/orchestrator_control.sh macro claude cycle_permission_mode
```
```

**Acceptance Criteria:**
- [ ] README mentions macro feature
- [ ] Example usage included
- [ ] Links to detailed documentation

---

### Task 4.4: Create Macro Reference Document
**File:** `docs/Interactive_Macros_Reference.md`

**Content:**
- Complete list of all default macros
- Table format: Agent | Macro Name | Description | Shortcut/Command
- Config schema documentation
- Examples of adding custom macros (for future enhancement)

**Acceptance Criteria:**
- [ ] Comprehensive reference created
- [ ] All default macros documented
- [ ] Config schema explained

---

## Testing & Validation

### Integration Testing
- [ ] End-to-end test: Web UI button → API → Control Channel → Tmux → CLI mode change
- [ ] Test all agents (Claude, Gemini, Codex, Qwen)
- [ ] Test all macro types (keys vs command)
- [ ] Verify logging throughout the stack

### Regression Testing
- [ ] Existing control channel commands still work (pause, resume, say, key)
- [ ] Web UI functionality unaffected (pause/resume buttons, keyboard input)
- [ ] Orchestration automation not disrupted

### Edge Case Testing
- [ ] Invalid agent names
- [ ] Invalid macro names
- [ ] Macro execution during active AI turn
- [ ] Multiple rapid macro executions (debouncing if implemented)
- [ ] Web UI with no backend connection

---

## Success Criteria

### Phase 1 Complete When:
- [ ] All macros executable via `orchestrator_control.sh`
- [ ] Visual confirmation in tmux for each macro
- [ ] Logging works correctly
- [ ] No disruption to existing orchestration

### Phase 2 Complete When:
- [ ] API endpoints functional
- [ ] WebSocket events emitted
- [ ] Postman/curl testing passes

### Phase 3 Complete When:
- [ ] Web UI dropdowns render correctly
- [ ] Macros executable via button clicks
- [ ] Toast notifications appear
- [ ] UI matches design proposal

### Phase 4 Complete When:
- [ ] All documentation updated
- [ ] Examples provided
- [ ] Reference guide created

### Project Complete When:
- [ ] All four phases complete
- [ ] Integration testing passes
- [ ] Regression testing passes
- [ ] Team approval received
- [ ] Feature demonstrated to Don

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tmux escape sequences don't work for all CLIs | High | Test each CLI individually; implement ANSI fallback if needed |
| Macro execution during AI turn causes confusion | Medium | Document recommended usage timing; consider optional turn-lock |
| Web UI dropdowns clutter interface | Low | Hide dropdowns when agent inactive; use icons to save space |
| Config changes require orchestrator restart | Low | Document requirement; future: hot-reload config |

---

## Future Enhancements (Out of Scope)

- Custom user-defined macros (Phase 5)
- Context-aware macro visibility
- Macro chaining / sequences
- Hotkeys in Web UI (keyboard shortcuts that trigger macros)
- Macro execution confirmation for "dangerous" operations
- State detection and visual mode indicators

---

## Approval Checklist

Before beginning implementation, confirm:

- [ ] Don approves overall design
- [ ] Gemini reviewed and approved
- [ ] Codex reviewed and approved
- [ ] Config structure is acceptable
- [ ] UI design is acceptable
- [ ] Phase priorities agreed upon
- [ ] Any modifications to plan documented

---

**Document Version:** 1.1
**Last Updated:** 2025-11-22
**Next Review:** After team approval
