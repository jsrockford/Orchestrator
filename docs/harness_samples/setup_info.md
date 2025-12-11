```markdown
# Install Claude Code CLI (latest version required)
npm install -g @anthropic-ai/claude-code

# Install Python dependencies
pip install -r requirements.txt

## 2. Set Up Authentication

You need two authentication tokens:

### Claude Code OAuth Token:

```
# Generate the token using Claude Code CLI
claude setup-token

# Set the environment variable
export CLAUDE_CODE_OAUTH_TOKEN='your-oauth-token-here'
```

### Linear API Key:

```
# Get your API key from: https://linear.app/YOUR-TEAM/settings/api
export LINEAR_API_KEY="lin_api_xxxxxxxx"
```

## 3. Verify Installation

```
claude --version # Should be latest version
pip show claude-code-sdk # Check SDK is installed
```