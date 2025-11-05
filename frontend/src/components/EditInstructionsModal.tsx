import React, { useState, useEffect } from 'react';

interface EditInstructionsModalProps {
  modelName: string;
  isOpen: boolean;
  onClose: () => void;
}

const EditInstructionsModal: React.FC<EditInstructionsModalProps> = ({ modelName, isOpen, onClose }) => {
  const [content, setContent] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && modelName) {
      setIsLoading(true);
      fetch(`http://localhost:8000/api/instructions/${modelName}`)
        .then(res => res.json())
        .then(data => setContent(data.content))
        .catch(err => console.error("Error fetching instructions:", err))
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, modelName]);

  const handleSave = () => {
    fetch(`http://localhost:8000/api/instructions/${modelName}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
      .then(res => {
        if (res.ok) {
          onClose();
        } else {
          console.error("Error saving instructions");
        }
      })
      .catch(err => console.error("Error saving instructions:", err));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-[#252526] rounded-lg shadow-xl w-1/2 h-3/4 flex flex-col">
        <div className="p-4 border-b border-[#3e4451]">
          <h2 className="text-xl font-semibold">Edit Instructions for {modelName}</h2>
        </div>
        <div className="p-4 flex-1">
          {isLoading ? (
            <div>Loading...</div>
          ) : (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full h-full bg-[#1e1e1e] border border-[#3e4451] rounded-lg p-4 text-gray-200 resize-none"
            />
          )}
        </div>
        <div className="p-4 border-t border-[#3e4451] flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg">Cancel</button>
          <button onClick={handleSave} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg">Save</button>
        </div>
      </div>
    </div>
  );
};

export default EditInstructionsModal;
