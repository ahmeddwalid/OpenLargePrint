import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { FontSelector } from '../components/FontSelector';

describe('reading font choice', () => {
  it('shows the chosen fonts and keeps the full list folded away', () => {
    render(<FontSelector latin="atkinson" arabic="noto-sans-arabic" onLatinChange={vi.fn()} onArabicChange={vi.fn()} />);
    expect(screen.getByText('Atkinson Hyperlegible')).toBeInTheDocument();
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Change font' })).toHaveAttribute('aria-expanded', 'false');
  });

  it('lets the reader pick a Latin and an Arabic font', () => {
    const onLatin = vi.fn();
    const onArabic = vi.fn();
    render(<FontSelector latin="atkinson" arabic="noto-sans-arabic" onLatinChange={onLatin} onArabicChange={onArabic} />);
    fireEvent.click(screen.getByRole('button', { name: 'Change font' }));
    expect(screen.getAllByRole('radiogroup')).toHaveLength(2);
    fireEvent.click(screen.getByLabelText(/^Lexend/));
    fireEvent.click(screen.getByLabelText(/^Amiri/));
    expect(onLatin).toHaveBeenCalledWith('lexend');
    expect(onArabic).toHaveBeenCalledWith('amiri');
  });
});
