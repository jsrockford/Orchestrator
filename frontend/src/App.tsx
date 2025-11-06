import { useState, useEffect } from 'react';
import { Settings } from 'lucide-react';
import ConversationWindow, { type Conversation } from './components/ConversationWindow';
import PromptInput from './components/PromptInput';
import SessionModelSelector from './components/SessionModelSelector';
import EditInstructionsModal from './components/EditInstructionsModal';
import ProjectSettingsModal from './components/ProjectSettingsModal';

const DEFAULT_API_BASE = 'http://localhost:8000';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE).replace(/\/$/, '');

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
    if (activeModels.length > 0) {
      setProjectState('running');
      // In the future, this will also trigger a backend call
    }
  };

  const handleStopProject = () => {
    setProjectState('idle');
    // In the future, this will also trigger a backend call
  };

  const handleEditInstructions = (modelName: string) => {
    setEditingModelName(modelName);
    setIsEditModalOpen(true);
  };

  const activeConversations = allConversations.filter(c => activeModels.includes(c.title));

  // Determine grid columns based on the number of conversations
  const gridColsClass = activeConversations.length <= 2 ? 'grid-cols-1' : 'grid-cols-2';

  // For demonstration, let's assign some statuses
  const getStatusForCoder = (title: string) => {
    if (projectState === 'idle') return 'ready';
    // In a real scenario, these statuses would come from the backend
    // For now, let's keep them all 'ready' when running unless explicitly changed
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

      <main className="flex-1 p-8 pb-32">
        <div className={`max-w-[1600px] mx-auto grid ${gridColsClass} gap-6`}>
          {activeConversations.map((conversation) => (
            <ConversationWindow
              key={conversation.id}
              conversation={conversation}
              onControlAction={handleControlAction}
              status={getStatusForCoder(conversation.title)}
              projectState={projectState}
              onEditInstructions={handleEditInstructions}
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
