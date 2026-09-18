import { useEffect } from 'react';

export interface ShortcutHandlers {
  onConvert?: () => void;
  onCancel?: () => void;
  onBack?: () => void;
}

/**
 * Keyboard shortcuts for the primary conversion flow (A11Y-003).
 * Ctrl+Enter starts conversion, Escape cancels or goes back.
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers): void {
  const { onConvert, onCancel, onBack } = handlers;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
        if (e.key === 'Escape' && onCancel) {
          onCancel();
        }
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && onConvert) {
        e.preventDefault();
        onConvert();
      } else if (e.key === 'Escape') {
        if (onCancel) {
          onCancel();
        } else if (onBack) {
          onBack();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onConvert, onCancel, onBack]);
}
