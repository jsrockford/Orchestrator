import { useState, useEffect, useCallback, useRef } from 'react';
import { Settings } from 'lucide-react';
import ConversationWindow, { type Conversation } from './components/ConversationWindow';
import PromptInput from './components/PromptInput';
import SessionModelSelector from './components/SessionModelSelector';
import EditInstructionsModal from './components/EditInstructionsModal';
import ProjectSettingsModal from './components/ProjectSettingsModal';

const DEFAULT_API_BASE = 'http://localhost:8000';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE).replace(/\/$/, '');
const MAX_OUTPUT_CHARS = 60000;

type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'error';

function App() {
  const [allConversations] = useState<Conversation[]>([
    { id: 1, title: 'Claude', messages: [] },
    { id: 2, title: 'Codex', messages: [] },
    { id: 3, title: 'Gemini', messages: [] },
    { id: 4, title: 'Qwen', messages: [] },
  ]);

  const [activeModels, setActiveModels] = useState<string[]>(['Claude', 'Codex', 'Gemini', 'Qwen']);
  const [selectedCoders, setSelectedCoders] = useState<number[]>([1, 2, 3, 4]);
  const [projectState, setProjectState] = useState<'idle' | 'running' | 'paused'>('idle');
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingModelName, setEditingModelName] = useState('');
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [projectDirectory, setProjectDirectory] = useState('/home/dgray/Projects/Orchestrator');
  const [sessionOutputs, setSessionOutputs] = useState<Record<string, string>>(
    () => Object.fromEntries(allConversations.map(c => [c.title, '']))
  );
  const [streamStatuses, setStreamStatuses] = useState<Record<string, StreamStatus>>(
    () => Object.fromEntries(allConversations.map(c => [c.title, 'idle']))
  );
  const [streamErrors, setStreamErrors] = useState<Record<string, string | null>>(
    () => Object.fromEntries(allConversations.map(c => [c.title, null]))
  );

  const socketsRef = useRef<Record<string, WebSocket>>({});
  const closingSocketsRef = useRef<Set<string>>(new Set());
  const projectStateRef = useRef(projectState);
  const activeModelsRef = useRef<string[]>(activeModels);

  useEffect(() => {
    projectStateRef.current = projectState;
  }, [projectState]);

  useEffect(() => {
    activeModelsRef.current = activeModels;
  }, [activeModels]);

  const clampOutput = useCallback((text: string) => {
    if (text.length <= MAX_OUTPUT_CHARS) {
      return text;
    }
    return text.slice(-MAX_OUTPUT_CHARS);
  }, []);

  const toWebSocketUrl = useCallback((path: string) => {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    const url = new URL(normalizedPath, API_BASE_URL);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url.toString();
  }, []);

  const closeSocket = useCallback((model: string, status: StreamStatus = 'idle') => {
    const socket = socketsRef.current[model];
    if (socket) {
      closingSocketsRef.current.add(model);
      try {
        socket.close();
      } catch (error) {
        console.warn(`Failed to close WebSocket for ${model}:`, error);
      }
      delete socketsRef.current[model];
    }
    setStreamStatuses(prev => ({ ...prev, [model]: status }));
    setStreamErrors(prev => ({ ...prev, [model]: null }));
  }, []);

  const closeAllSockets = useCallback((status: StreamStatus = 'idle') => {
    Object.keys(socketsRef.current).forEach(model => {
      closeSocket(model, status);
    });
  }, [closeSocket]);

  const ensureSocket = useCallback((model: string) => {
    if (projectStateRef.current === 'idle') {
      return;
    }
    if (!activeModelsRef.current.includes(model)) {
      return;
    }
    if (socketsRef.current[model]) {
      return;
    }

    const modelSlug = model.trim().toLowerCase();
    let socket: WebSocket;
    try {
      socket = new WebSocket(toWebSocketUrl(`/ws/session/${modelSlug}`));
    } catch (error) {
      console.error(`Unable to create WebSocket for ${model}:`, error);
      setStreamStatuses(prev => ({ ...prev, [model]: 'error' }));
      setStreamErrors(prev => ({ ...prev, [model]: 'WebSocket initialization failed' }));
      return;
    }

    socketsRef.current[model] = socket;
    closingSocketsRef.current.delete(model);
    setStreamStatuses(prev => ({ ...prev, [model]: 'connecting' }));

    socket.onopen = () => {
      setStreamStatuses(prev => ({ ...prev, [model]: 'streaming' }));
      setStreamErrors(prev => ({ ...prev, [model]: null }));
    };

    socket.onerror = () => {
      setStreamStatuses(prev => ({ ...prev, [model]: 'error' }));
      setStreamErrors(prev => ({ ...prev, [model]: 'WebSocket error' }));
    };

    socket.onmessage = event => {
      try {
        const data = JSON.parse(event.data ?? '{}');
        if (!data || typeof data !== 'object') {
          return;
        }
        const eventType = typeof data.type === 'string' ? data.type : undefined;
        const content = typeof data.content === 'string' ? data.content : '';

        if (eventType === 'error') {
          const message = typeof data.message === 'string' ? data.message : 'Stream error';
          setStreamStatuses(prev => ({ ...prev, [model]: 'error' }));
          setStreamErrors(prev => ({ ...prev, [model]: message }));
          return;
        }

        if (eventType === 'snapshot' || eventType === 'reset') {
          setSessionOutputs(prev => ({
            ...prev,
            [model]: clampOutput(content),
          }));
          setStreamErrors(prev => ({ ...prev, [model]: null }));
        } else if (eventType === 'append') {
          setSessionOutputs(prev => {
            const existing = prev[model] ?? '';
            return {
              ...prev,
              [model]: clampOutput(existing + content),
            };
          });
          setStreamErrors(prev => ({ ...prev, [model]: null }));
        }
      } catch (error) {
        console.error('Failed to parse stream message:', error);
      }
    };

    socket.onclose = () => {
      const wasPlanned = closingSocketsRef.current.delete(model);
      delete socketsRef.current[model];
      if (!wasPlanned) {
        const nextStatus: StreamStatus = projectStateRef.current === 'idle' ? 'idle' : 'error';
        setStreamStatuses(prev => ({ ...prev, [model]: nextStatus }));
        if (projectStateRef.current !== 'idle') {
          setStreamErrors(prev => ({ ...prev, [model]: prev[model] ?? 'Connection closed' }));
          setTimeout(() => ensureSocket(model), 1000);
        } else {
          setStreamErrors(prev => ({ ...prev, [model]: null }));
        }
      } else {
        setStreamErrors(prev => ({ ...prev, [model]: null }));
      }
    };
  }, [clampOutput, toWebSocketUrl]);

  useEffect(() => {
    if (projectState === 'idle') {
      closeAllSockets('idle');
      return;
    }

    const activeSet = new Set(activeModels);
    Object.keys(socketsRef.current).forEach(model => {
      if (!activeSet.has(model)) {
        closeSocket(model);
      }
    });

    activeModels.forEach(model => {
      ensureSocket(model);
    });
  }, [projectState, activeModels, closeAllSockets, closeSocket, ensureSocket]);

  useEffect(() => {
    return () => {
      closeAllSockets('idle');
    };
  }, [closeAllSockets]);

  useEffect(() => {
    const activeIds = allConversations
      .filter(c => activeModels.includes(c.title))
      .map(c => c.id);
    setSelectedCoders(activeIds);
  }, [activeModels, allConversations]);

  const handleSendPrompt = (prompt: string, coderIds: number[]) => {
    console.log('Sending prompt to coders:', coderIds, prompt);
  };

  const postControl = async (path: string) => {
    const url = (() => {
      if (/^https?:\/\//.test(path)) {
        return path;
      }
      const normalizedPath = path.startsWith('/') ? path : `/${path}`;
      return `${API_BASE_URL}${normalizedPath}`;
    })();

    const response = await fetch(url, { method: 'POST' });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const data = await response.json();
        if (data?.detail) {
          detail = data.detail;
        }
      } catch {
        // ignore JSON parsing errors and fall back to status text
      }
      throw new Error(detail);
    }
    return response.json().catch(() => ({}));
  };

  const postKey = (modelSlug: string, key: string) => {
    const encodedKey = encodeURIComponent(key);
    return postControl(`/api/control/${modelSlug}/key/${encodedKey}`);
  };

  const handleControlAction = async (modelName: string, action: string) => {
    const modelSlug = modelName.trim().toLowerCase();
    try {
      switch (action) {
        case 'escape': {
          await postKey(modelSlug, 'Escape');
          await postControl('/api/control/pause');
          setProjectState('paused');
          break;
        }
        case 'resume': {
          await postControl('/api/control/resume');
          setProjectState('running');
          break;
        }
        case 'up': {
          await postKey(modelSlug, 'Up');
          break;
        }
        case 'down': {
          await postKey(modelSlug, 'Down');
          break;
        }
        case 'enter': {
          await postKey(modelSlug, 'Enter');
          break;
        }
        case 'close': {
          console.warn(`Close action requested for ${modelName} but no handler is implemented yet.`);
          break;
        }
        default: {
          console.warn(`Unhandled control action: ${action} for ${modelName}`);
        }
      }
    } catch (error) {
      console.error(`Failed to send ${action} for ${modelName}:`, error);
    }
  };

  const handleStartProject = () => {
    if (activeModels.length === 0) {
      return;
    }

    setSessionOutputs(prev => {
      const next = { ...prev };
      activeModels.forEach(model => {
        next[model] = '';
      });
      return next;
    });

    setStreamErrors(prev => {
      const next = { ...prev };
      activeModels.forEach(model => {
        next[model] = null;
      });
      return next;
    });

    setProjectState('running');
    // In the future, this will also trigger a backend call
  };

  const handleStopProject = () => {
    closeAllSockets('idle');
    setProjectState('idle');
    // In the future, this will also trigger a backend call
  };

  const handleEditInstructions = (modelName: string) => {
    setEditingModelName(modelName);
    setIsEditModalOpen(true);
  };

  const activeConversations = allConversations.filter(c => activeModels.includes(c.title));

  // Determine grid columns based on the number of conversations
  const gridColsClass = activeConversations.length === 1 ? 'grid-cols-1' : 'grid-cols-2';

  // For demonstration, let's assign some statuses
  const getStatusForCoder = (title: string) => {
    const streamStatus = streamStatuses[title] ?? 'idle';
    if (streamStatus === 'error') {
      return 'error';
    }
    if (streamStatus === 'connecting') {
      return 'processing';
    }
    return 'ready';
  };

  return (
    <div className="min-h-screen bg-[#1e1e1e] text-gray-100 flex flex-col">
      <header className="py-8 text-center border-b border-gray-700">
        <h1 className="text-5xl font-bold text-white tracking-tight">
          Orchestrator
        </h1>
        <div className="flex justify-center items-center gap-8 mt-4">
          <div className={`${projectState === 'running' ? 'opacity-50 pointer-events-none' : ''}`}>
            <SessionModelSelector
              allModels={allConversations.map(c => c.title)}
              activeModels={activeModels}
              onActiveModelsChange={setActiveModels}
            />
          </div>
          {projectState === 'idle' ? (
            <button
              onClick={handleStartProject}
              disabled={activeModels.length === 0}
              className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Start Project
            </button>
          ) : (
            <button
              onClick={handleStopProject}
              className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-all duration-200"
            >
              Stop Project
            </button>
          )}
          <button 
            onClick={() => setIsSettingsModalOpen(true)} 
            className={`text-gray-400 hover:text-white ${projectState === 'running' ? 'opacity-50 cursor-not-allowed' : ''}`}
            disabled={projectState === 'running'}
          >
            <Settings size={24} />
          </button>
        </div>
        <div className={`text-center mt-2 text-sm text-gray-500 ${projectState === 'running' ? 'opacity-50' : ''}`}>
          Project Directory: {projectDirectory}
        </div>
      </header>

      <main className="flex-1 p-8 pb-32 overflow-hidden min-h-0">
        <div className={`max-w-[1600px] mx-auto grid ${gridColsClass} gap-6 h-full min-h-0 auto-rows-[32rem]`}>
          {activeConversations.map((conversation) => (
            <ConversationWindow
              key={conversation.id}
              conversation={conversation}
              onControlAction={handleControlAction}
              status={getStatusForCoder(conversation.title)}
              projectState={projectState}
              onEditInstructions={handleEditInstructions}
              output={sessionOutputs[conversation.title] ?? ''}
              streamStatus={streamStatuses[conversation.title] ?? 'idle'}
              errorMessage={streamErrors[conversation.title] ?? null}
            />
          ))}
          {activeConversations.length === 3 && <div className="col-span-1"></div> /* Blank space for 3 conversations */}
        </div>
      </main>

      {projectState === 'running' && (
        <PromptInput
          coders={activeConversations}
          selectedCoders={selectedCoders}
          onSelectedCodersChange={setSelectedCoders}
          onSendPrompt={handleSendPrompt}
        />
      )}

      <EditInstructionsModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        modelName={editingModelName}
        projectDirectory={projectDirectory}
      />

      <ProjectSettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        projectDirectory={projectDirectory}
        onProjectDirectoryChange={setProjectDirectory}
      />
    </div>
  );
}

export default App;
