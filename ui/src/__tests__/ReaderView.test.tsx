import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ReaderView } from '../components/ReaderView';
import type { DocumentIR } from '../types';

const docIR: DocumentIR = {
  schema_version: '1.0.0',
  source_file: 'sample.pdf',
  source_mime: 'application/pdf',
  page_count: 1,
  blocks: [
    { id: 'b-1', block_type: 'heading', heading_level: 1, text: 'Title', source_page: 1 },
    { id: 'b-2', block_type: 'paragraph', text: 'Body text', source_page: 1 },
  ],
};

describe('ReaderView', () => {
  it('renders document blocks and supports text-size controls (OUT-002)', async () => {
    render(
      <ReaderView
        documentIR={docIR}
        initialSize={20}
        currentTheme="light"
        onThemeChange={vi.fn()}
        onBack={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByText('Title')).toBeInTheDocument();
    const inc = screen.getByRole('button', { name: /increase text size/i });
    await userEvent.click(inc);
    expect(screen.getByText(/22 pt/i)).toBeInTheDocument();
  });

  it('renders figures, footnotes, page markers, and lists from DocumentIR (IMG-001, OUT-005)', () => {
    const richIR: DocumentIR = {
      schema_version: '1.0.0',
      source_file: 'sample.pdf',
      source_mime: 'application/pdf',
      page_count: 2,
      blocks: [
        { id: 'm-1', block_type: 'page_marker', source_page: 1, text: '— Original Page 1 —' },
        {
          id: 'f-1',
          block_type: 'figure',
          source_page: 1,
          image_asset: { data_url: 'data:image/png;base64,iVBORw0KGgo=', alt_text: 'Diagram' },
        },
        { id: 'l-1', block_type: 'list_item', text: 'First item', source_page: 1 },
        { id: 'fn-1', block_type: 'footnote', text: 'A footnote.', source_page: 1 },
      ],
    };
    render(
      <ReaderView
        documentIR={richIR}
        initialSize={20}
        currentTheme="light"
        onThemeChange={vi.fn()}
        onBack={vi.fn()}
        onExport={vi.fn()}
      />
    );

    expect(screen.getByRole('img', { name: /diagram/i })).toBeInTheDocument();
    expect(screen.getByText('First item')).toBeInTheDocument();
    expect(screen.getByText('A footnote.')).toBeInTheDocument();
    expect(screen.getByText(/Original Page 1/)).toBeInTheDocument();
  });

  it('exposes a reading-width control (DESIGN.md §8)', () => {
    render(
      <ReaderView
        documentIR={docIR}
        initialSize={20}
        currentTheme="light"
        onThemeChange={vi.fn()}
        onBack={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByLabelText(/reading width/i)).toBeInTheDocument();
  });

  it('shows the exported file banner when a path is provided', () => {
    render(
      <ReaderView
        documentIR={docIR}
        initialSize={20}
        currentTheme="light"
        exportedFilePath="/tmp/out.pdf"
        onThemeChange={vi.fn()}
        onBack={vi.fn()}
        onExport={vi.fn()}
      />
    );
    expect(screen.getByLabelText(/exported file destination/i)).toBeInTheDocument();
  });
});
