import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { AdvancedOptions } from '../components/AdvancedOptions';
import { I18nProvider } from '../i18n/i18n';

function renderOptions(overrides: Partial<React.ComponentProps<typeof AdvancedOptions>> = {}) {
  const props = {
    pageRange: '',
    onPageRangeChange: vi.fn(),
    monochrome: false,
    onMonochromeChange: vi.fn(),
    pageBreakOnSourcePage: false,
    onPageBreakOnSourcePageChange: vi.fn(),
    searchableOriginal: false,
    onSearchableOriginalChange: vi.fn(),
    ...overrides,
  };
  render(
    <I18nProvider>
      <AdvancedOptions {...props} />
    </I18nProvider>
  );
  return props;
}

async function open() {
  await userEvent.click(screen.getByRole('button', { name: /more options/i }));
}

describe('More options (UI-001)', () => {
  it('stays closed until asked for, so the main flow keeps three steps', () => {
    renderOptions();
    expect(screen.getByRole('button', { name: /more options/i })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('offers no recognition-mode or accuracy choices', async () => {
    renderOptions();
    await open();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByText(/accuracy|recognition mode|artwork/i)).toBeNull();
  });

  it('reports page range typing', async () => {
    const props = renderOptions();
    await open();
    await userEvent.type(screen.getByLabelText(/only some pages/i), '3');
    expect(props.onPageRangeChange).toHaveBeenCalledWith('3');
  });

  it.each([
    [/start each original page on a new sheet/i, 'onPageBreakOnSourcePageChange'],
    [/black and white pictures/i, 'onMonochromeChange'],
    [/searchable copy of the original/i, 'onSearchableOriginalChange'],
  ] as const)('toggles %s', async (name, handler) => {
    const props = renderOptions();
    await open();
    const box = screen.getByRole('checkbox', { name });
    expect(box).not.toBeChecked();
    await userEvent.click(box);
    expect(props[handler]).toHaveBeenCalledWith(true);
    expect(box.closest('label')).toHaveClass('check-row');
  });
});
