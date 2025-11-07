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
  const [projectActionPending, setProjectActionPending] = useState(false);

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

  const handleSendPrompt = async (prompt: string, coderIds: number[]) => {
    const modelNames = coderIds
      .map(id => allConversations.find(c => c.id === id)?.title)
      .filter(Boolean) as string[];

    if (modelNames.length === 0) {
      console.warn('No models selected for prompt');
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/control/send-prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          models: modelNames,
          submit: true
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('Prompt sent:', data);

      // Check for any failures and show errors
      const failures = Object.entries(data.results)
        .filter(([_, result]: [string, any]) => !result.success)
        .map(([model, result]: [string, any]) => `${model}: ${result.error}`);

      if (failures.length > 0) {
        console.error('Failed to send to some models:', failures);
        alert(`Failed to send prompt to:\n${failures.join('\n')}`);
      }
    } catch (error) {
      console.error('Failed to send prompt:', error);
      alert(`Error sending prompt: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const postControl = async (path: string, options: RequestInit = {}) => {
    const url = (() => {
      if (/^https?:\/\//.test(path)) {
        return path;
      }
      const normalizedPath = path.startsWith('/') ? path : `/${path}`;
      return `${API_BASE_URL}${normalizedPath}`;
    })();

    const response = await fetch(url, { method: 'POST', ...options });
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
        case 'kill': {
          const confirmed = window.confirm(
            `KILL ${modelName}?\n\nThis will immediately terminate the session for ${modelName}.\n\nAre you sure?`
          );
          if (!confirmed) {
            break;
          }

          try {
            const response = await fetch(`${API_BASE_URL}/api/control/stop-sessions`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ models: [modelSlug] })
            });

            if (!response.ok) {
              throw new Error(`Failed to kill ${modelName}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log(`Kill response for ${modelName}:`, data);

            // Close the WebSocket for this model
            closeSocket(modelName, 'idle');

            // If no models are running anymore, update project state
            if (data.stopped?.includes(modelSlug)) {
              alert(`${modelName} has been terminated.`);

              // Check if any other models are still running
              const stillRunning = activeModels.some(m =>
                m.toLowerCase() !== modelSlug &&
                socketsRef.current[m]
              );

              if (!stillRunning) {
                setProjectState('idle');
              }
            }
          } catch (error) {
            console.error(`Failed to kill ${modelName}:`, error);
            alert(`Failed to kill ${modelName}: ${error instanceof Error ? error.message : String(error)}`);
          }
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

  const handleStartProject = async () => {
    if (activeModels.length === 0 || projectState !== 'idle' || projectActionPending) {
      return;
    }

    setProjectActionPending(true);
    try {
      const payload = {
        project_directory: projectDirectory,
        models: activeModels.map(model => model.trim().toLowerCase()),
      };
      const data = await postControl('/api/control/start-sessions', {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const startedCount = (data?.started?.length ?? 0) + (data?.already_running?.length ?? 0);
      if (!startedCount) {
        const failureMessage = Array.isArray(data?.failed) && data.failed.length > 0
          ? data.failed.map((entry: { error?: string }) => entry?.error ?? 'unknown error').join('; ')
          : 'No sessions started';
        throw new Error(failureMessage);
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
    } catch (error) {
      console.error('Failed to start project:', error);
    } finally {
      setProjectActionPending(false);
    }
  };

  const handleStopProject = async () => {
    if (projectState === 'idle' || projectActionPending) {
      return;
    }

    setProjectActionPending(true);
    try {
      const payload = {
        models: activeModels.map(model => model.trim().toLowerCase()),
      };
      await postControl('/api/control/stop-sessions', {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      console.error('Failed to stop project:', error);
    } finally {
      closeAllSockets('idle');
      setProjectState('idle');
      setProjectActionPending(false);
    }
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
              disabled={activeModels.length === 0 || projectActionPending}
              className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {projectActionPending ? 'Starting...' : 'Start Project'}
            </button>
          ) : (
            <button
              onClick={handleStopProject}
              disabled={projectActionPending}
              className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {projectActionPending ? 'Stopping...' : 'Stop Project'}
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
          disabled={projectState === 'idle'}
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
