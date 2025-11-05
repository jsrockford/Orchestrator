import { useState, useEffect } from 'react';
import { Settings } from 'lucide-react';
import ConversationWindow from './components/ConversationWindow';
import PromptInput from './components/PromptInput';
import SessionModelSelector from './components/SessionModelSelector';
import EditInstructionsModal from './components/EditInstructionsModal';
import ProjectSettingsModal from './components/ProjectSettingsModal';

function App() {
  const [allConversations] = useState([
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

  const handleControlAction = (coderId: number, action: string) => {
    console.log(`Action ${action} triggered for AI Coder ${coderId}`);
  };

  const handleStartProject = () => {
    if (activeModels.length > 0) {
      setProjectState('running');
      // In the future, this will also trigger a backend call
    }
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
    if (title === 'Claude') return 'processing';
    if (title === 'Codex') return 'error';
    return 'ready';
  };

  return (
    <div className="min-h-screen bg-[#1e1e1e] text-gray-100 flex flex-col">
      <header className="py-8 text-center border-b border-gray-700">
        <h1 className="text-5xl font-bold text-white tracking-tight">
          Orchestrator
        </h1>
        <div className="flex justify-center items-center gap-8 mt-4">
          <SessionModelSelector
            allModels={allConversations.map(c => c.title)}
            activeModels={activeModels}
            onActiveModelsChange={setActiveModels}
          />
          <button
            onClick={handleStartProject}
            disabled={activeModels.length === 0 || projectState !== 'idle'}
            className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Project
          </button>
          <button onClick={() => setIsSettingsModalOpen(true)} className="text-gray-400 hover:text-white">
            <Settings size={24} />
          </button>
        </div>
        <div className="text-center mt-2 text-sm text-gray-500">
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
