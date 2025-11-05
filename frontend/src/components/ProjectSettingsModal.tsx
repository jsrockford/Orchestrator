import React, { useState, useEffect } from 'react';
import { Folder, File, ArrowUp } from 'lucide-react';

interface ProjectSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectDirectory: string;
  onProjectDirectoryChange: (newDirectory: string) => void;
}

interface FileSystemItem {
  name: string;
  is_dir: boolean;
  path: string;
}

const ProjectSettingsModal: React.FC<ProjectSettingsModalProps> = ({ isOpen, onClose, projectDirectory, onProjectDirectoryChange }) => {
  const [currentPath, setCurrentPath] = useState(projectDirectory);
  const [contents, setContents] = useState<FileSystemItem[]>([]);
  const [newFolderName, setNewFolderName] = useState('');

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
    }
  }, [isOpen, projectDirectory]);

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

  const handleSelectDirectory = () => {
    onProjectDirectoryChange(currentPath);
    onClose();
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
        <div className="p-4 border-t border-[#3e4451] flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg">Cancel</button>
          <button onClick={handleSelectDirectory} className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg">Select Current Directory</button>
        </div>
      </div>
    </div>
  );
};

export default ProjectSettingsModal;
