import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FilePicker } from '../components/FilePicker';

describe('FilePicker', () => {
  it('offers a Browse button that is not drag-and-drop only (A11Y-004)', () => {
    render(<FilePicker selectedFile={null} onFileSelect={vi.fn()} onClear={vi.fn()} />);
    const browse = screen.getAllByRole('button', { name: /browse files/i });
    expect(browse.length).toBeGreaterThanOrEqual(1);
    expect(browse[0]).toBeInTheDocument();
  });

  it('exposes a keyboard-operable dropzone with an accessible label', () => {
    render(<FilePicker selectedFile={null} onFileSelect={vi.fn()} onClear={vi.fn()} />);
    const zone = screen.getByRole('button', { name: /drag and drop/i });
    expect(zone).toHaveAttribute('tabindex', '0');
  });
});
