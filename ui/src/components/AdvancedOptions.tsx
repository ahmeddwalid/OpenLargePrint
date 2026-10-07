import React, { useState } from 'react';
import { useI18n } from '../i18n/i18n';

interface AdvancedOptionsProps {
  pageRange: string;
  onPageRangeChange: (range: string) => void;
  monochrome: boolean;
  onMonochromeChange: (val: boolean) => void;
  pageBreakOnSourcePage: boolean;
  onPageBreakOnSourcePageChange: (val: boolean) => void;
  searchableOriginal: boolean;
  onSearchableOriginalChange: (val: boolean) => void;
}

interface CheckRowProps {
  id: string;
  checked: boolean;
  onChange: (val: boolean) => void;
  label: string;
  description: string;
}

const CheckRow: React.FC<CheckRowProps> = ({ id, checked, onChange, label, description }) => (
  <label className="check-row" htmlFor={id}>
    <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    <span>
      <span className="check-title">{label}</span>
      <span className="check-desc">{description}</span>
    </span>
  </label>
);

/** Settings most people never need, kept out of the three-step flow (UI-001). */
export const AdvancedOptions: React.FC<AdvancedOptionsProps> = ({
  pageRange,
  onPageRangeChange,
  monochrome,
  onMonochromeChange,
  pageBreakOnSourcePage,
  onPageBreakOnSourcePageChange,
  searchableOriginal,
  onSearchableOriginalChange,
}) => {
  const { t } = useI18n();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="advanced-options-section">
      <button
        type="button"
        className="disclosure-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-controls="advanced-options-content"
      >
        <span aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
        <span>{t('advanced.toggle')}</span>
      </button>

      {isOpen && (
        <div id="advanced-options-content" className="disclosure-body">
          <div className="field">
            <label htmlFor="page-range-input" className="field-label">
              {t('advanced.page_range_label')}
            </label>
            <span id="page-range-help" className="field-help">{t('advanced.page_range_help')}</span>
            <input
              id="page-range-input"
              className="field-input"
              type="text"
              inputMode="numeric"
              placeholder={t('advanced.page_range_placeholder')}
              aria-describedby="page-range-help"
              value={pageRange}
              onChange={(e) => onPageRangeChange(e.target.value)}
            />
          </div>

          <CheckRow
            id="option-page-break"
            checked={pageBreakOnSourcePage}
            onChange={onPageBreakOnSourcePageChange}
            label={t('export.page_break_label')}
            description={t('export.page_break_desc')}
          />
          <CheckRow
            id="option-monochrome"
            checked={monochrome}
            onChange={onMonochromeChange}
            label={t('export.monochrome_label')}
            description={t('export.monochrome_desc')}
          />
          <CheckRow
            id="option-searchable"
            checked={searchableOriginal}
            onChange={onSearchableOriginalChange}
            label={t('export.searchable_label')}
            description={t('export.searchable_desc')}
          />
        </div>
      )}
    </div>
  );
};
