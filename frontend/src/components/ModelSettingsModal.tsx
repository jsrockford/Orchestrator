import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { ModelSettingsField } from '../types';

interface ModelSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  modelName: string;
  projectDirectory: string;
  apiBaseUrl: string;
}

type EditableField = {
  key: string;
  label: string;
  description?: string;
  type: ModelSettingsField['type'];
  valueType: ModelSettingsField['value_type'];
  min?: number;
  max?: number;
  step?: number;
  defaultValue: number | string | boolean | null;
  inputValue: string | boolean;
};

const formatDefault = (field: EditableField) => {
  if (field.type === 'boolean') {
    return typeof field.defaultValue === 'boolean'
      ? (field.defaultValue ? 'Enabled' : 'Disabled')
      : 'n/a';
  }
  if (
    field.defaultValue === null ||
    field.defaultValue === undefined ||
    field.defaultValue === ''
  ) {
    return 'n/a';
  }
  return String(field.defaultValue);
};

const formatRangeHint = (field: EditableField): string | null => {
  const hasMin = typeof field.min === 'number';
  const hasMax = typeof field.max === 'number';
  if (!hasMin && !hasMax) {
    return null;
  }
  if (hasMin && hasMax) {
    return `Allowed range: ${field.min} – ${field.max}`;
  }
  if (hasMin) {
    return `Minimum: ${field.min}`;
  }
  return `Maximum: ${field.max}`;
};

const resolveNumericValue = (field: EditableField): number => {
  const parsed = Number.parseFloat(String(field.inputValue ?? ''));
  if (!Number.isNaN(parsed)) {
    return parsed;
  }
  if (typeof field.defaultValue === 'number') {
    return field.defaultValue;
  }
  if (typeof field.min === 'number') {
    return field.min;
  }
  if (typeof field.max === 'number') {
    return field.max;
  }
  return 0;
};

const ModelSettingsModal: React.FC<ModelSettingsModalProps> = ({
  isOpen,
  onClose,
  modelName,
  projectDirectory,
  apiBaseUrl,
}) => {
  const [fields, setFields] = useState<EditableField[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [notes, setNotes] = useState<string | null>(null);

  const normalizedModel = (modelName || '').trim().toLowerCase();
  const baseUrl =
    normalizedModel.length > 0
      ? `${apiBaseUrl}/api/settings/model/${encodeURIComponent(normalizedModel)}`
      : null;
  const canSubmit = Boolean(projectDirectory) && !saving && !loading && Boolean(baseUrl);

  const mapFields = useCallback((incoming: ModelSettingsField[]): EditableField[] => {
    return incoming.map((field) => {
      const effectiveValue =
        field.value !== null && field.value !== undefined
          ? field.value
          : field.default;
      const isBoolean = field.type === 'boolean';
      return {
        key: field.key,
        label: field.label,
        description: field.description,
        type: field.type,
        valueType: field.value_type,
        min: field.min,
        max: field.max,
        step: field.step,
        defaultValue: field.default ?? null,
        inputValue: isBoolean
          ? Boolean(effectiveValue ?? field.default ?? false)
          : effectiveValue === null || effectiveValue === undefined
            ? ''
            : String(effectiveValue),
      };
    });
  }, []);

  const fetchSettings = useCallback(async () => {
    if (!isOpen || !baseUrl || !projectDirectory) {
      return;
    }
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const params = new URLSearchParams({ project_directory: projectDirectory });
      const response = await fetch(`${baseUrl}?${params.toString()}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || response.statusText);
      }
      const incomingFields: ModelSettingsField[] = Array.isArray(data?.fields)
        ? data.fields
        : [];
      setFields(mapFields(incomingFields));
      setNotes(typeof data?.notes === 'string' ? data.notes : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [baseUrl, projectDirectory, isOpen, mapFields]);

  useEffect(() => {
    if (isOpen) {
      void fetchSettings();
    } else {
      setFields([]);
      setError(null);
      setSuccessMessage(null);
      setNotes(null);
    }
  }, [isOpen, fetchSettings]);

  const handleFieldChange = (key: string, value: string | boolean) => {
    setFields((prev) =>
      prev.map((field) =>
        field.key === key ? { ...field, inputValue: value } : field,
      ),
    );
  };

  const buildOverrides = (): Record<string, number | string | boolean> | null => {
    const overrides: Record<string, number | string | boolean> = {};
    for (const field of fields) {
      if (field.type === 'boolean') {
        const boolValue = Boolean(field.inputValue);
        if (
          field.defaultValue === null ||
          typeof field.defaultValue !== 'boolean' ||
          boolValue !== field.defaultValue
        ) {
          overrides[field.key] = boolValue;
        }
        continue;
      }

      const rawInput = String(field.inputValue ?? '').trim();
      if (!rawInput) {
        continue;
      }

      if (field.valueType === 'int') {
        const parsed = Number.parseInt(rawInput, 10);
        if (Number.isNaN(parsed)) {
          setError(`Enter a whole number for ${field.label}.`);
          return null;
        }
        if (typeof field.min === 'number' && parsed < field.min) {
          setError(`${field.label} must be at least ${field.min}.`);
          return null;
        }
        if (typeof field.max === 'number' && parsed > field.max) {
          setError(`${field.label} must be at most ${field.max}.`);
          return null;
        }
        if (
          field.defaultValue === null ||
          typeof field.defaultValue !== 'number' ||
          parsed !== field.defaultValue
        ) {
          overrides[field.key] = parsed;
        }
        continue;
      }

      if (field.valueType === 'float') {
        const parsed = Number.parseFloat(rawInput);
        if (Number.isNaN(parsed)) {
          setError(`Enter a numeric value for ${field.label}.`);
          return null;
        }
        if (typeof field.min === 'number' && parsed < field.min) {
          setError(`${field.label} must be at least ${field.min}.`);
          return null;
        }
        if (typeof field.max === 'number' && parsed > field.max) {
          setError(`${field.label} must be at most ${field.max}.`);
          return null;
        }
        if (
          field.defaultValue === null ||
          typeof field.defaultValue !== 'number' ||
          parsed !== field.defaultValue
        ) {
          overrides[field.key] = parsed;
        }
        continue;
      }

      if (
        field.defaultValue === null ||
        typeof field.defaultValue !== 'string' ||
        rawInput !== field.defaultValue
      ) {
        overrides[field.key] = rawInput;
      }
    }
    return overrides;
  };

  const handleSave = async () => {
    if (!baseUrl || !projectDirectory) {
      setError('Select a project directory before editing settings.');
      return;
    }
    const overrides = buildOverrides();
    if (overrides === null) {
      return;
    }

    setSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await fetch(baseUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_directory: projectDirectory,
          overrides,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || response.statusText);
      }
      if (Object.keys(overrides).length === 0) {
        setSuccessMessage('All overrides cleared.');
      } else {
        setSuccessMessage('Overrides saved.');
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!baseUrl || !projectDirectory) {
      return;
    }
    setSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const params = new URLSearchParams({ project_directory: projectDirectory });
      const response = await fetch(`${baseUrl}?${params.toString()}`, {
        method: 'DELETE',
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || response.statusText);
      }
      setSuccessMessage('Overrides cleared.');
      await fetchSettings();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const modalTitle = useMemo(() => {
    if (!modelName) {
      return 'Model Settings';
    }
    return `${modelName} Settings`;
  }, [modelName]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-3xl rounded-lg bg-[#1f1f23] shadow-2xl border border-[#3e4451] flex flex-col max-h-[90vh]">
        <header className="px-6 py-4 border-b border-[#3e4451]">
          <h2 className="text-2xl font-semibold text-white">{modalTitle}</h2>
          <p className="mt-1 text-sm text-gray-400">
            Overrides apply per project session. Config defaults remain unchanged.
          </p>
          <p className="mt-1 text-xs text-gray-500 truncate">
            Project directory: {projectDirectory || 'Not selected'}
          </p>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {notes && (
            <div className="rounded border border-blue-400/40 bg-blue-500/10 px-4 py-2 text-sm text-blue-200">
              {notes}
            </div>
          )}

          {error && (
            <div className="rounded border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-200">
              {error}
            </div>
          )}

          {successMessage && (
            <div className="rounded border border-green-500/40 bg-green-500/10 px-4 py-2 text-sm text-green-200">
              {successMessage}
            </div>
          )}

          {loading && (
            <div className="text-sm text-gray-400">Loading model settings…</div>
          )}

          {!loading && fields.length === 0 && (
            <div className="text-sm text-gray-500">
              No configurable fields were found for this model.
            </div>
          )}

          {!loading && fields.length > 0 && (
            <div className="space-y-4">
              {fields.map((field) => {
                const rangeHint = formatRangeHint(field);
                const useSlider =
                  field.type !== 'text' &&
                  typeof field.min === 'number' &&
                  typeof field.max === 'number';
                const sliderValue = useSlider ? resolveNumericValue(field) : undefined;
                return (
                  <div
                    key={field.key}
                    className="rounded-lg border border-[#3e4451] bg-[#252526] p-4"
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <div>
                        <div className="font-semibold text-gray-100">
                          {field.label}
                        </div>
                        {field.description && (
                          <p className="text-xs text-gray-400">
                            {field.description}
                          </p>
                        )}
                        {rangeHint && (
                          <p className="text-xs text-gray-500">
                            {rangeHint}
                          </p>
                        )}
                      </div>
                      <div className="text-xs text-gray-500">
                        Default: {formatDefault(field)}
                      </div>
                    </div>
                    <div className="mt-3 space-y-2">
                      {field.type === 'boolean' ? (
                        <label className="inline-flex items-center gap-2 text-sm text-gray-200">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-gray-400 bg-transparent"
                            checked={Boolean(field.inputValue)}
                            onChange={(event) =>
                              handleFieldChange(field.key, event.target.checked)
                            }
                            disabled={saving}
                          />
                          <span>{Boolean(field.inputValue) ? 'Enabled' : 'Disabled'}</span>
                        </label>
                      ) : useSlider ? (
                        <>
                          <input
                            type="range"
                            min={field.min}
                            max={field.max}
                            step={field.step ?? (field.valueType === 'int' ? 1 : 0.1)}
                            value={String(sliderValue ?? field.min ?? 0)}
                            onChange={(event) =>
                              handleFieldChange(field.key, event.target.value)
                            }
                            disabled={saving}
                            className="w-full accent-blue-400"
                          />
                          <div className="flex items-center justify-between text-xs text-gray-400">
                            <span>{field.min}</span>
                            <span className="text-sm font-mono text-gray-100">
                              {Number.isFinite(sliderValue ?? NaN)
                                ? sliderValue
                                : field.defaultValue ?? ''}
                            </span>
                            <span>{field.max}</span>
                          </div>
                          <input
                            type="text"
                            inputMode="decimal"
                            value={field.inputValue as string}
                            onChange={(event) =>
                              handleFieldChange(field.key, event.target.value)
                            }
                            disabled={saving}
                            className="w-full rounded border border-[#3e4451] bg-[#1b1b1f] px-3 py-2 text-sm text-gray-100 focus:border-blue-400 focus:outline-none"
                            placeholder={String(sliderValue ?? '')}
                          />
                        </>
                      ) : (
                        <input
                          type="text"
                          inputMode={field.type === 'text' ? undefined : 'decimal'}
                          value={field.inputValue as string}
                          onChange={(event) =>
                            handleFieldChange(field.key, event.target.value)
                          }
                          disabled={saving}
                          className="w-full rounded border border-[#3e4451] bg-[#1b1b1f] px-3 py-2 text-sm text-gray-100 focus:border-blue-400 focus:outline-none"
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <footer className="px-6 py-4 border-t border-[#3e4451] flex flex-wrap gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-gray-600 text-white hover:bg-gray-500 transition"
            disabled={saving}
          >
            Close
          </button>
          <button
            onClick={handleReset}
            disabled={saving || loading || !baseUrl}
            className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-500 transition disabled:opacity-50"
          >
            Reset to Defaults
          </button>
          <button
            onClick={handleSave}
            disabled={!canSubmit}
            className="px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-500 transition disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save Overrides'}
          </button>
        </footer>
      </div>
    </div>
  );
};

export default ModelSettingsModal;
