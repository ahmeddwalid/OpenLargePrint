import React, { useState } from 'react';
import { ARABIC_FONTS, LATIN_FONTS, ReadingFont, arabicFont, latinFont } from '../fonts';
import { useI18n } from '../i18n/i18n';

interface FontSelectorProps {
  latin: string;
  arabic: string;
  onLatinChange: (id: string) => void;
  onArabicChange: (id: string) => void;
}

const LATIN_SAMPLE = 'Il1 O0 rn m — The quick brown fox';
const ARABIC_SAMPLE = 'لا يجوز إلا باتفاق الطرفين ١٢٣';

/**
 * The reading font, shown as a live sample with a "Change" button: most readers
 * keep the default, so the full choice stays out of the way until asked for.
 */
export const FontSelector: React.FC<FontSelectorProps> = ({ latin, arabic, onLatinChange, onArabicChange }) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const chosenLatin = latinFont(latin);
  const chosenArabic = arabicFont(arabic);

  const group = (
    name: string,
    legend: string,
    fonts: ReadingFont[],
    value: string,
    onChange: (id: string) => void,
    sample: string,
    dir: 'ltr' | 'rtl',
  ) => (
    <fieldset className="choice-group font-group">
      <legend className="choice-legend">{legend}</legend>
      <div className="font-options" role="radiogroup" aria-label={legend}>
        {fonts.map((font) => {
          const selected = font.id === value;
          return (
            <label key={font.id} className={`radio-card font-card ${selected ? 'selected' : ''}`}
                   htmlFor={`${name}-${font.id}`}>
              <input
                type="radio"
                id={`${name}-${font.id}`}
                name={name}
                value={font.id}
                checked={selected}
                onChange={() => onChange(font.id)}
              />
              <span className="radio-title" style={{ fontFamily: `"${font.family}"` }}>{font.family}</span>
              <span className="font-sample" dir={dir} lang={dir === 'rtl' ? 'ar' : 'en'}
                    style={{ fontFamily: `"${font.family}"` }}>{sample}</span>
              <span className="radio-sub">{t(`font.${font.id}`)}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );

  return (
    <section className="font-selector" aria-labelledby="font-heading">
      <div className="font-summary">
        <div>
          <h3 id="font-heading" className="choice-legend">{t('font.heading')}</h3>
          <p className="font-preview" style={{ fontFamily: `"${chosenLatin.family}"` }}>
            {chosenLatin.family}
          </p>
          <p className="font-preview" dir="rtl" lang="ar" style={{ fontFamily: `"${chosenArabic.family}"` }}>
            {chosenArabic.family} — {ARABIC_SAMPLE}
          </p>
        </div>
        <button
          type="button"
          className="secondary-btn"
          aria-expanded={open}
          aria-controls="font-choices"
          onClick={() => setOpen(!open)}
        >
          {open ? t('font.done') : t('font.change')}
        </button>
      </div>
      {open && (
        <div id="font-choices" className="font-choices">
          {group('latin-font', t('font.latin_legend'), LATIN_FONTS, latin, onLatinChange, LATIN_SAMPLE, 'ltr')}
          {group('arabic-font', t('font.arabic_legend'), ARABIC_FONTS, arabic, onArabicChange, ARABIC_SAMPLE, 'rtl')}
        </div>
      )}
    </section>
  );
};
