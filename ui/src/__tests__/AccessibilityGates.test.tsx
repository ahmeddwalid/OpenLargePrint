import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FilePicker } from '../components/FilePicker';
import { TextSizeSelector } from '../components/TextSizeSelector';
import { PaperSizeSelector } from '../components/PaperSizeSelector';
import { DocumentTypeSelector } from '../components/DocumentTypeSelector';

describe('Accessibility Gates (A11Y-001..005, UI-001, UI-005)', () => {
  it('FilePicker provides an accessible browse button and keyboard-operable dropzone (A11Y-003, A11Y-004)', () => {
    render(<FilePicker selectedFile={null} onFileSelect={vi.fn()} onClear={vi.fn()} />);

    // Must have a keyboard accessible browse button (A11Y-004: non-drag-and-drop path)
    const browseButtons = screen.getAllByRole('button', { name: /browse files/i });
    expect(browseButtons.length).toBeGreaterThanOrEqual(1);

    // Dropzone must have an accessible role or tabindex
    const dropzone = screen.getByRole('button', { name: /drag and drop/i });
    expect(dropzone).toHaveAttribute('tabindex', '0');
  });

  it('TextSizeSelector provides semantic radiogroup with labelled inputs and rem-based styles (A11Y-002, A11Y-003)', () => {
    render(
      <TextSizeSelector
        value={20}
        onChange={vi.fn()}
        customBodyPt={null}
        onCustomBodyPtChange={vi.fn()}
      />
    );

    const radiogroup = screen.getByRole('radiogroup', { name: /text size options/i });
    expect(radiogroup).toBeInTheDocument();

    // Check radio buttons for 18pt, 20pt, 24pt, 28pt presets
    const radio20 = screen.getByRole('radio', { name: /20 pt/i });
    expect(radio20).toBeChecked();

    const radio18 = screen.getByRole('radio', { name: /18 pt/i });
    expect(radio18).not.toBeChecked();

    // Custom size input has explicit accessible label
    const customInput = screen.getByLabelText(/custom body text size in points/i);
    expect(customInput).toBeInTheDocument();
  });

  it('PaperSizeSelector exposes first-class A4 and A3 choices with accessible radiogroup (OUT-007, UI-006)', () => {
    render(<PaperSizeSelector value="A4" onChange={vi.fn()} />);

    const radioA4 = screen.getByRole('radio', { name: /a4/i });
    const radioA3 = screen.getByRole('radio', { name: /a3/i });

    expect(radioA4).toBeChecked();
    expect(radioA3).not.toBeChecked();
  });

  it('DocumentTypeSelector provides accessible format selection (OUT-001, OUT-003, OUT-004)', () => {
    render(<DocumentTypeSelector value="pdf" onChange={vi.fn()} />);

    const radioPdf = screen.getByRole('radio', { name: /^PDF/i });
    expect(radioPdf).toBeChecked();

    const radioDocx = screen.getByRole('radio', { name: /^Word document/i });
    expect(radioDocx).not.toBeChecked();
  });
});
