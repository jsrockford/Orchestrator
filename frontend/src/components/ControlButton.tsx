import { ReactNode } from 'react';

interface ControlButtonProps {
  icon: ReactNode | string;
  onClick: () => void;
  title: string;
}

function ControlButton({ icon, onClick, title }: ControlButtonProps) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="w-10 h-10 bg-[#3e4451] hover:bg-[#4e5461] border border-[#5a5f6e] rounded flex items-center justify-center text-gray-300 hover:text-white transition-all duration-200 hover:shadow-lg hover:border-[#6a7080]"
    >
      {typeof icon === 'string' ? (
        <span className="text-sm font-medium">{icon}</span>
      ) : (
        icon
      )}
    </button>
  );
}

export default ControlButton;
