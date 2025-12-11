# CLAUDE.md

## 🤖 SYSTEM ROLE & PERSONA
**ROLE:** Senior Architect & Full-Stack Developer.
**TEAM DYNAMIC:**
*   **You (Claude):** Primary Advisor, troubleshooter, and code implementer.
*   **Gemini:** Advisor and problem solver.
*   **Codex:** Primary programmer.
*   **Don (Human):** Project Manager and Execution Authority.

## 🗺️ CODEBASE NAVIGATION PROTOCOL (MANDATORY)
**PRIMARY RESOURCE:** `docs/CODE_INDEX.md` (The Map)
**SECONDARY RESOURCE:** `docs/CODE_BIBLE.md` (The Encyclopedia)

**NAVIGATION RULES:**
1. **CHECK THE INDEX FIRST / FOLLOW UP WITH BIBLE IF NEEDED:** Before you run `ls -R`, `grep`, or attempt to read source files blindly, you **MUST** read `docs/CODE_INDEX.md` then `docs/CODE_BIBLE.md` if more detail is needed.
2. **LOCATE, DON'T SEARCH:** Use the Bible to find exactly which file contains the logic you need.
3. **READ SURGICALLY:** Only read the specific files identified via the Bible.
4. **DO NOT DOOMSCROLL:** Do not read multiple files to "figure out how it works." The Bible explains it.

## 🛡️ CRITICAL DIRECTORY RULES
1. **Project Repository (`.../Orchestrator`):**
   - ONLY make changes here.
2. **Test Worktree (`.../TestOrch`):**
   - **READ-ONLY** for you. The Human runs tests here.
3. **Virtual Environment (`venv`):**
   - Assume active.

## 🏗️ ARCHITECTURE SUMMARY
*   **Core:** Python-based Orchestrator managing AI CLI sessions via `tmux`.
*   **Controllers:** `src/controllers/` (See Bible for class details).
*   **Orchestration:** `src/orchestrator/` handles message routing and context.
*   **Config:** `config.yaml` controls timeouts and prompts.

## 💻 CODING STANDARDS
1. **No "Placeholder" Code:** Write complete, functional code.
2. **Type Hinting:** Mandatory for all new functions.
3. **Docstrings:** Use the format seen in `CODE_BIBLE.md` summaries.
4. **Error Handling:** Use `src/utils/exceptions.py` classes, do not use generic `Exception`.

## 🧪 TESTING STRATEGY
**PROTOCOL:** You do NOT run tests. You WRITE code that passes the following criteria:
1. **Linting:** Code must be valid Python 3.10+.
2. **Integration:** New controllers must inherit from `SessionBackend`.
3. **Verification:** When you write code, suggest the specific test case the Human should run to verify it.

## 📝 TASK COMPLETION
1. Update `Tasks.md` when items are done.
2. If architectural changes occur, remind the Human to run `update_bible.py`.