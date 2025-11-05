import { ArrowUp, ArrowDown, X, FilePenLine } from 'lucide-react';
import ControlButton from './ControlButton';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Conversation {
  id: number;
  title: string;
  messages: Message[];
}

interface ConversationWindowProps {
  conversation: Conversation;
  onControlAction: (coderId: number, action: string) => void;
  status: 'ready' | 'processing' | 'error';
  projectState: 'idle' | 'running' | 'paused';
  onEditInstructions: (modelName: string) => void;
}

function ConversationWindow({ conversation, onControlAction, status, projectState, onEditInstructions }: ConversationWindowProps) {
  const sampleOutput = `> Running task for ${conversation.title}...
> Initializing workspace
> Loading configuration files
> Processing request

const handleRequest = async (req, res) => {
  try {
    const data = await processData(req.body);
    return res.json({ success: true, data });
  } catch (error) {
    console.error('Error:', error);
    return res.status(500).json({ error: error.message });
  }
};

> Task completed successfully
> Waiting for next command...`;

  const headerColorClass = {
    ready: 'bg-[#2d2d30]',
    processing: 'bg-green-700',
    error: 'bg-red-700',
  }[status];

  return (
    <div className="flex-1 bg-[#252526] border border-[#3e4451] rounded-lg overflow-hidden flex flex-col">
      <div className={`${headerColorClass} px-4 py-3 border-b border-[#3e4451] flex items-center justify-between`}>
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-200">
            {conversation.title}
          </h2>
          <button onClick={() => onEditInstructions(conversation.title)} className="text-gray-400 hover:text-white">
            <FilePenLine size={14} />
          </button>
        </div>
        <div className="flex gap-2">
          <ControlButton
            icon="Esc"
            onClick={() => onControlAction(conversation.id, 'escape')}
            title="Escape"
          />
          <ControlButton
            icon={<ArrowUp size={16} />}
            onClick={() => onControlAction(conversation.id, 'up')}
            title="Up Key"
          />
          <ControlButton
            icon={<ArrowDown size={16} />}
            onClick={() => onControlAction(conversation.id, 'down')}
            title="Down Key"
          />
          <ControlButton
            icon="↵"
            onClick={() => onControlAction(conversation.id, 'enter')}
            title="Enter Key"
          />
          <button
            onClick={() => onControlAction(conversation.id, 'close')}
            className="text-gray-400 hover:text-red-400 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed">
        {projectState === 'idle' ? (
          <div className="text-gray-500 italic">Waiting to start project...</div>
        ) : (
          <pre className="text-blue-400 whitespace-pre-wrap">
            {sampleOutput}
          </pre>
        )}
      </div>
    </div>
  );
}

export default ConversationWindow;
