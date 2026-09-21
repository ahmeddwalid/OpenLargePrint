import React from 'react';
import { OutputFormat } from '../types';

interface DocumentTypeSelectorProps {
  value: OutputFormat;
  onChange: (format: OutputFormat) => void;
}

interface FormatOption {
  id: OutputFormat;
  title: string;
  description: string;
}

const FORMAT_OPTIONS: FormatOption[] = [
  {
    id: 'pdf',
    title: 'PDF',
    description: 'Print-ready reflowed document at selected point size',
  },
  {
    id: 'docx',
    title: 'Word document',
    description: 'Edit the enlarged document in Word',
  },
  {
    id: 'html',
    title: 'HTML reader',
    description: 'Read offline and adjust text size',
  },
  {
    id: 'searchable_pdf',
    title: 'Searchable original PDF',
    description: 'Keeps the original size. Adds searchable text; does not enlarge.',
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
        className="format-options"
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
              <span className="radio-title" style={{ marginBottom: '4px' }}>{opt.title}</span>
              <span className="radio-sub">{opt.description}</span>
            </label>
          );
        })}
      </div>
    </section>
  );
};
