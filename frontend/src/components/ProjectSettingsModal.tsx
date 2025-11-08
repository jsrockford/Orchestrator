import React, { useState, useEffect } from 'react';
import { Folder, File, ArrowUp } from 'lucide-react';
import { DiscussionSettings } from '../types';

interface ProjectSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectDirectory: string;
  discussionSettings: DiscussionSettings;
  availableModels: string[];
  onSave: (directory: string, settings: DiscussionSettings) => Promise<void> | void;
}

interface FileSystemItem {
  name: string;
  is_dir: boolean;
  path: string;
}

const ProjectSettingsModal: React.FC<ProjectSettingsModalProps> = ({
  isOpen,
  onClose,
  projectDirectory,
  discussionSettings,
  availableModels,
  onSave,
}) => {
  const [currentPath, setCurrentPath] = useState(projectDirectory);
  const [contents, setContents] = useState<FileSystemItem[]>([]);
  const [newFolderName, setNewFolderName] = useState('');
  const [localSettings, setLocalSettings] = useState<DiscussionSettings>(discussionSettings);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const browsePath = (path: string) => {
    console.log("Browsing to:", path);
    fetch('http://localhost:8000/api/fs/browse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
      .then(res => res.json())
      .then(data => {
        if (data.detail) { // Handle backend errors
          console.error("Backend error:", data.detail);
          return;
        }
        setCurrentPath(data.path);
        // Sort contents alphabetically, directories first
        const sortedContents = data.contents.sort((a: FileSystemItem, b: FileSystemItem) => {
          if (a.is_dir && !b.is_dir) return -1;
          if (!a.is_dir && b.is_dir) return 1;
          return a.name.localeCompare(b.name);
        });
        setContents(sortedContents);
      })
      .catch(err => console.error("Error browsing path:", err));
  };

  useEffect(() => {
    if (isOpen) {
      browsePath(projectDirectory);
      const fallbackModel = availableModels.includes(discussionSettings.startingModel)
        ? discussionSettings.startingModel
        : availableModels[0] ?? discussionSettings.startingModel;
      setLocalSettings({
        ...discussionSettings,
        startingModel: fallbackModel,
      });
    }
  }, [isOpen, projectDirectory, discussionSettings, availableModels]);

  const handleCreateFolder = () => {
    if (newFolderName.trim()) {
      const folderData = { path: currentPath, folderName: newFolderName };
      console.log("Creating folder with data:", folderData);
      fetch('http://localhost:8000/api/fs/create-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(folderData),
      })
        .then(res => res.json())
        .then(data => {
          if (data.detail) {
            console.error("Backend error:", data.detail);
          } else {
            const newPath = currentPath === '/' ? `/${newFolderName}` : `${currentPath}/${newFolderName}`;
            setNewFolderName('');
            browsePath(newPath); // Navigate into the new folder
          }
        })
        .catch(err => console.error("Error creating folder:", err));
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      // First, prepare instruction files in the project directory
      const prepareResponse = await fetch('http://localhost:8000/api/fs/prepare-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: currentPath }),
      });

      if (!prepareResponse.ok) {
        throw new Error(`Failed to prepare project directory: ${prepareResponse.statusText}`);
      }

      const prepareData = await prepareResponse.json();
      console.log('Project prepared:', prepareData);

      // Then save the settings
      await onSave(currentPath, localSettings);
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save settings';
      setSaveError(message);
    } finally {
      setSaving(false);
    }
  };

  const handleNavigateUp = () => {
    const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
    // If at root, stay at root
    if (parentPath === '') {
      browsePath('/');
    } else {
      browsePath(parentPath);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-[#252526] rounded-lg shadow-xl w-1/2 h-3/4 flex flex-col">
        <div className="p-4 border-b border-[#3e4451]">
          <h2 className="text-xl font-semibold">Select Project Directory</h2>
          <div className="text-sm text-gray-400 mt-1">{currentPath}</div>
        </div>
        <div className="p-4 flex-1 overflow-y-auto">
          <button onClick={handleNavigateUp} className="flex items-center gap-2 text-gray-400 hover:text-white mb-2">
            <ArrowUp size={16} /> Up
          </button>
          <ul>
            {contents.map(item => (
              <li key={item.name} 
                  onClick={() => item.is_dir && browsePath(item.path)}
                  className={`flex items-center gap-2 p-1 rounded cursor-pointer ${item.is_dir ? 'hover:bg-gray-700' : 'text-gray-500'}`}>
                {item.is_dir ? <Folder size={16} /> : <File size={16} />}
                {item.name}
              </li>
            ))}
          </ul>
        </div>
        <div className="p-4 border-t border-[#3e4451]">
          <div className="flex gap-2">
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="New folder name..."
              className="flex-1 bg-[#1e1e1e] border border-[#3e4451] rounded-lg p-2 text-gray-200"
            />
            <button onClick={handleCreateFolder} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg">Create Folder</button>
          </div>
        </div>
        <div className="p-4 border-t border-[#3e4451] text-left space-y-4">
          <h3 className="text-lg font-semibold">Discussion Settings</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm text-gray-400">Max Turns</label>
              <input
                type="number"
                min={1}
                max={100}
                value={localSettings.maxTurns}
                onChange={(e) => setLocalSettings(prev => ({ ...prev, maxTurns: Number(e.target.value) || 1 }))}
                className="bg-[#1e1e1e] border border-[#3e4451] rounded-lg p-2 text-gray-200"
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm text-gray-400">Starting Model</label>
              <select
                value={localSettings.startingModel}
                onChange={(e) => setLocalSettings(prev => ({ ...prev, startingModel: e.target.value }))}
                className="bg-[#1e1e1e] border border-[#3e4451] rounded-lg p-2 text-gray-200"
              >
                {availableModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-2 md:col-span-2">
              <label className="text-sm text-gray-400">Discussion Topic</label>
              <textarea
                value={localSettings.discussionTopic}
                onChange={(e) => setLocalSettings(prev => ({ ...prev, discussionTopic: e.target.value }))}
                placeholder="Describe the goal or topic for the discussion..."
                className="bg-[#1e1e1e] border border-[#3e4451] rounded-lg p-2 text-gray-200 h-24"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                id="include-history"
                type="checkbox"
                checked={localSettings.includeHistory}
                onChange={(e) => setLocalSettings(prev => ({ ...prev, includeHistory: e.target.checked }))}
              />
              <label htmlFor="include-history" className="text-sm text-gray-300">Include conversation history in prompts</label>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm text-gray-400">Log Level</label>
              <select
                value={localSettings.logLevel}
                onChange={(e) => setLocalSettings(prev => ({ ...prev, logLevel: e.target.value }))}
                className="bg-[#1e1e1e] border border-[#3e4451] rounded-lg p-2 text-gray-200"
              >
                {['DEBUG', 'INFO', 'WARNING', 'ERROR'].map(level => (
                  <option key={level} value={level}>{level}</option>
                ))}
              </select>
            </div>
          </div>
          {saveError && <div className="text-sm text-red-400">{saveError}</div>}
        </div>
        <div className="p-4 border-t border-[#3e4451] flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg">Cancel</button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save & Close'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProjectSettingsModal;
