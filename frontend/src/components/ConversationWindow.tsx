import { useLayoutEffect, useMemo, useRef } from 'react';
import { ArrowUp, ArrowDown, X, FilePenLine, Settings, Skull } from 'lucide-react';
import ControlButton from './ControlButton';
import MacroDropdown from './MacroDropdown';
import { MacroDefinition } from '../types';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface Conversation {
  id: number;
  title: string;
  messages: Message[];
}

interface ConversationWindowProps {
  conversation: Conversation;
  onControlAction: (modelName: string, action: string) => void;
  onMacroTrigger: (agentName: string, macroName: string) => void;
  status: 'ready' | 'processing' | 'error';
  projectState: 'idle' | 'running' | 'paused';
  onEditInstructions: (modelName: string) => void;
  onConfigureSettings: (modelName: string) => void;
  output: string;
  streamStatus: 'idle' | 'connecting' | 'streaming' | 'error';
  errorMessage?: string | null;
  macros?: Record<string, MacroDefinition>;
}

function ConversationWindow({
  conversation,
  onControlAction,
  onMacroTrigger,
  status,
  projectState,
  onEditInstructions,
  onConfigureSettings,
  output,
  streamStatus,
  errorMessage,
  macros,
}: ConversationWindowProps) {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const isStickyRef = useRef(true);
  const ignoreScrollRef = useRef(false);
  const STICKY_THRESHOLD_PX = 60;

  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }

    const overflowed = container.scrollHeight > container.clientHeight;
    if (!overflowed) {
      container.scrollTop = 0;
      return;
    }

    if (!isStickyRef.current) {
      return;
    }

    ignoreScrollRef.current = true;
    container.scrollTop = container.scrollHeight;
  }, [output]);

  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }

    if (ignoreScrollRef.current) {
      ignoreScrollRef.current = false;
      return;
    }
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    isStickyRef.current = distanceFromBottom <= STICKY_THRESHOLD_PX;
  };

  const headerColorClass = {
    ready: 'bg-[#2d2d30]',
    processing: 'bg-green-700',
    error: 'bg-red-700',
  }[status];

  const showPlaceholder = projectState === 'idle' && output.trim().length === 0;

  const streamStatusLabel = (() => {
    switch (streamStatus) {
      case 'connecting':
        return 'Connecting...';
      case 'streaming':
        return 'Streaming';
      case 'error':
        return 'Stream error';
      default:
        return projectState === 'running' ? 'Waiting for output...' : 'Idle';
    }
  })();

  const macroGroups = useMemo(() => {
    const grouped: Record<string, { name: string; macro: MacroDefinition }[]> = {
      slash: [],
      ctrl: [],
      shift: [],
      other: [],
    };

    if (macros) {
      Object.entries(macros).forEach(([name, macro]) => {
        const category = (macro.category || 'other').toLowerCase();
        const bucket = grouped[category] ? category : 'other';
        grouped[bucket].push({ name, macro });
      });
    }

    return grouped;
  }, [macros]);

  const availableCategories = useMemo(() => {
    return (['slash', 'ctrl', 'shift', 'other'] as const).filter(cat => macroGroups[cat]?.length);
  }, [macroGroups]);

  return (
    <div className="bg-[#252526] border border-[#3e4451] rounded-lg overflow-visible flex flex-col min-h-0 min-w-[40rem] w-full h-[32rem] max-h-[32rem]">
      <div className={`${headerColorClass} px-4 py-3 border-b border-[#3e4451] flex items-center justify-between gap-3`}>
        <div className="flex items-center gap-2 min-w-0">
          <h2 className="text-sm font-semibold text-gray-200">
            {conversation.title}
          </h2>
          <button onClick={() => onEditInstructions(conversation.title)} className="text-gray-400 hover:text-white">
            <FilePenLine size={14} />
          </button>
          <button
            onClick={() => onConfigureSettings(conversation.title)}
            className="text-gray-400 hover:text-white"
            title="Model settings"
          >
            <Settings size={14} />
          </button>
        </div>
        <div className="flex items-center gap-2">
          {availableCategories.map(category => (
            <MacroDropdown
              key={category}
              agent={conversation.title}
              category={category}
              macros={macroGroups[category]}
              onSelect={macroName => onMacroTrigger(conversation.title, macroName)}
              disabled={projectState === 'idle'}
            />
          ))}
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs uppercase tracking-wide text-gray-300">
            {streamStatusLabel}
          </span>
          <div className="flex gap-2">
            <ControlButton
              icon="Esc"
              onClick={() => onControlAction(conversation.title, 'escape')}
              title="Escape"
            />
            <ControlButton
              icon="Rsm"
              onClick={() => onControlAction(conversation.title, 'resume')}
              title="Resume"
            />
            <ControlButton
              icon={<ArrowUp size={16} />}
              onClick={() => onControlAction(conversation.title, 'up')}
              title="Up Key"
            />
            <ControlButton
              icon={<ArrowDown size={16} />}
              onClick={() => onControlAction(conversation.title, 'down')}
              title="Down Key"
            />
            <ControlButton
              icon="↵"
              onClick={() => onControlAction(conversation.title, 'enter')}
              title="Enter Key"
            />
            <button
              onClick={() => onControlAction(conversation.title, 'kill')}
              className="w-8 h-8 rounded-full bg-red-600 hover:bg-red-700 text-white flex items-center justify-center transition-all shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
              title="KILL - Emergency Stop"
              disabled={projectState === 'idle'}
            >
              <Skull size={16} />
            </button>
            <button
              onClick={() => onControlAction(conversation.title, 'close')}
              className="text-gray-400 hover:text-red-400 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      </div>

      <div
        className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed min-h-0"
        ref={scrollContainerRef}
        onScroll={handleScroll}
      >
        {showPlaceholder ? (
          <div className="text-gray-500 italic">Waiting to start project...</div>
        ) : (
          <>
            {errorMessage && (
              <div className="mb-2 rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-300 text-xs">
                {errorMessage}
              </div>
            )}
            <pre className="text-blue-400 whitespace-pre-wrap overflow-x-hidden">
              {output || 'No output received yet.'}
            </pre>
          </>
        )}
      </div>
    </div>
  );
}

export default ConversationWindow;
