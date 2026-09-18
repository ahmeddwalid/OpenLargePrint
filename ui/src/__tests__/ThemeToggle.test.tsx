import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { I18nProvider } from '../i18n/i18n';

function Probe() {
  return (
    <I18nProvider>
      <button type="button">Probe</button>
    </I18nProvider>
  );
}

describe('Theme and i18n', () => {
  it('renders children inside the i18n provider (A11Y-005)', async () => {
    render(<Probe />);
    const btn = screen.getByRole('button', { name: /probe/i });
    expect(btn).toBeInTheDocument();
    await userEvent.click(btn);
  });

  it('sets html lang/dir attributes for RTL support', () => {
    render(<Probe />);
    expect(document.documentElement.getAttribute('lang')).toMatch(/en|ar/);
    expect(document.documentElement.getAttribute('dir')).toMatch(/ltr|rtl/);
  });
});
