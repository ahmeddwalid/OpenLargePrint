import React, { useEffect, useRef, useState } from 'react';
import { AppTheme } from '../types';
import { Locale, useI18n } from '../i18n/i18n';
import { CURRENT_VERSION, checkForUpdates, isAutoUpdateEnabled, setAutoUpdateEnabled } from '../api/update-checker';

interface SettingsMenuProps {
  theme: AppTheme;
  onThemeChange: (theme: AppTheme) => void;
}

const THEMES: AppTheme[] = ['sepia', 'light', 'dark', 'auto'];

/** Appearance, language and updates: set once, so they live behind one button in the header. */
export const SettingsMenu: React.FC<SettingsMenuProps> = ({ theme, onThemeChange }) => {
  const { t, locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);
  const [autoUpdate, setAutoUpdate] = useState<boolean>(() => isAutoUpdateEnabled());
  const [status, setStatus] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    const onClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!panelRef.current?.contains(target) && !buttonRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  const checkNow = async () => {
    setChecking(true);
    setStatus(t('settings.update_checking'));
    try {
      const result = await checkForUpdates(true);
      setStatus(result.available && result.latestVersion
        ? t('settings.update_available', { version: result.latestVersion })
        : t('settings.update_current', { version: CURRENT_VERSION }));
    } catch {
      setStatus(t('settings.update_failed'));
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="settings-menu">
      <button
        ref={buttonRef}
        type="button"
        className="secondary-btn"
        aria-expanded={open}
        aria-controls="settings-panel"
        onClick={() => setOpen(!open)}
      >
        {t('settings.button')}
      </button>
      {open && (
        <div id="settings-panel" ref={panelRef} className="settings-panel" role="group" aria-label={t('settings.button')}>
          <div className="field">
            <label htmlFor="global-theme-toggle" className="field-label">{t('theme.label')}</label>
            <select
              id="global-theme-toggle"
              className="field-input"
              value={theme}
              onChange={(e) => onThemeChange(e.target.value as AppTheme)}
            >
              {THEMES.map((value) => (
                <option key={value} value={value}>{t(`theme.${value}`)}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="global-lang-select" className="field-label">{t('lang.label')}</label>
            <select
              id="global-lang-select"
              className="field-input"
              value={locale}
              onChange={(e) => setLocale(e.target.value as Locale)}
            >
              <option value="en">{t('lang.en')}</option>
              <option value="ar">{t('lang.ar')}</option>
            </select>
          </div>
          <div className="field">
            <span className="field-label">{t('settings.updates')}</span>
            <label className="check-row" htmlFor="auto-update">
              <input
                id="auto-update"
                type="checkbox"
                checked={autoUpdate}
                onChange={(e) => {
                  setAutoUpdate(e.target.checked);
                  setAutoUpdateEnabled(e.target.checked);
                }}
              />
              <span className="check-title">{t('settings.update_auto')}</span>
            </label>
            <div className="settings-update-row">
              <button type="button" className="secondary-btn" onClick={checkNow} disabled={checking}>
                {t('settings.update_check')}
              </button>
              {status && <span className="field-help" aria-live="polite">{status}</span>}
            </div>
            <span className="field-help">{t('settings.version', { version: CURRENT_VERSION })}</span>
          </div>
        </div>
      )}
    </div>
  );
};
