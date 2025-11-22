import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { MacroCategory, MacroDefinition } from '../types';

type MacroEntry = {
  name: string;
  macro: MacroDefinition;
};

interface MacroDropdownProps {
  agent: string;
  category: MacroCategory;
  macros: MacroEntry[];
  disabled?: boolean;
  onSelect: (macroName: string) => void;
}

const categoryIcon: Record<string, string> = {
  slash: '/',
  ctrl: 'Ctrl',
  shift: '⇧',
  other: '⋯',
};

const formatKeys = (keys?: string[]) => {
  if (!keys || keys.length === 0) {
    return '';
  }

  return keys
    .map(key => {
      if (/^C[-+]/i.test(key)) {
        return `Ctrl+${key.slice(2).toUpperCase()}`;
      }
      if (/^S[-+]/i.test(key)) {
        return `Shift+${key.slice(2)}`;
      }
      return key;
    })
    .join(' ');
};

function MacroDropdown({ agent, category, macros, disabled, onSelect }: MacroDropdownProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const icon = categoryIcon[category] ?? categoryIcon.other;

  const sortedMacros = useMemo(() => {
    return [...macros].sort((a, b) => {
      const aLabel = a.macro.description || a.name;
      const bLabel = b.macro.description || b.name;
      return aLabel.localeCompare(bLabel);
    });
  }, [macros]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  if (!sortedMacros.length) {
    return null;
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        className={`flex items-center gap-1 rounded-md border border-gray-500/60 bg-[#1e1e1e] px-2 py-1 text-xs font-semibold text-gray-200 hover:bg-[#2b2b2b] transition ${
          disabled ? 'opacity-50 cursor-not-allowed' : ''
        }`}
        onClick={() => setOpen(prev => !prev)}
        disabled={disabled}
        title={`Macros for ${agent} (${category})`}
      >
        <span>{icon}</span>
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-80 max-w-[22rem] rounded-md border border-gray-600 bg-[#1c1c1c] shadow-xl">
          <div className="px-3 py-2 text-[10px] uppercase tracking-wide text-gray-400 border-b border-gray-700 whitespace-nowrap overflow-hidden text-ellipsis">
            {agent} • {category}
          </div>
          <ul className="max-h-64 overflow-y-auto divide-y divide-gray-800">
            {sortedMacros.map(({ name, macro }) => {
              const shortcut = formatKeys(macro.keys);
              const label = macro.description || name;
              const secondary = macro.command || shortcut;
              return (
                <li key={name}>
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm text-gray-100 hover:bg-gray-800"
                    onClick={() => {
                      onSelect(name);
                      setOpen(false);
                    }}
                    disabled={disabled}
                    title={`${label}${secondary ? ` — ${secondary}` : ''}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="whitespace-normal break-words">{label}</span>
                      {secondary && (
                        <span className="text-[11px] text-gray-400 whitespace-nowrap">
                          {secondary}
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

export default MacroDropdown;
