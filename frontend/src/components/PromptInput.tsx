import { useState } from 'react';
import { Send } from 'lucide-react';

interface Coder {
  id: number;
  title: string;
}

interface PromptInputProps {
  coders: Coder[];
  selectedCoders: number[];
  onSelectedCodersChange: (coders: number[]) => void;
  onSendPrompt: (prompt: string, coderIds: number[]) => void;
}

function PromptInput({
  coders,
  selectedCoders,
  onSelectedCodersChange,
  onSendPrompt,
}: PromptInputProps) {
  const [prompt, setPrompt] = useState('');

  const handleSend = () => {
    if (prompt.trim()) {
      if (selectedCoders.length === 0) {
        // If no coders are selected, send to all as a fallback or show a warning
        onSendPrompt(prompt, coders.map((c) => c.id));
      } else {
        onSendPrompt(prompt, selectedCoders);
      }
      setPrompt('');
    }
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
      handleSend();
    }
  };

  const isSendDisabled = prompt.trim().length === 0;
  const sendButtonText = selectedCoders.length === 0 || selectedCoders.length === coders.length
    ? 'Send to All'
    : `Send to ${selectedCoders.length} Model${selectedCoders.length > 1 ? 's' : ''}`;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-[#252526] border-t border-[#3e4451] shadow-2xl">
      <div className="max-w-[1600px] mx-auto p-6">
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Enter your prompt..."
              className="w-full bg-[#1e1e1e] border border-[#3e4451] rounded-lg px-4 py-3 text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none font-mono text-sm"
              rows={3}
            />
          </div>

          <div className="flex flex-col gap-3">
            <button
              onClick={handleSend}
              disabled={isSendDisabled}
              className={`px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 shadow-lg hover:shadow-xl ${isSendDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Send size={18} />
              {sendButtonText}
            </button>

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
          </div>
        </div>
      </div>
    </div>
  );
}

export default PromptInput;