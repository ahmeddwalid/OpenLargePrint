import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { AdvancedOptions } from '../components/AdvancedOptions';
import { I18nProvider } from '../i18n/i18n';

function renderOptions(overrides: Partial<React.ComponentProps<typeof AdvancedOptions>> = {}) {
  const props = {
    routingMode: 'auto' as const,
    onRoutingModeChange: vi.fn(),
    pageRange: '',
    onPageRangeChange: vi.fn(),
    monochrome: false,
    onMonochromeChange: vi.fn(),
    preservePageArtwork: false,
    onPreservePageArtworkChange: vi.fn(),
    pageBreakOnSourcePage: false,
    onPageBreakOnSourcePageChange: vi.fn(),
    ...overrides,
  };
  render(
    <I18nProvider>
      <AdvancedOptions {...props} />
    </I18nProvider>
  );
  return props;
}

async function openAdvancedOptions() {
  await userEvent.click(screen.getByRole('button', { name: /more options|hide advanced/i }));
}

describe('AdvancedOptions page artwork toggle', () => {
  it('starts off and reports the change (UI-001, IMG-001)', async () => {
    const props = renderOptions();
    await openAdvancedOptions();

    const toggle = screen.getByRole('checkbox', { name: /keep page artwork/i });
    expect(toggle).not.toBeChecked();

    await userEvent.click(toggle);
    expect(props.onPreservePageArtworkChange).toHaveBeenCalledWith(true);
  });

  it('reflects the current setting when it is already on', async () => {
    renderOptions({ preservePageArtwork: true });
    await openAdvancedOptions();

    expect(screen.getByRole('checkbox', { name: /keep page artwork/i })).toBeChecked();
  });

  it('offers a full-size touch target (A11Y-001)', async () => {
    renderOptions();
    await openAdvancedOptions();

    const label = screen.getByRole('checkbox', { name: /keep page artwork/i }).closest('label');
    expect(label).not.toBeNull();
    expect(label as HTMLElement).toHaveStyle({ minHeight: '48px' });
  });
});

describe('AdvancedOptions page break on source page toggle', () => {
  it('starts off and reports the change when toggled (UI-001)', async () => {
    const props = renderOptions();
    await openAdvancedOptions();

    const toggle = screen.getByRole('checkbox', { name: /start each original page on a new sheet/i });
    expect(toggle).not.toBeChecked();

    await userEvent.click(toggle);
    expect(props.onPageBreakOnSourcePageChange).toHaveBeenCalledWith(true);
  });

  it('reflects the current setting when active', async () => {
    renderOptions({ pageBreakOnSourcePage: true });
    await openAdvancedOptions();

    expect(screen.getByRole('checkbox', { name: /start each original page on a new sheet/i })).toBeChecked();
  });

  it('offers a full-size touch target of at least 44-48px (A11Y-001)', async () => {
    renderOptions();
    await openAdvancedOptions();

    const label = screen.getByRole('checkbox', { name: /start each original page on a new sheet/i }).closest('label');
    expect(label).not.toBeNull();
    expect(label as HTMLElement).toHaveStyle({ minHeight: '48px' });
  });
});
