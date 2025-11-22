 Slash commands in Codex CLI

Control Codex during interactive sessions and extend it with your own slash commands.
Codex CLI

Slash commands give you fast, keyboard-first control over Codex. Type / in the composer to open the slash popup, choose a command, and Codex will perform actions such as switching models, adjusting approvals, or summarising long conversations without leaving the terminal.

This guide shows you how to:

    understand every built-in slash command and when to reach for it,
    steer an active session with commands like /model, /status, and /compact, and
    register custom prompts that behave like new slash commands with arguments and metadata.

Built-in slash commands at a glance

Codex ships with the following commands. Open the slash popup and start typing the command name to filter the list.
Command	Purpose	When to use it
/model	Choose the active model (and reasoning effort, when available).	Switch between general-purpose models (gpt-4.1-mini) and deeper reasoning models before running a task.
/approvals	Set what Codex can do without asking first.	Relax or tighten approval requirements mid-session, for example switching between Auto and Read Only.
/review	Ask Codex to review your working tree.	Run after Codex completes work or when you need a second set of eyes on local changes.
/new	Start a new conversation inside the same CLI session.	Reset the chat context without leaving the CLI; useful when you want a fresh prompt but keep the same repo.
/init	Generate an AGENTS.md scaffold in the current directory.	Capture persistent instructions for the repository or subdirectory you are working in.
/compact	Summarise the visible conversation to free tokens.	Use after long runs so Codex retains key points without blowing the context window.
/undo	Revert Codex’s most recent turn.	Quickly roll back an unwanted edit or command execution.
/diff	Show the git diff, including untracked files.	Review Codex’s edits before committing or running tests.
/mention	Attach a file to the conversation.	Highlight specific files or folders you want Codex to inspect next.
/status	Display session configuration and token usage.	Confirm the active model, approval policy, writable roots, and remaining context capacity.
/mcp	List configured Model Context Protocol (MCP) tools.	Check which external tools Codex can call during the session.
/logout	Sign out of Codex.	Clear local credentials when using a shared machine.
/quit	Exit the CLI.	Leave the session immediately.
/exit	Exit the CLI (same as /quit).	Alternative spelling; both commands terminate the session.
/feedback	Send logs to the Codex maintainers.	Report issues or share diagnostics with support.

/quit and /exit both terminate the CLI. Use them only after you have saved or committed any important work.
Control your session with slash commands

The following workflows keep your session on track without restarting Codex.
Set the active model with /model

    Start Codex and open the composer.
    Type /model and press Enter.
    Choose a model such as gpt-4.1-mini or gpt-4.1 from the popup.

Expected: Codex confirms the new model in the transcript. Run /status to verify the change.
Update approval rules with /approvals

    Type /approvals and press Enter.
    Select the approval preset that matches your comfort level, for example Auto for hands-off runs or Read Only to review edits.

Expected: Codex announces the updated policy. Future actions respect the new approval mode until you change it again.
Inspect the session with /status

    In any conversation, type /status.
    Review the modal output for the active model, approval policy, writable roots, and current token usage.

Expected: You see a summary similar to what codex status prints in the shell, confirming Codex is operating where you expect.
Keep transcripts lean with /compact

    After a long exchange, type /compact.
    Confirm when Codex offers to summarise the conversation so far.

Expected: Codex replaces earlier turns with a concise summary, freeing context while keeping critical details.
Undo recent work with /undo

    When Codex makes an incorrect edit or runs an unwanted command, type /undo.
    Confirm the rollback when prompted.

Expected: Codex restores the previous state (including reverting file changes) and tells you what it removed.
Review changes with /diff

    Type /diff to inspect the git diff.
    Scroll through the output inside the CLI to review edits and added files.

Expected: Codex shows staged and unstaged differences, including untracked files, so you can decide what to keep.
Highlight files with /mention

    Type /mention followed by a path, for example /mention src/lib/api.ts.
    Select the matching result from the popup.

Expected: Codex adds the file to the conversation, ensuring follow-up turns reference it directly.
Close or report a session

    Use /feedback to send logs to maintainers when you encounter issues.
    Use /logout to clear your credentials, then /quit (or /exit) to leave the CLI once you are finished.

Create your own slash commands with custom prompts

Custom prompts turn Markdown files into reusable slash commands that you trigger with /prompts:<name>.

    Ensure your Codex home exists:

    mkdir -p ~/.codex/prompts

        
      

Create ~/.codex/prompts/draftpr.md with reusable guidance:

---
description: Prep a branch, commit, and open a draft PR
argument-hint: [FILES=<paths>] [PR_TITLE="<title>"]
---

Create a branch named `dev/<feature_name>` for this work.
If files are specified, stage them first: $FILES.
Commit the staged changes with a clear message.
Open a draft PR on the same branch. Use $PR_TITLE when supplied; otherwise write a concise summary yourself.

    
  

    Restart Codex (or start a new session) so it loads the new prompt.

Expected: Typing /prompts:draftpr in the slash popup shows your custom command with the description from the frontmatter and hints that files and a PR title are optional.
Add metadata and arguments

Codex reads prompt metadata and placeholders the next time the session starts.

    Description — Shown under the command name in the popup. Set it in YAML frontmatter as description:.
    Argument hint — Document expected parameters with argument-hint: KEY=<value>.
    Positional placeholders — $1–$9 expand from space-separated arguments you provide after the command. $ARGUMENTS includes them all.
    Named placeholders — Use uppercase names like $FILE or $TICKET_ID and supply values as KEY=value. Quote values with spaces (for example, FOCUS="loading state").
    Literal dollar signs — Write $$ to emit a single $ in the expanded prompt.

After editing prompt files, restart Codex or open a new chat so the updates load. Codex ignores non-Markdown files in the prompts directory.
Invoke and manage custom commands

Launch Codex and type / to open the popup.

Enter prompts: or the prompt name, for example /prompts:draftpr.

Supply required arguments:

/prompts:draftpr FILES="src/pages/index.astro src/lib/api.ts" PR_TITLE="Add hero animation"

    
  

    Press Enter to send the expanded instructions (skip either argument when you do not need it).

Expected: Codex pastes the content of draftpr.md, replacing placeholders with the arguments you supplied. Run /status or /diff afterward to confirm the prompt triggered the intended workflow.

Manage prompts by editing or deleting files under ~/.codex/prompts/. Codex scans only the top-level Markdown files in that folder, so place each custom prompt directly under ~/.codex/prompts/ rather than in subdirectories.