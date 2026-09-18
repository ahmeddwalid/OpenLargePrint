/**
 * Lightweight i18n system for OpenLargePrint (A11Y-005, LANG-001).
 *
 * Supports English and Arabic with automatic locale detection.
 * No heavy framework dependency needed for ~130 strings.
 */

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import en from './en';
import ar from './ar';

export type Locale = 'en' | 'ar';

const LOCALE_KEY = 'openlargeprint_locale';

const stringTables: Record<Locale, Record<string, string>> = { en, ar };

/** Direction associated with each locale */
export const localeDirection: Record<Locale, 'ltr' | 'rtl'> = {
  en: 'ltr',
  ar: 'rtl',
};

/** Detect initial locale from browser or saved preference */
function detectLocale(): Locale {
  const saved = localStorage.getItem(LOCALE_KEY);
  if (saved === 'en' || saved === 'ar') {
    return saved;
  }
  const nav = navigator.language || '';
  if (nav.startsWith('ar')) {
    return 'ar';
  }
  return 'en';
}

/**
 * Translate a key, optionally interpolating {placeholder} tokens.
 *
 * Example: t('review.banner', { count: '3' }) => "3 pages may need review"
 */
function translate(locale: Locale, key: string, vars?: Record<string, string | number>): string {
  let text = stringTables[locale]?.[key] ?? stringTables.en[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}

// --- React Context ---

interface I18nContextValue {
  locale: Locale;
  direction: 'ltr' | 'rtl';
  setLocale: (locale: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue>({
  locale: 'en',
  direction: 'ltr',
  setLocale: () => {},
  t: (key) => key,
});

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [locale, setLocaleState] = useState<Locale>(detectLocale);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(LOCALE_KEY, newLocale);
  }, []);

  const direction = localeDirection[locale];

  // Synchronize document-level lang and dir attributes
  useEffect(() => {
    document.documentElement.setAttribute('lang', locale);
    document.documentElement.setAttribute('dir', direction);
  }, [locale, direction]);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars),
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, direction, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
};

/** Hook to access the current locale, direction, setter, and translation function */
export function useI18n(): I18nContextValue {
  return useContext(I18nContext);
}

/** Standalone translate for use outside React components */
export function tStandalone(key: string, vars?: Record<string, string | number>): string {
  const saved = localStorage.getItem(LOCALE_KEY);
  const locale: Locale = saved === 'ar' ? 'ar' : 'en';
  return translate(locale, key, vars);
}
