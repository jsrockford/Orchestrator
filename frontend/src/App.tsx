import { useState, useEffect, useCallback, useRef } from 'react';
import { Settings } from 'lucide-react';
import ConversationWindow, { type Conversation } from './components/ConversationWindow';
import PromptInput from './components/PromptInput';
import SessionModelSelector from './components/SessionModelSelector';
import EditInstructionsModal from './components/EditInstructionsModal';
import ProjectSettingsModal from './components/ProjectSettingsModal';
import ModelSettingsModal from './components/ModelSettingsModal';
import { DiscussionSettings, DiscussionState } from './types';

const DEFAULT_API_BASE = 'http://localhost:9100';
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
  const [isModelSettingsModalOpen, setIsModelSettingsModalOpen] = useState(false);
  const [modelSettingsModelName, setModelSettingsModelName] = useState('');
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
  const [discussionSettings, setDiscussionSettings] = useState<DiscussionSettings>({
    maxTurns: 10,
    startingModel: 'Claude',
    discussionTopic: '',
    includeHistory: true,
    logLevel: 'INFO',
  });
  const [discussionState, setDiscussionState] = useState<DiscussionState>('idle');
  const [discussionStatus, setDiscussionStatus] = useState<{ turn: number | null; speaker: string | null; topic: string | null }>({
    turn: null,
    speaker: null,
    topic: null,
  });
  const [discussionActionPending, setDiscussionActionPending] = useState(false);
  const [discussionError, setDiscussionError] = useState<string | null>(null);

  const socketsRef = useRef<Record<string, WebSocket>>({});
  const closingSocketsRef = useRef<Set<string>>(new Set());
  const projectStateRef = useRef(projectState);
  const activeModelsRef = useRef<string[]>(activeModels);
  const previousDiscussionStateRef = useRef<DiscussionState>('idle');

  useEffect(() => {
    projectStateRef.current = projectState;
  }, [projectState]);

  useEffect(() => {
    activeModelsRef.current = activeModels;
  }, [activeModels]);

  useEffect(() => {
    if (projectState === 'idle') {
      setDiscussionState('idle');
      setDiscussionStatus({ turn: null, speaker: null, topic: null });
      setDiscussionError(null);
    }
  }, [projectState]);

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

  useEffect(() => {
    if (projectState === 'idle') {
      return;
    }

    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/discussion/status`);
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        if (cancelled || !data) {
          return;
        }
        const normalizedState = String(data.discussion_state ?? 'idle').toLowerCase() as DiscussionState;

        // Detect discussion completion
        if (normalizedState === 'idle' && previousDiscussionStateRef.current === 'running') {
          const turnCount = data.manager?.turn_counter ?? 0;
          alert(`✅ Discussion completed! Total turns: ${turnCount}`);
        }

        previousDiscussionStateRef.current = normalizedState;
        setDiscussionState(normalizedState);
        setDiscussionStatus({
          turn: data.manager?.turn_counter ?? null,
          speaker: data.manager?.current_agent ?? null,
          topic: data.config?.discussion_topic ?? null,
        });
        setDiscussionError(data.error ?? null);
      } catch (error) {
        if (!cancelled) {
          console.warn('Failed to fetch discussion status:', error);
        }
      }
    };

    fetchStatus();
    const intervalId = window.setInterval(fetchStatus, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [projectState]);

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

  const configureDiscussion = async (override?: DiscussionSettings) => {
    if (activeModels.length < 2) {
      throw new Error('Select at least two models before configuring a discussion');
    }

    const settings = override ?? discussionSettings;
    let startingModel = settings.startingModel;
    if (!activeModels.includes(startingModel)) {
      startingModel = activeModels[0];
    }

    const topicText = (settings.discussionTopic ?? '').trim();
    const payload = {
      max_turns: settings.maxTurns,
      starting_model: startingModel.trim().toLowerCase(),
      participants: activeModels.map(model => model.trim().toLowerCase()),
      discussion_topic: topicText || null,
      include_history: settings.includeHistory,
      log_level: settings.logLevel ? settings.logLevel.toUpperCase() : null,
    };

    await postControl('/api/discussion/configure', {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  const handleSaveSettings = async (directory: string, settings: DiscussionSettings) => {
    setProjectDirectory(directory);
    setDiscussionSettings(settings);
    try {
      await configureDiscussion(settings);
    } catch (error) {
      console.error('Failed to save discussion settings:', error);
      throw error;
    }
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
          if (discussionState === 'running') {
            setDiscussionState('paused');
          }
          break;
        }
        case 'resume': {
          await postControl('/api/control/resume');
          setProjectState('running');
          if (discussionState === 'paused') {
            setDiscussionState('running');
          }
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
      setDiscussionState('idle');
      setDiscussionStatus({ turn: null, speaker: null, topic: null });
      setDiscussionError(null);
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
      if (discussionState !== 'idle') {
        try {
          await postControl('/api/discussion/stop');
        } catch (error) {
          console.error('Failed to stop discussion before closing project:', error);
        }
        setDiscussionState('idle');
        setDiscussionStatus({ turn: null, speaker: null, topic: null });
      }

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
      setDiscussionError(null);
      setProjectActionPending(false);
    }
  };

  const handleStartDiscussion = async () => {
    if (projectState !== 'running') {
      alert('Open the project before starting a discussion.');
      return;
    }
    if (activeModels.length < 2) {
      alert('Select at least two models to start a discussion.');
      return;
    }
    setDiscussionActionPending(true);
    try {
      await configureDiscussion();
      await postControl('/api/discussion/start');
      setDiscussionState('running');
      setDiscussionError(null);
    } catch (error) {
      console.error('Failed to start discussion:', error);
      alert(`Failed to start discussion: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setDiscussionActionPending(false);
    }
  };

  const handleStopDiscussion = async () => {
    setDiscussionActionPending(true);
    try {
      await postControl('/api/discussion/stop');
    } catch (error) {
      console.error('Failed to stop discussion:', error);
      alert(`Failed to stop discussion: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setDiscussionState('idle');
      setDiscussionStatus({ turn: null, speaker: null, topic: null });
      setDiscussionError(null);
      setDiscussionActionPending(false);
    }
  };

  const handleEditInstructions = (modelName: string) => {
    setEditingModelName(modelName);
    setIsEditModalOpen(true);
  };

  const handleConfigureModelSettings = (modelName: string) => {
    setModelSettingsModelName(modelName);
    setIsModelSettingsModalOpen(true);
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

  const discussionSummary = (() => {
    if (discussionState === 'idle') {
      return 'Discussion idle';
    }

    const parts: string[] = [
      discussionState === 'running' ? 'Discussion running' : 'Discussion paused',
    ];
    if (discussionStatus.turn !== null) {
      parts.push(`Turn ${discussionStatus.turn}`);
    }
    if (discussionStatus.speaker) {
      parts.push(`Speaker: ${discussionStatus.speaker}`);
    }
    if (discussionStatus.topic) {
      parts.push(`Topic: ${discussionStatus.topic}`);
    }
    return parts.join(' • ');
  })();

  return (
    <div className="min-h-screen bg-[#1e1e1e] text-gray-100 flex flex-col">
      <header className="py-8 text-center border-b border-gray-700">
        <h1 className="text-5xl font-bold text-white tracking-tight">
          Orchestrator
        </h1>
        <div className="mt-4 flex flex-col items-center gap-4">
          <div className="flex flex-wrap justify-center items-center gap-4">
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
                {projectActionPending ? 'Opening...' : 'Start Models'}
              </button>
            ) : (
              <button
                onClick={handleStopProject}
                disabled={projectActionPending}
                className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {projectActionPending ? 'Closing...' : 'Close Models'}
              </button>
            )}
            {discussionState === 'idle' ? (
              <button
                onClick={handleStartDiscussion}
                disabled={projectState !== 'running' || activeModels.length < 2 || discussionActionPending}
                className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {discussionActionPending ? 'Starting...' : 'Start Discussion'}
              </button>
            ) : (
              <button
                onClick={handleStopDiscussion}
                disabled={discussionActionPending}
                className="px-6 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {discussionActionPending ? 'Stopping...' : 'Stop Discussion'}
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
          <div className="text-sm text-gray-400 space-y-1">
            <div>Project Directory: {projectDirectory}</div>
            <div>{discussionSummary}</div>
            {discussionError && <div className="text-red-400">Discussion error: {discussionError}</div>}
          </div>
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
              onConfigureSettings={handleConfigureModelSettings}
              output={sessionOutputs[conversation.title] ?? ''}
              streamStatus={streamStatuses[conversation.title] ?? 'idle'}
              errorMessage={streamErrors[conversation.title] ?? null}
            />
          ))}
          {activeConversations.length === 3 && <div className="col-span-1"></div> /* Blank space for 3 conversations */}
        </div>
      </main>

      {projectState !== 'idle' && (
        <PromptInput
          coders={activeConversations}
          selectedCoders={selectedCoders}
          onSelectedCodersChange={setSelectedCoders}
          onSendPrompt={handleSendPrompt}
          disabled={projectState === 'idle' || discussionState === 'running'}
        />
      )}

      <EditInstructionsModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        modelName={editingModelName}
        projectDirectory={projectDirectory}
        apiBaseUrl={API_BASE_URL}
      />

      <ProjectSettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        projectDirectory={projectDirectory}
        discussionSettings={discussionSettings}
        availableModels={allConversations.map(c => c.title)}
        onSave={handleSaveSettings}
        apiBaseUrl={API_BASE_URL}
      />

      <ModelSettingsModal
        isOpen={isModelSettingsModalOpen}
        onClose={() => {
          setIsModelSettingsModalOpen(false);
          setModelSettingsModelName('');
        }}
        modelName={modelSettingsModelName}
        projectDirectory={projectDirectory}
        apiBaseUrl={API_BASE_URL}
      />
    </div>
  );
}

export default App;
