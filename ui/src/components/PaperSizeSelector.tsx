import React from 'react';
import { PaperSize } from '../types';

interface PaperSizeSelectorProps {
  value: PaperSize;
  onChange: (size: PaperSize) => void;
}

const PAPERS: { size: PaperSize; label: string; description: string }[] = [
  { size: 'A4', label: 'A4 Paper (Default)', description: 'Standard size for ordinary office & home printers' },
  { size: 'A3', label: 'A3 Paper', description: 'Large format sheet, recommended for wide tables' },
];

export const PaperSizeSelector: React.FC<PaperSizeSelectorProps> = ({ value, onChange }) => {
  return (
    <fieldset className="decision-step" style={{ border: 'none', padding: 0 }}>
      <legend className="step-label">Paper format</legend>
      <div className="radio-group-grid" role="radiogroup" aria-label="Paper size options">
        {PAPERS.map((item) => {
          const isSelected = value === item.size;
          return (
            <label
              key={item.size}
              className={`radio-card ${isSelected ? 'selected' : ''}`}
              htmlFor={`paper-${item.size}`}
            >
              <input
                type="radio"
                id={`paper-${item.size}`}
                name="paper-size"
                value={item.size}
                checked={isSelected}
                onChange={() => onChange(item.size)}
              />
              <span className="radio-title">{item.label}</span>
              <span className="radio-sub">{item.description}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
};
