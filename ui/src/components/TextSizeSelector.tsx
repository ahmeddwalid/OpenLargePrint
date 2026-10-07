import React from 'react';
import { TextSize } from '../types';
import { useI18n } from '../i18n/i18n';

interface TextSizeSelectorProps {
  value: TextSize;
  onChange: (size: TextSize) => void;
  customBodyPt?: number | null;
  onCustomBodyPtChange?: (size: number | null) => void;
}

const SIZES: TextSize[] = [18, 20, 24, 28];

const MIN_CUSTOM_PT = 14;
const MAX_CUSTOM_PT = 48;

export const TextSizeSelector: React.FC<TextSizeSelectorProps> = ({
  value,
  onChange,
  customBodyPt,
  onCustomBodyPtChange,
}) => {
  const { t } = useI18n();
  const isCustom = customBodyPt != null;

  return (
    <fieldset className="decision-step" style={{ border: 'none', padding: 0 }}>
      <legend className="step-label">2. {t('textsize.step_label')}</legend>
      <div className="text-size-options" role="radiogroup" aria-label={t('textsize.group_aria')}>
        {SIZES.map((size) => {
          const isSelected = !isCustom && value === size;
          return (
            <label
              key={size}
              className={`radio-card ${isSelected ? 'selected' : ''}`}
              htmlFor={`size-${size}`}
            >
              <input
                type="radio"
                id={`size-${size}`}
                name="text-size"
                value={size}
                checked={isSelected}
                onChange={() => {
                  onCustomBodyPtChange?.(null);
                  onChange(size);
                }}
              />
              <span className="radio-title" style={{ fontSize: `${size / 16}rem` }}>{size} pt</span>
              <span className="radio-sub">{t(`textsize.${size}`)}</span>
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
            <span className="radio-title">{t('textsize.custom')}</span>
            </label>
            <span className="radio-sub text-size-custom-input">
              <label htmlFor="custom-body-pt" className="field-label">
                {t('textsize.custom_label')}
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
                className="field-input number-input"
                aria-label={t('textsize.custom_aria')}
              />
              <span>pt</span>
            </span>
          </div>
        )}
      </div>
    </fieldset>
  );
};
