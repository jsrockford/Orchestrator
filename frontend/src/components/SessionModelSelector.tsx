import React from 'react';

interface SessionModelSelectorProps {
  allModels: string[];
  activeModels: string[];
  onActiveModelsChange: (activeModels: string[]) => void;
}

const SessionModelSelector: React.FC<SessionModelSelectorProps> = ({ allModels, activeModels, onActiveModelsChange }) => {
  const toggleModel = (model: string) => {
    const newActiveModels = activeModels.includes(model)
      ? activeModels.filter((m) => m !== model)
      : [...activeModels, model];
    onActiveModelsChange(newActiveModels);
  };

  return (
    <div className="flex justify-center items-center gap-4 py-4">
      <span className="text-gray-400 font-semibold">Active Models:</span>
      {allModels.map((model) => (
        <label key={model} className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={activeModels.includes(model)}
            onChange={() => toggleModel(model)}
            className="w-4 h-4 rounded border-[#3e4451] bg-[#1e1e1e] text-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer"
          />
          <span className="text-gray-200">{model}</span>
        </label>
      ))}
    </div>
  );
};

export default SessionModelSelector;
