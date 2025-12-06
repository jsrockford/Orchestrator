import os
import httpx
import re
from datetime import datetime

# ================= CONFIGURATION =================
SOURCE_DIR = "./src"
BIBLE_FILE = "./docs/CODE_BIBLE.md"
API_URL = "http://127.0.0.1:5804/v1/chat/completions"
MODEL = "Granite-4.0-h-small"

# TIMEOUT: Increased to 15 minutes for your large files
HTTP_TIMEOUT = 900.0 

IGNORE_FILES = {
    "__init__.py", "setup.py", "conftest.py", "requirements.txt",
    "update_bible.py", "doc_gen.py", "LICENSE", ".gitignore"
}

IGNORE_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "env", "dist", "build", "tests", "docs"
}
# =================================================

SYSTEM_PROMPT = """
You are a Senior Technical Writer. Analyze the provided Python source code. 
Generate a concise Markdown entry including:
1. A 1-sentence summary of the file's purpose.
2. A list of Classes (with inheritance).
3. A table of Functions/Methods (Name, Arguments, Returns, Logic Summary).
Do not include full code. Focus on the 'What' and 'Why'.
"""

def parse_existing_bible():
    """Reads the existing markdown and extracts valid summaries."""
    if not os.path.exists(BIBLE_FILE):
        return {}
    
    print("🔍 Scanning existing Code Bible for reusable entries...")
    entries = {}
    current_file = None
    current_content = []
    
    with open(BIBLE_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        # Detect Header: ## File: `src/utils/logger.py`
        match = re.match(r"^## File: `(.*)`", line)
        if match:
            # Save previous entry if valid
            if current_file:
                entries[current_file] = "".join(current_content).strip()
            
            # Start new entry
            current_file = match.group(1)
            current_content = []
        elif current_file:
            current_content.append(line)
            
    # Save last entry
    if current_file:
        entries[current_file] = "".join(current_content).strip()
        
    return entries

def summarize_file(file_path, code_content):
    est_tokens = len(code_content) / 3.5
    print(f"📖 Librarian reading: {file_path} (~{int(est_tokens)} tokens)...")
    
    if est_tokens > 120000:
        return "> **Skipped:** File too large for automatic summarization."

    try:
        response = httpx.post(
            API_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Filename: {file_path}\n\n{code_content}"}
                ],
                "temperature": 0.1,
                # REDUCED TOKENS to force conciseness on large files
                "max_tokens": 1500, 
                "stream": False
            },
            timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except httpx.TimeoutException:
        print(f"❌ TIMEOUT on {file_path}")
        return "> **Error:** Timed out during analysis."
    except Exception as e:
        print(f"❌ Error on {file_path}: {e}")
        return f"> **Error analyzing file:** {str(e)}"

def build_bible():
    print("🚀 Starting Smart Librarian...")
    
    # 1. Load existing work
    existing_entries = parse_existing_bible()
    print(f"   Found {len(existing_entries)} existing entries.")
    
    new_entries = {}
    files_processed = 0
    files_skipped = 0
    
    # 2. Walk directory and decide: Keep or Refresh?
    for root, dirs, files in os.walk(SOURCE_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        
        for file in files:
            if not file.endswith(".py") or file in IGNORE_FILES:
                continue
            
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, start=".")
            
            # CHECK: Do we have a valid entry already?
            existing_text = existing_entries.get(rel_path, "")
            
            # If entry exists AND does NOT contain error keywords, keep it.
            if rel_path in existing_entries and "> **Error:" not in existing_text and "> **Skipped:" not in existing_text:
                print(f"✅ Keeping existing entry for: {rel_path}")
                new_entries[rel_path] = existing_text
                continue
            
            # Otherwise, regenerate (It's missing, or it was an error)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if not content.strip(): continue

                summary = summarize_file(rel_path, content)
                new_entries[rel_path] = summary
                files_processed += 1
            except Exception as e:
                print(f"Skipping {file}: {e}")

    # 3. Write EVERYTHING back to disk (Overwriting with the merged set)
    print(f"\n💾 Saving Code Bible...")
    with open(BIBLE_FILE, "w", encoding="utf-8") as bible:
        bible.write(f"# Project Code Bible\n")
        bible.write(f"*Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        bible.write("*Generated by Granite 4.0 Local Librarian*\n\n")
        bible.write("---\n\n")
        
        # Sort files alphabetically for cleanliness
        for filename in sorted(new_entries.keys()):
            bible.write(f"## File: `{filename}`\n\n")
            bible.write(new_entries[filename])
            bible.write("\n\n---\n\n")
            bible.flush() # Force write to disk immediately

    print(f"\n✨ Complete! Refreshed {files_processed} files, Kept {len(new_entries) - files_processed} files.")
    print(f"Saved to: {os.path.abspath(BIBLE_FILE)}")

if __name__ == "__main__":
    build_bible()