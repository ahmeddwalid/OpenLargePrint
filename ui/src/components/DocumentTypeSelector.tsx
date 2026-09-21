import React from 'react';
import { OutputFormat } from '../types';

interface DocumentTypeSelectorProps {
  value: OutputFormat;
  onChange: (format: OutputFormat) => void;
}

interface FormatOption {
  id: OutputFormat;
  title: string;
  badge?: string;
  description: string;
}

const FORMAT_OPTIONS: FormatOption[] = [
  {
    id: 'pdf',
    title: 'PDF Document (.pdf)',
    badge: 'Default',
    description: 'Print-ready reflowed document at selected point size',
  },
  {
    id: 'docx',
    title: 'Word Document (.docx)',
    description: 'Editable Microsoft Word format with semantic hierarchy',
  },
  {
    id: 'html',
    title: 'Interactive Reader (.html)',
    description: 'Self-contained accessible web reader with zoom controls',
  },
  {
    id: 'searchable_pdf',
    title: 'Searchable original PDF',
    description: 'Keeps the original page layout and adds a text layer for searching',
  },
];

export const DocumentTypeSelector: React.FC<DocumentTypeSelectorProps> = ({
  value,
  onChange,
}) => {
  return (
    <section className="decision-step" aria-labelledby="step-format-label">
      <h2 id="step-format-label" className="step-label">
        3. Choose export format
      </h2>
      <div
        className="radio-group-grid"
        role="radiogroup"
        aria-labelledby="step-format-label"
      >
        {FORMAT_OPTIONS.map((opt) => {
          const isSelected = value === opt.id;
          return (
            <label
              key={opt.id}
              className={`radio-card ${isSelected ? 'selected' : ''}`}
              htmlFor={`format-${opt.id}`}
            >
              <input
                type="radio"
                id={`format-${opt.id}`}
                name="export-format"
                value={opt.id}
                checked={isSelected}
                onChange={() => onChange(opt.id)}
                aria-checked={isSelected}
              />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span className="radio-title">{opt.title}</span>
                {opt.badge && (
                  <span
                    style={{
                      fontSize: '12px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      backgroundColor: isSelected ? 'var(--accent-primary)' : 'var(--border-color)',
                      color: isSelected ? 'var(--accent-text)' : 'var(--text-secondary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}
                  >
                    {opt.badge}
                  </span>
                )}
              </div>
              <span className="radio-sub">{opt.description}</span>
            </label>
          );
        })}
      </div>
    </section>
  );
};
