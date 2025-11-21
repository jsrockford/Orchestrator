import { useState } from 'react';
import { Send, UserCheck, SkipForward, ToggleLeft, ToggleRight } from 'lucide-react';

interface Coder {
  id: number;
  title: string;
}

interface PromptInputProps {
  coders: Coder[];
  selectedCoders: number[];
  onSelectedCodersChange: (coders: number[]) => void;
  onSendPrompt: (prompt: string, coderIds: number[]) => Promise<void> | void;
  disabled?: boolean;
  sending?: boolean;
  // Phase 7: HitL - Human turn props
  waitingOnHuman?: boolean;
  pendingTurnParticipant?: string | null;
  humanEnabled?: boolean;
  bypassHuman?: boolean;
  onHumanSubmit?: (response: string) => Promise<void>;
  onHumanSkip?: () => Promise<void>;
  onToggleBypass?: () => Promise<void>;
  humanActionPending?: boolean;
}

function PromptInput({
  coders,
  selectedCoders,
  onSelectedCodersChange,
  onSendPrompt,
  disabled = false,
  sending = false,
  // Phase 7: HitL - Human turn props with defaults
  waitingOnHuman = false,
  pendingTurnParticipant = null,
  humanEnabled = false,
  bypassHuman = false,
  onHumanSubmit,
  onHumanSkip,
  onToggleBypass,
  humanActionPending = false,
}: PromptInputProps) {
  const [prompt, setPrompt] = useState('');

  const handleSend = async () => {
    if (sending) {
      return;
    }

    const trimmed = prompt.trim();
    if (!trimmed) {
      return;
    }

    if (selectedCoders.length === 0) {
      await onSendPrompt(trimmed, coders.map((c) => c.id));
    } else {
      await onSendPrompt(trimmed, selectedCoders);
    }
    setPrompt('');
  };

  const toggleCoder = (coderId: number) => {
    if (selectedCoders.includes(coderId)) {
      onSelectedCodersChange(selectedCoders.filter((id) => id !== coderId));
    } else {
      onSelectedCodersChange([...selectedCoders, coderId]);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      // Phase 7: HitL - Use human submit if waiting on human, otherwise regular send
      if (waitingOnHuman) {
        handleHumanSubmit();
      } else {
        handleSend();
      }
    }
  };

  // Phase 7: HitL - Human turn handlers
  const handleHumanSubmit = async () => {
    if (humanActionPending || !onHumanSubmit) {
      return;
    }
    const trimmed = prompt.trim();
    await onHumanSubmit(trimmed);
    setPrompt(''); // Clear on success
  };

  const handleHumanSkip = async () => {
    if (humanActionPending || !onHumanSkip) {
      return;
    }
    if (prompt.trim()) {
      // Warn if there's text that will be discarded
      if (!window.confirm('Discard your typed response and skip this turn?')) {
        return;
      }
    }
    await onHumanSkip();
    setPrompt(''); // Clear after skip
  };

  const handleToggleBypass = async () => {
    if (!onToggleBypass) {
      return;
    }
    await onToggleBypass();
  };

  const isSendDisabled = disabled || sending || prompt.trim().length === 0;
  const sendButtonText = selectedCoders.length === 0 || selectedCoders.length === coders.length
    ? 'Send to All'
    : `Send to ${selectedCoders.length} Model${selectedCoders.length > 1 ? 's' : ''}`;
  const buttonLabel = sending ? 'Sending...' : sendButtonText;

  // Phase 7: HitL - Determine if we should show human turn UI
  const showHumanTurnUI = waitingOnHuman;
  const showBypassToggle = humanEnabled && !waitingOnHuman;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-[#252526] border-t border-[#3e4451] shadow-2xl">
      {/* Phase 7: HitL - Human turn banner */}
      {showHumanTurnUI && (
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 py-3 px-6">
          <div className="max-w-[1600px] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <UserCheck size={24} className="text-white" />
              <div>
                <div className="text-white font-bold text-lg">Your Turn!</div>
                <div className="text-indigo-100 text-sm">
                  {pendingTurnParticipant ? `${pendingTurnParticipant}'s turn` : 'Enter your response below'}
                </div>
              </div>
            </div>
            <div className="text-indigo-100 text-sm">
              Press Enter or click Submit to send • Click Skip to pass this turn
            </div>
          </div>
        </div>
      )}

      <div className="max-w-[1600px] mx-auto p-6">
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                showHumanTurnUI
                  ? "Enter your response to the discussion..."
                  : disabled
                    ? "Start models to send prompts..."
                    : "Enter your prompt..."
              }
              disabled={disabled && !showHumanTurnUI}
              className="w-full bg-[#1e1e1e] border border-[#3e4451] rounded-lg px-4 py-3 text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none font-mono text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              rows={3}
            />
          </div>

          <div className="flex flex-col gap-3">
            {/* Phase 7: HitL - Conditional button rendering */}
            {showHumanTurnUI ? (
              <>
                <button
                  onClick={handleHumanSubmit}
                  disabled={humanActionPending}
                  className={`px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 shadow-lg hover:shadow-xl ${humanActionPending ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <UserCheck size={18} />
                  {humanActionPending ? 'Submitting...' : 'Submit'}
                </button>
                <button
                  onClick={handleHumanSkip}
                  disabled={humanActionPending}
                  className={`px-6 py-3 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 shadow-lg hover:shadow-xl ${humanActionPending ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <SkipForward size={18} />
                  {humanActionPending ? 'Skipping...' : 'Skip'}
                </button>
              </>
            ) : (
              <button
                onClick={handleSend}
                disabled={isSendDisabled}
                className={`px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 shadow-lg hover:shadow-xl ${isSendDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <Send size={18} />
                {buttonLabel}
              </button>
            )}

            {/* Phase 7: HitL - Bypass toggle (only show when Human enabled and not human's turn) */}
            {showBypassToggle && (
              <button
                onClick={handleToggleBypass}
                className={`px-4 py-2 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 text-sm ${
                  bypassHuman
                    ? 'bg-orange-600 hover:bg-orange-700 text-white'
                    : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                }`}
                title={bypassHuman ? 'Human turns are bypassed' : 'Human turns are enabled'}
              >
                {bypassHuman ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                {bypassHuman ? 'Bypass: ON' : 'Bypass: OFF'}
              </button>
            )}

            {/* Model selector checkboxes - hide during human turn */}
            {!showHumanTurnUI && (
              <div className="flex gap-3">
                {coders.map((coder) => (
                  <label
                    key={coder.id}
                    className="flex items-center gap-2 cursor-pointer group"
                  >
                    <input
                      type="checkbox"
                      checked={selectedCoders.includes(coder.id)}
                      onChange={() => toggleCoder(coder.id)}
                      className="w-4 h-4 rounded border-[#3e4451] bg-[#1e1e1e] text-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer"
                    />
                    <span className="text-sm text-gray-400 group-hover:text-gray-200 transition-colors">
                      {coder.title}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PromptInput;
