import React from 'react';
import { OutputFormat } from '../types';
import { useI18n } from '../i18n/i18n';

type MainFormat = Exclude<OutputFormat, 'searchable_pdf'>;

interface DocumentTypeSelectorProps {
  value: OutputFormat;
  onChange: (format: MainFormat) => void;
}

const FORMATS: MainFormat[] = ['pdf', 'docx', 'html'];

/** The three large-print outputs. The searchable copy of the original lives under "More options". */
export const DocumentTypeSelector: React.FC<DocumentTypeSelectorProps> = ({ value, onChange }) => {
  const { t } = useI18n();
  return (
    <fieldset className="choice-group">
      <legend className="choice-legend">{t('format.step_label')}</legend>
      <div className="choice-row" role="radiogroup" aria-label={t('format.step_label')}>
        {FORMATS.map((id) => {
          const selected = value === id;
          return (
            <label key={id} className={`radio-card ${selected ? 'selected' : ''}`} htmlFor={`format-${id}`}>
              <input
                type="radio"
                id={`format-${id}`}
                name="export-format"
                value={id}
                checked={selected}
                onChange={() => onChange(id)}
              />
              <span className="radio-title">{t(`format.${id}`)}</span>
              <span className="radio-sub">{t(`format.${id}_detail`)}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
};
