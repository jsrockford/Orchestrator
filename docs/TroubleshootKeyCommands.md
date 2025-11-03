Based on conversation with Gemini regarding @scripts/orchestrator_control.sh 
============================================================================
Issue: Sending 'scripts/orchestrator_control.sh key qwen Escape' does NOT interrupt the current model, instead it waits for the model to finish before being injected.
Desired Result: sending the 'Escape' KEY should immediately stop the model and allow for PROMPT injection using 'scripts/orchestrator_control.sh SAY qwen "Do this instead...'

GEMINI's Observation:
Don: what if i want to interrupt Qwen so it stops processing immediately then input a prompt before
  the orchestrator takes the next turn?
  I tested the command using the 'KEY qwen Escape' command and watching the terminal window for
  @examples/run_orchestrated_discussion.py it did not get activated until AFTER the model was
  finished processing. So we have a problem. It needs to be immediate. Can you check the code and
  see if you find an obvious reason for the problem.
Gemini: You are absolutely right to point this out, and my apologies. My previous explanation was based
   on the logic of the control channel itself and did not account for the blocking nature of the
  main orchestration loop. Your observation is correct, and I have now reviewed the code and
  found the exact reason for the delay.

  The problem is a blocking `while` loop inside the `wait_for_ready` method.

  Here is the specific code path that causes the issue:

   1. The main script, run_orchestrated_discussion.py, calls the orchestrator to start a turn.
   2. The ConversationManager dispatches the command to the agent (e.g., Qwen).
   3. Immediately after dispatching, it calls _read_last_output to get the response.
   4. This method, in turn, calls _wait_for_controller, which then calls the TmuxController's
      wait_for_ready method.
   5. The Problem: The wait_for_ready method contains a while loop that runs continuously,
      checking if the agent has finished processing. This loop uses time.sleep() and blocks the
      entire orchestrator process.

  Because the orchestrator is single-threaded, it is completely stuck inside this wait_for_ready
   loop while the agent is thinking. It cannot do anything else, including checking the control
  pipe for your KEY command.

  Only after Qwen finishes its task and the wait_for_ready loop finally exits does the
  orchestrator's main loop continue, at which point it finally processes the KEY...Escape
  command you sent. By then, it's too late.

  Conclusion:

  You have discovered a fundamental architectural limitation in our current design. The system
  is not responsive to control commands during an agent's processing turn because it is blocked
  waiting for the turn to complete.

  To fix this, the wait_for_ready logic would need to be re-architected to be non-blocking,
  likely requiring a move to an asynchronous or multi-threaded approach so that the control
  channel can be polled concurrently.

--------------------------------------------------
QWEN's Observation:
Don: The KEY implementation isn't working as desired. You can read a brief explanation in
  @docs/TroubleshootKeyCommands.md . We need the KEY commands to be nearly instantaneous rather
  than waiting for the models to finish so orchestrator can send the command. What is your
  opinion?

Qwen: ✦ You're absolutely right, and Gemini correctly identified the core issue. The problem is
  architectural - the wait_for_ready() method uses a blocking loop that prevents the control
  channel from being checked until the current AI finishes processing.

  The Core Problem:

  The synchronous blocking loop in wait_for_ready():

   1 while not self._is_response_ready():
   2     time.sleep(check_interval)  # This blocks the entire orchestrator!

  During this time, the orchestrator cannot check the control pipe for KEY commands, making
  interrupt functionality impossible.

  My Opinion on Solutions:

  I believe there are several approaches to fix this, in order of preference:

  Option 1: Non-blocking Polling Pattern
  Modify the main orchestration loop to periodically check both response status AND control
  commands:

    1 def _wait_for_ready_with_interrupt(self, controller, timeout=30):
    2     """Wait for controller to be ready, but check control channel
      periodically."""
    3     start_time = time.time()
    4     check_interval = 0.1  # Short interval for responsiveness
    5
    6     while time.time() - start_time < timeout:
    7         if self._is_response_ready(controller):
    8             return True
    9
   10         # Check for control commands without blocking
   11         self.conversation_manager._check_control_commands()
   12
   13         if self.human_control_mode:  # If human took control, exit early
   14             return False
   15
   16         time.sleep(check_interval)
   17
   18     return False

  Option 2: Asynchronous Implementation
  Refactor to use asyncio with concurrent tasks:
   - One task: Wait for AI response completion
   - Second task: Monitor control channel continuously
   - Use asyncio.wait() with FIRST_COMPLETED

  Option 3: Threading
  Run the wait_for_ready logic in a separate thread, allowing the main thread to monitor control
   commands.

  My Recommendation: Go with Option 1

  The non-blocking polling approach is the best because:
   - ✅ Minimal architectural changes needed
   - ✅ Maintains single-threaded simplicity
   - ✅ Immediate responsiveness to ESC/KEY commands
   - ✅ Can be implemented incrementally
   - ✅ Doesn't require async refactoring of entire system

  The key insight is that instead of having one blocking loop, we intersperse control channel
  checks throughout the wait process. This would allow ESC keys to be processed immediately
  during long-running AI operations, achieving the instantaneous interrupt you need for
  permission dialogs and manual intervention.

  Would you like me to elaborate on any of these approaches?