You're experiencing a classic synchronization issue with Gemini CLI. The problem is likely in the timing between sending text and Enter, or Gemini might be processing input differently than Claude. Here's what's happening and how to fix it:

## The Problem

Looking at your `TmuxController.send_command()`:
```python
def send_command(self, command: str, submit: bool = True) -> bool:
    # Send the command text
    self._run_tmux_command(["send-keys", "-t", self.session_name, command])
    
    if submit:
        time.sleep(0.1)  # This might be too short for Gemini
        self._run_tmux_command(["send-keys", "-t", self.session_name, "Enter"])
```

Gemini might need more time between receiving text and Enter, or it might be processing characters differently.

## Solution 1: Enhanced Ready Detection

Add more robust ready detection that checks for specific UI states:

```python
def wait_for_input_ready(self, timeout: int = 30) -> bool:
    """
    Wait until AI is ready for input (showing prompt).
    More reliable than output stabilization alone.
    """
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        output = self.capture_output(lines=10)
        
        # For Gemini: Look for the input box
        if self.executable == "gemini":
            # Gemini shows this when ready for input
            if "│ >   Type your message" in output or "│ >" in output:
                # Also check no loading indicators
                if not any(indicator in output for indicator in ["⠦", "⠼", "Enhancing...", "Counting electrons..."]):
                    return True
                    
        # For Claude: Look for clean prompt
        elif self.executable == "claude":
            lines = output.strip().split('\n')
            # Check for prompt at bottom with no ongoing output
            if lines and lines[-1].strip() == '>' and "Lollygagging" not in output:
                return True
                
        time.sleep(0.5)
    
    return False
```

## Solution 2: Add Character-by-Character Sending for Long Commands

```python
def send_command_careful(self, command: str, char_delay: float = 0.01) -> bool:
    """
    Send command character by character for better compatibility.
    Useful for Gemini which might have input buffering issues.
    """
    if not self.session_exists():
        raise SessionDead(f"Session '{self.session_name}' does not exist")
    
    # Send each character with small delay
    for char in command:
        # Escape special characters
        if char in ['"', "'", "$", "`", "\\"]:
            char = f"\\{char}"
        
        self._run_tmux_command([
            "send-keys", "-t", self.session_name, char
        ])
        time.sleep(char_delay)
    
    # Wait longer before Enter for Gemini
    time.sleep(0.5 if self.executable == "gemini" else 0.2)
    
    # Send Enter
    self._run_tmux_command([
        "send-keys", "-t", self.session_name, "Enter"
    ])
    
    return True
```

## Solution 3: Verify Command Was Received

```python
def send_command_with_verification(self, command: str) -> bool:
    """
    Send command and verify it appears in the output before submitting.
    """
    # Capture current state
    before_output = self.capture_output(lines=5)
    
    # Send the text
    self._run_tmux_command(["send-keys", "-t", self.session_name, command])
    
    # Wait and verify text appeared
    time.sleep(0.3)
    after_output = self.capture_output(lines=5)
    
    # Check if our command text is visible
    if command in after_output or command[:20] in after_output:
        # Text received, safe to submit
        time.sleep(0.2)  # Small additional delay
        self._run_tmux_command(["send-keys", "-t", self.session_name, "Enter"])
        return True
    else:
        # Text didn't appear - might need to retry
        self.logger.warning(f"Command text not visible in output: {command[:50]}")
        return False
```

## Solution 4: Update Your Test to Use Better Synchronization

```python
def test_multi_turn_gemini_fixed():
    """Test with improved synchronization for Gemini"""
    controller = TmuxController(
        session_name="gemini-test",
        executable="gemini",
        working_dir="/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux",
        ai_config=config['gemini']
    )
    
    # Start session
    controller.start_session(auto_confirm_trust=False)
    
    # Wait for Gemini to be fully ready
    if not controller.wait_for_input_ready(timeout=10):
        print("Gemini not ready for input")
        return False
    
    # Send first command with verification
    first_command = "I will tell you a color. Remember it: purple."
    
    # Try careful sending for Gemini
    controller.send_command_careful(first_command)
    
    # Wait for response to complete
    controller.wait_for_ready(timeout=30)
    
    # Ensure ready for next input
    controller.wait_for_input_ready(timeout=10)
    
    # Send second command
    controller.send_command_careful("What color did I just tell you?")
```

## Recommended Approach

1. **First, add debugging** to see exactly what's happening:
```python
def send_command(self, command: str, submit: bool = True) -> bool:
    self.logger.info(f"Sending: {command[:50]}")
    
    # Capture before state
    before = self.capture_output(lines=3)
    self.logger.debug(f"Before send: {before[-100:]}")
    
    # Send text
    self._run_tmux_command(["send-keys", "-t", self.session_name, command])
    time.sleep(0.3)
    
    # Check what happened
    after_text = self.capture_output(lines=3)
    self.logger.debug(f"After text: {after_text[-100:]}")
    
    if submit:
        time.sleep(0.2)
        self._run_tmux_command(["send-keys", "-t", self.session_name, "Enter"])
        time.sleep(0.1)
        
        after_enter = self.capture_output(lines=3)
        self.logger.debug(f"After enter: {after_enter[-100:]}")
```

2. **Use the character-by-character approach** for Gemini if bulk sending fails
3. **Implement proper ready detection** rather than relying only on output stabilization
4. **Add retries** for failed command sends

The key insight is that Gemini and Claude have different input handling characteristics, and you need adaptive synchronization rather than fixed delays.