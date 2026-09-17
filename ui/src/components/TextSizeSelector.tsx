import React from 'react';
import { TextSize } from '../types';

interface TextSizeSelectorProps {
  value: TextSize;
  onChange: (size: TextSize) => void;
}

const SIZES: { size: TextSize; label: string; description: string }[] = [
  { size: 18, label: '18 pt', description: 'Standard large print' },
  { size: 20, label: '20 pt (Default)', description: 'Recommended for most readers' },
  { size: 24, label: '24 pt', description: 'Enhanced visibility' },
  { size: 28, label: '28 pt', description: 'Maximum enlargement' },
];

export const TextSizeSelector: React.FC<TextSizeSelectorProps> = ({ value, onChange }) => {
  return (
    <fieldset className="decision-step" style={{ border: 'none', padding: 0 }}>
      <legend className="step-label">2. Choose text size</legend>
      <div className="radio-group-grid" role="radiogroup" aria-label="Text size options">
        {SIZES.map((item) => {
          const isSelected = value === item.size;
          return (
            <label
              key={item.size}
              className={`radio-card ${isSelected ? 'selected' : ''}`}
              htmlFor={`size-${item.size}`}
            >
              <input
                type="radio"
                id={`size-${item.size}`}
                name="text-size"
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
