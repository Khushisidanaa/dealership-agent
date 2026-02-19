import { useState, useMemo } from "react";
import {
  REQUIREMENTS_GROUPS,
  mergeWithDefaults,
  countFilled,
  type RequirementField,
  type FieldType,
} from "./requirementsFields";
import "./RequirementsModal.css";

interface RequirementsModalProps {
  requirements: Record<string, unknown>;
  onRequirementsChange: (next: Record<string, unknown>) => void;
  sessionId: string | null;
  onMarkComplete: () => void;
}

function formatDisplayValue(value: unknown, _field: RequirementField): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "number") return value === 0 && _field.type === "optionalNumber" ? "—" : String(value);
  const s = String(value).trim();
  return s || "—";
}

function parseEditValue(raw: string, type: FieldType): unknown {
  const trimmed = raw.trim();
  if (type === "string" || type === "optionalString") {
    return trimmed || (type === "optionalString" ? undefined : "");
  }
  if (type === "number") {
    const n = parseFloat(trimmed);
    return Number.isNaN(n) ? 0 : n;
  }
  if (type === "optionalNumber") {
    if (!trimmed) return undefined;
    const n = parseInt(trimmed, 10);
    return Number.isNaN(n) ? undefined : n;
  }
  if (type === "array") {
    if (!trimmed) return [];
    return trimmed.split(",").map((s) => s.trim()).filter(Boolean);
  }
  return trimmed;
}

export function RequirementsModal({
  requirements,
  onRequirementsChange,
  onMarkComplete,
}: RequirementsModalProps) {
  const [expanded, setExpanded] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editInput, setEditInput] = useState("");

  const merged = useMemo(() => mergeWithDefaults(requirements), [requirements]);
  const filledCount = countFilled(merged);

  const startEdit = (key: string, currentValue: unknown, field: RequirementField) => {
    setEditingKey(key);
    if (Array.isArray(currentValue)) {
      setEditInput(currentValue.join(", "));
    } else if (currentValue !== undefined && currentValue !== null && currentValue !== "") {
      setEditInput(String(currentValue));
    } else {
      setEditInput(field.placeholder || "");
    }
  };

  const applyEdit = () => {
    if (editingKey === null) return;
    const field = REQUIREMENTS_GROUPS.flatMap((g) => g.fields).find((f) => f.key === editingKey);
    const parsed = field ? parseEditValue(editInput, field.type) : editInput;
    onRequirementsChange({ ...merged, [editingKey]: parsed });
    setEditingKey(null);
    setEditInput("");
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setEditInput("");
  };

  return (
    <div className={`requirements-modal ${expanded ? "requirements-modal--expanded" : ""}`}>
      <button
        type="button"
        className="requirements-trigger"
        onClick={() => setExpanded(!expanded)}
        title="View / edit requirements (filled as you chat)"
      >
        <span className="requirements-trigger-icon">◇</span>
        <span className="requirements-trigger-label">
          Requirements {filledCount > 0 ? `(${filledCount})` : ""}
        </span>
      </button>

      <div className="requirements-panel">
        <div className="requirements-panel-header">
          <h2>Your requirements</h2>
          <button type="button" className="requirements-close" onClick={() => setExpanded(false)}>
            ×
          </button>
        </div>
        <div className="requirements-panel-body">
          <p className="requirements-hint">Fills in as you chat. Click any value to edit.</p>

          {REQUIREMENTS_GROUPS.map((group) => (
            <div key={group.title} className="requirements-group">
              <h3 className="requirements-group-title">{group.title}</h3>
              <ul className="requirements-list">
                {group.fields.map((field) => {
                  const value = merged[field.key];
                  const isEditing = editingKey === field.key;
                  const display = formatDisplayValue(value, field);
                  const hasOptions = field.options && field.options.length > 0;
                  return (
                    <li key={field.key} className="requirements-item">
                      <span className="requirements-key">{field.label}</span>
                      {isEditing ? (
                        hasOptions ? (
                          field.type === "array" ? (
                            <span className="requirements-edit-row requirements-edit-row--select">
                              <select
                                className="requirements-select requirements-select--multiple"
                                multiple
                                value={Array.isArray(value) ? value as string[] : []}
                                onChange={(e) => {
                                  const selected = Array.from(e.target.selectedOptions, (o) => o.value);
                                  onRequirementsChange({ ...merged, [field.key]: selected });
                                }}
                                onBlur={cancelEdit}
                              >
                                {field.options!.map((opt) => (
                                  <option key={opt} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </select>
                              <button type="button" className="requirements-edit-apply" onClick={cancelEdit}>
                                Done
                              </button>
                            </span>
                          ) : (
                            <span className="requirements-edit-row requirements-edit-row--select">
                              <select
                                className="requirements-select"
                                value={editInput || String(value ?? "")}
                                onChange={(e) => setEditInput(e.target.value)}
                                onBlur={applyEdit}
                                autoFocus
                              >
                                {field.options!.map((opt) => (
                                  <option key={opt} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </select>
                              <button type="button" className="requirements-edit-apply" onClick={applyEdit}>
                                OK
                              </button>
                              <button type="button" className="requirements-edit-cancel" onClick={cancelEdit}>
                                Cancel
                              </button>
                            </span>
                          )
                        ) : (
                          <span className="requirements-edit-row">
                            <input
                              className="requirements-edit-input"
                              value={editInput}
                              onChange={(e) => setEditInput(e.target.value)}
                              onBlur={applyEdit}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") applyEdit();
                                if (e.key === "Escape") cancelEdit();
                              }}
                              autoFocus
                              placeholder={field.placeholder}
                            />
                            <button type="button" className="requirements-edit-apply" onClick={applyEdit}>
                              OK
                            </button>
                            <button type="button" className="requirements-edit-cancel" onClick={cancelEdit}>
                              Cancel
                            </button>
                          </span>
                        )
                      ) : (
                        <span
                          className="requirements-value"
                          onClick={() => startEdit(field.key, value, field)}
                          role="button"
                          title="Click to edit"
                        >
                          {display}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}

          <button type="button" className="requirements-mark-complete" onClick={onMarkComplete}>
            Mark requirements complete → go to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
