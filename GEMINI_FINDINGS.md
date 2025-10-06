# Gemini CLI Interaction Findings

## Test Date
2025-10-06

## Environment
- **OS**: WSL2 (Ubuntu)
- **Tmux Version**: 3.2a
- **Gemini CLI**: gemini-2.5-pro
- **Path**: /home/dgray/.nvm/versions/node/v24.7.0/bin/gemini

## Comparison with Claude Code

### Similarities ✓
1. **Same tmux approach works** - All techniques from Claude apply to Gemini
2. **Text/Enter separation required** - Must send text and Enter as separate commands
3. **Interactive CLI** - Similar text-based interface
4. **Prompt structure** - Uses `>` prompt marker
5. **Box drawing UI** - Uses unicode box characters for interface

### Key Differences

#### 1. **Response Marker**
- **Claude Code**: `●` (bullet point)
- **Gemini CLI**: `✦` (sparkle/star symbol)

#### 2. **Loading Indicators**
- **Claude**: "Lollygagging…"
- **Gemini**: Various messages:
  - "⠦ Enhancing... Enhancing... Still loading"
  - "⠼ Counting electrons..."
  - Shows time estimate: "(esc to cancel, 2s)"

#### 3. **Tool Usage** (Major Difference!)
Gemini can use external tools:
```
╭───────────────────────────────────────────────────────────────────╮
│ ✓  GoogleSearch Searching the web for: "What is Python?"          │
│                                                                   │
│    Search results for "What is Python?" returned.                 │
╰───────────────────────────────────────────────────────────────────╯
```
- Shows tool calls in boxes
- Checkmark (✓) indicates successful tool execution
- Returns tool results before final response

#### 4. **Status Bar**
- **Claude**: Single line, right-aligned
  ```
  ? for shortcuts    Thinking off (tab to toggle)
  ```
- **Gemini**: Multi-column layout
  ```
  OrchestratorTest (GeminiDev*)  no sandbox (see /docs)  gemini-2.5-pro (99% context left)
  ```
  - Shows directory and git branch
  - Sandbox status
  - Model name
  - Context usage percentage

#### 5. **Startup Output**
Gemini shows:
- ASCII art logo
- Tips for getting started
- File context information ("Using: 2 GEMINI.md files")
- Cached credentials message

#### 6. **Error Messages**
Observed: `[ERROR] [ImportProcessor] Failed to import CLAUDE.md,: ENOENT`
- Gemini tries to load `.md` files for context
- Shows import errors (non-fatal)

## Technical Details

### Startup Sequence
1. Logo display: < 1 second
2. Tips and initialization: ~2 seconds
3. Ready state: ~3 seconds total
4. **Faster than Claude Code** (~3s vs ~8s)

### Prompt Patterns
```
╭────────────────────╮
│  > What is 2 + 2?  │
╰────────────────────╯
```
- Question appears in a box
- Prompt indicator: `>`
- Input prompt: `>   Type your message or @path/to/file`

### Response Format
```
✦ Response text here
```
- Sparkle marker (✦) indicates response
- Multi-line responses indent properly
- Tool results appear in separate boxes

### Ready State Indicators
- Input box visible: `╭─────────...`
- Status bar shows: "context left"
- No loading spinner visible
- Separator lines present

## Implementation Considerations

### Wait for Ready Detection
Similar to Claude but watch for:
1. Output stabilization (same approach)
2. Input box presence: `│ >   Type your message`
3. No loading spinner: `⠦`, `⠼`, etc.
4. Tool completion boxes gone

### Output Parsing Differences
Need to handle:
- Different response marker: `✦` instead of `●`
- Tool execution boxes (optional - can strip)
- Multi-column status bar
- Different header/logo format

### Timing
- **Startup**: ~3 seconds (faster than Claude)
- **Simple responses**: 2-4 seconds
- **With tools**: 5-10 seconds (depends on tool)
- **Context preservation**: Same as Claude

## Configuration Recommendations

```yaml
gemini:
  startup_timeout: 5        # Faster than Claude
  response_timeout: 30      # Same (may need more if using tools)
  prompt_pattern: ">"       # Same as Claude
  response_marker: "✦"      # Different marker
  loading_indicators:
    - "⠦"
    - "⠼"
    - "Enhancing..."
    - "Counting electrons..."
  executable: "gemini"

  # Gemini-specific
  supports_tools: true
  tool_timeout: 15          # Additional time for tool execution
```

## Success Criteria

- [x] Can start Gemini in tmux session ✅
- [x] Can send commands (text/Enter separation) ✅
- [x] Can capture responses ✅
- [x] Response markers detected (✦) ✅
- [x] Multi-turn conversations work ✅
- [x] All Claude techniques apply to Gemini ✅

## Next Steps

1. Update config.yaml with Gemini settings
2. Make TmuxController AI-agnostic (support both)
3. Create GeminiController subclass (if needed for specifics)
4. Update OutputParser to handle both response markers
5. Test both AIs running simultaneously
6. Build orchestration layer

## Notes

- Gemini is **more verbose** with tool usage information
- Tool capability means responses may take longer
- Error handling needed for failed tool executions
- Status bar parsing more complex than Claude
- Context tracking percentage is useful feature
