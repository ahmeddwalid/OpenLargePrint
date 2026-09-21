import React from 'react';
import { TextSize } from '../types';

interface TextSizeSelectorProps {
  value: TextSize;
  onChange: (size: TextSize) => void;
  customBodyPt?: number | null;
  onCustomBodyPtChange?: (size: number | null) => void;
}

const SIZES: { size: TextSize; label: string; description: string }[] = [
  { size: 18, label: '18 pt', description: 'Standard large print' },
  { size: 20, label: '20 pt', description: 'Default size' },
  { size: 24, label: '24 pt', description: 'Enhanced visibility' },
  { size: 28, label: '28 pt', description: 'Larger text' },
];

const MIN_CUSTOM_PT = 14;
const MAX_CUSTOM_PT = 48;

export const TextSizeSelector: React.FC<TextSizeSelectorProps> = ({
  value,
  onChange,
  customBodyPt,
  onCustomBodyPtChange,
}) => {
  const isCustom = customBodyPt != null;

  return (
    <fieldset className="decision-step" style={{ border: 'none', padding: 0 }}>
      <legend className="step-label">2. Choose text size</legend>
      <div className="text-size-options" role="radiogroup" aria-label="Text size options">
        {SIZES.map((item) => {
          const isSelected = !isCustom && value === item.size;
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
                onChange={() => {
                  onCustomBodyPtChange?.(null);
                  onChange(item.size);
                }}
              />
              <span className="radio-title" style={{ fontSize: `${item.size / 16}rem` }}>{item.label}</span>
              <span className="radio-sub">{item.description}</span>
            </label>
          );
        })}

        {onCustomBodyPtChange && (
          <div className="text-size-custom">
            <label htmlFor="size-custom">
            <input
              type="radio"
              id="size-custom"
              name="text-size"
              value="custom"
              checked={isCustom}
              onChange={() => onCustomBodyPtChange(isCustom ? customBodyPt ?? 22 : 22)}
            />
            <span className="radio-title">Custom size</span>
            </label>
            <span className="radio-sub" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
              <label htmlFor="custom-body-pt" style={{ fontWeight: 600 }}>
                Body size:
              </label>
              <input
                id="custom-body-pt"
                type="number"
                min={MIN_CUSTOM_PT}
                max={MAX_CUSTOM_PT}
                step={1}
                value={isCustom ? customBodyPt ?? 22 : ''}
                onChange={(e) => {
                  const parsed = parseFloat(e.target.value);
                  if (Number.isFinite(parsed)) {
                    const clamped = Math.min(MAX_CUSTOM_PT, Math.max(MIN_CUSTOM_PT, parsed));
                    onCustomBodyPtChange(clamped);
                  }
                }}
                style={{ width: '72px', padding: '4px 6px' }}
                aria-label="Custom body text size in points"
              />
              <span>pt</span>
            </span>
          </div>
        )}
      </div>
    </fieldset>
  );
};
