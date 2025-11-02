# AI Approval Configuration Reference

This document explains how each AI CLI is configured to bypass permission prompts during orchestrated discussions.

## Configuration Summary

| AI     | Method        | Configuration                           | Scope                 | Location                    |
|--------|---------------|-----------------------------------------|-----------------------|-----------------------------|
| Claude | CLI Flag      | `--dangerously-skip-permissions`        | All operations        | config.yaml:45              |
| Gemini | CLI Flag      | `--yolo`                                | All tools             | config.yaml:101             |
| Codex  | Settings File | `trust_level = "trusted"`               | Per-project           | ~/.codex/config.toml        |
| Qwen   | Settings File | `"autoAccept": true`                    | Per-project           | .qwen/settings.json         |

## Detailed Configuration

### Claude (`--dangerously-skip-permissions`)
- **Purpose**: Bypasses ALL permission prompts
- **Allows**: File edits, shell commands, tool execution without confirmation
- **One-time setup**: First run shows safety acknowledgment dialog (saved to `~/.claude.json`)
- **Security**: High risk - approves everything

### Gemini (`--yolo`)
- **Purpose**: Auto-approves ALL tool calls
- **Allows**: All operations without confirmation
- **Security**: High risk - approves everything

### Codex (Settings file)
- **Purpose**: Project-level trust configuration
- **File**: `~/.codex/config.toml`
- **Configuration**:
  ```toml
  [projects."/home/dgray/Projects/Orchestrator"]
  trust_level = "trusted"
  ```
- **Allows**: All operations in trusted projects
- **Security**: Medium risk - scoped to specific projects

### Qwen (Settings file)
- **Purpose**: Project-level approval configuration
- **File**: `.qwen/settings.json` in project directory
- **Configuration**:
  ```json
  {
    "autoAccept": true
  }
  ```
- **Allows**: Auto-approves read-only operations; can be configured for more
- **Alternative**: Can use command-line `--approval-mode` flag if needed
- **Security**: Medium risk - scoped to project directory

## Configuration Files

### Primary: config.yaml
Command-line flags are defined in `/home/dgray/Projects/Orchestrator/config.yaml`:

```yaml
claude:
  executable_args:
    - "--dangerously-skip-permissions"

gemini:
  executable_args:
    - "--yolo"

codex:
  executable_args: []  # Uses settings file instead

qwen:
  executable_args: []  # Uses settings file instead
```

### Codex Settings: ~/.codex/config.toml
Codex uses a global settings file for project trust levels:

```toml
[projects."/home/dgray/Projects/Orchestrator"]
trust_level = "trusted"

[projects."/home/dgray"]
trust_level = "trusted"
```

### Qwen Settings: .qwen/settings.json
Qwen uses a project-specific settings file in the working directory:

```json
{
  "autoAccept": true
}
```

This file should be created at `/home/dgray/Projects/Orchestrator/.qwen/settings.json`

## Qwen Settings Configuration

Qwen can be configured via `.qwen/settings.json` in the project directory. According to the documentation, the `autoAccept` setting controls automatic approval of tool calls:

```json
{
  "autoAccept": true
}
```

**Note**: The exact behavior of `autoAccept` may depend on the Qwen version. Based on the CLI documentation, this setting controls whether safe (read-only) operations are automatically approved.

For more granular control, Qwen also supports command-line `--approval-mode` flag:
- `--approval-mode default` - Prompt for each tool
- `--approval-mode auto_edit` - Auto-approve edit tools only
- `--approval-mode yolo` - Auto-approve ALL tools

## Security Considerations

**Risk Level by Configuration:**
- 🔴 **High Risk**: Claude (`--dangerously-skip-permissions`), Gemini (`--yolo`), Qwen (`yolo` mode)
  - Auto-approves all operations including destructive commands
  - Use only in controlled/sandboxed environments

- 🟡 **Medium Risk**: Codex (project trust levels), Qwen (project settings)
  - Scoped to specific project directories
  - Requires explicit configuration per project
  - Settings file must exist in project

## Testing

To verify approval configuration works:

```bash
# Start an orchestrated discussion with all AIs
python3 examples/run_three_agent_discussion.py \
  --auto-start \
  --kill-existing \
  "Each AI: create a test file in /tmp with your name and current timestamp"
```

**Expected behavior:**
- Claude, Gemini: File created without prompts ✅
- Codex: File created without prompts (project is trusted) ✅
- Qwen: File created without prompts (if `.qwen/settings.json` configured) ✅

**If Qwen settings file doesn't exist:**
- Qwen: Would block waiting for user approval ❌

## Related Documentation

- Qwen CLI Commands: `/home/dgray/Projects/Orchestrator/docs/Qwen_CLI_Commands.pdf`
- Claude CLI Reference: `/home/dgray/Projects/Orchestrator/docs/Claude_CLI_Reference`
- Project Configuration: `/home/dgray/Projects/Orchestrator/config.yaml`

## Setup Instructions

### Create Qwen Settings File

To enable auto-approval for Qwen in this project:

```bash
mkdir -p /home/dgray/Projects/Orchestrator/.qwen
cat > /home/dgray/Projects/Orchestrator/.qwen/settings.json <<'EOF'
{
  "autoAccept": true
}
EOF
```

---
*Last updated: 2025-10-31*
*Qwen uses project-specific `.qwen/settings.json` file (similar to Codex approach)*
