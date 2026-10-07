import React from 'react';
import { PaperSize } from '../types';
import { useI18n } from '../i18n/i18n';

interface PaperSizeSelectorProps {
  value: PaperSize;
  onChange: (size: PaperSize) => void;
}

const SIZES: PaperSize[] = ['A4', 'A3'];

/** A4 is the default; A3 is a first-class choice next to it, never hidden (OUT-007, UI-006). */
export const PaperSizeSelector: React.FC<PaperSizeSelectorProps> = ({ value, onChange }) => {
  const { t } = useI18n();
  return (
    <fieldset className="choice-group">
      <legend className="choice-legend">{t('paper.step_label')}</legend>
      <div className="choice-row" role="radiogroup" aria-label={t('paper.step_label')}>
        {SIZES.map((size) => {
          const selected = value === size;
          const key = size.toLowerCase();
          return (
            <label key={size} className={`radio-card ${selected ? 'selected' : ''}`} htmlFor={`paper-${size}`}>
              <input
                type="radio"
                id={`paper-${size}`}
                name="paper-size"
                value={size}
                checked={selected}
                onChange={() => onChange(size)}
              />
              <span className="radio-title">{t(`paper.${key}`)}</span>
              <span className="radio-sub">{t(`paper.${key}_detail`)}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
};
