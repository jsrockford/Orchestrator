export type DiscussionState = 'idle' | 'running' | 'paused';

export interface DiscussionSettings {
  maxTurns: number;
  startingModel: string;
  discussionTopic: string;
  includeHistory: boolean;
  logLevel: string;
}

export type ModelSettingFieldType = 'number' | 'boolean' | 'text';
export type ModelSettingValueType = 'int' | 'float' | 'string' | 'boolean';

export interface ModelSettingsField {
  key: string;
  label: string;
  description?: string;
  type: ModelSettingFieldType;
  value_type: ModelSettingValueType;
  min?: number;
  max?: number;
  step?: number;
  default: number | boolean | string | null;
  value: number | boolean | string | null;
  overridden: boolean;
}

export interface ModelSettingsResponse {
  model: string;
  project_directory: string;
  fields: ModelSettingsField[];
  notes?: string;
}

export type MacroCategory = 'slash' | 'ctrl' | 'shift' | 'other' | string;

export interface MacroDefinition {
  description?: string;
  category?: MacroCategory;
  keys?: string[];
  command?: string;
}

export type MacroConfigMap = Record<string, Record<string, MacroDefinition>>;
