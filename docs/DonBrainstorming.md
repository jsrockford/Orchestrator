IDEAS
------
Prompt management - BASE PROMPT that is shared with each model at beginning | each model responds with simple "Understood"
Create various MODERATOR scripts for different scenarios - APPS, PLANNING, TROUBLESHOOTING, etc
Create spontaneous INSTRUCTION FILES for each model on the fly (ie CLAUDE.md, GEMINI.md, etc)
Allow HUMAN INTERJECTION in conversations
Save {prompt_text, response_text} data to JSON or SQL
NOTE: agents can be started with --<agent>-cwd /path/to/workdir flag AND <AGENT>.md can be placed in said directory with instructions
Instruction files VERY IMPORTANT for satisfying results. Have AI help create for detailed instructions so they don't go off course.

Implement OpenCode CLI
Implement Human interaction


AI-to-AI Communication
-----------------------
(from Qwen):
 For actual efficient AI-to-AI communication, there are several approaches that could work:

  Structured Communication Formats:
   - JSON messages with structured fields (role, content, metadata, intent)
   - Protocol buffers or other serialization formats
   - Function calling APIs where AIs request specific actions from each other

  Compressed Representations:
   - Using embeddings or vector representations of concepts instead of text
   - Shared knowledge graphs that both AIs reference with IDs
   - Template-based communication with fill-in-the-blank patterns

  Token Efficiency Techniques:
   - Shared vocabulary files with short codes for common concepts
   - Delta updates (only sending changes from previous state)
   - Binary formats for complex data exchanges

  However, these approaches would significantly complicate the current architecture and might
  actually reduce the human interpretability that's valuable for debugging. The delimiter
  approach we discussed earlier offers the best balance of token efficiency while maintaining
  human-readable logs and simple architecture.

  