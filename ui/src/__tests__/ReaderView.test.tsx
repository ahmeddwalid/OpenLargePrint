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
    expect(screen.getByText(/Original page 1/i)).toBeInTheDocument();
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

  it('toggles table of contents drawer and lists headings (UI-001, OUT-002)', async () => {
    const multiHeadingDoc: DocumentIR = {
      schema_version: '1.0.0',
      source_file: 'sample.pdf',
      source_mime: 'application/pdf',
      page_count: 2,
      blocks: [
        { id: 'h-1', block_type: 'heading', heading_level: 1, text: 'Chapter One', source_page: 1 },
        { id: 'p-1', block_type: 'paragraph', text: 'Some text here', source_page: 1 },
        { id: 'h-2', block_type: 'heading', heading_level: 2, text: 'Section A', source_page: 2 },
      ],
    };

    render(
      <ReaderView
        documentIR={multiHeadingDoc}
        initialSize={20}
        currentTheme="light"
        onThemeChange={vi.fn()}
        onBack={vi.fn()}
        onExport={vi.fn()}
      />
    );

    const contentsBtn = screen.getByRole('button', { name: /table of contents/i });
    expect(contentsBtn).toBeInTheDocument();
    await userEvent.click(contentsBtn);

    expect(screen.getByRole('navigation', { name: /table of contents/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /chapter one/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /section a/i })).toBeInTheDocument();
  });

  it('supports in-reader search with match cycling (A11Y-002, A11Y-003)', async () => {
    const searchDoc: DocumentIR = {
      schema_version: '1.0.0',
      source_file: 'sample.pdf',
      source_mime: 'application/pdf',
      page_count: 1,
      blocks: [
        { id: 'p-1', block_type: 'paragraph', text: 'Apples and bananas.', source_page: 1 },
        { id: 'p-2', block_type: 'paragraph', text: 'More delicious apples.', source_page: 1 },
      ],
    };

    render(
      <ReaderView
        documentIR={searchDoc}
        initialSize={20}
        currentTheme="light"
        onThemeChange={vi.fn()}
        onBack={vi.fn()}
        onExport={vi.fn()}
      />
    );

    const searchBtn = screen.getByRole('button', { name: /^search$/i });
    await userEvent.click(searchBtn);

    const searchInput = screen.getByPlaceholderText(/search in document/i);
    expect(searchInput).toBeInTheDocument();

    await userEvent.type(searchInput, 'apples');
    expect(screen.getByText(/1 of 2/i)).toBeInTheDocument();

    const nextBtn = screen.getByRole('button', { name: /next match/i });
    await userEvent.click(nextBtn);
    expect(screen.getByText(/2 of 2/i)).toBeInTheDocument();
  });

  it('exposes local text-to-speech controls (OUT-002, A11Y-002)', async () => {
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

    const ttsBtn = screen.getByRole('button', { name: /read aloud/i });
    expect(ttsBtn).toBeInTheDocument();
  });

  it('renders source markers, emphasis, blanks, notes and picture text like the exports (IR 1.1)', () => {
    const ir: DocumentIR = {
      schema_version: '1.1.0',
      source_file: 'book.pdf',
      source_mime: 'application/pdf',
      page_count: 1,
      pages: [{ page_number: 1, printed_page: '41' }],
      blocks: [
        { id: 'm', block_type: 'page_marker', source_page: 1 },
        { id: 'l', block_type: 'list_item', text: '1 She went ______ school.', list_marker: '1', source_page: 1,
          styles: [{ start: 2, end: 5, bold: true }] },
        { id: 'd', block_type: 'list_item', text: 'A: Hello there', list_marker: 'A:', role: 'dialogue', source_page: 1 },
        { id: 'a', block_type: 'aside', text: 'Remember the rule.', source_page: 1 },
        { id: 'c', block_type: 'caption', text: 'EXIT', role: 'figure_text', source_page: 1 },
        { id: 'p', block_type: 'paragraph', text: 'Hard to read.', source_page: 1,
          warnings: ['Some words here were hard to read. Compare with the original page.'] },
      ],
    };
    const { container } = render(
      <ReaderView documentIR={ir} initialSize={20} currentTheme="light"
        onThemeChange={vi.fn()} onBack={vi.fn()} onExport={vi.fn()} />
    );
    expect(screen.getByText('Original page 1 (printed 41)')).toBeInTheDocument();
    // The source's own number is the marker: no extra bullet is added.
    expect(container.querySelector('#l .reader-item-marker')?.textContent).toBe('1');
    expect(container.textContent).not.toContain('•');
    expect(container.querySelector('#l strong')?.textContent).toBe('She');
    expect(screen.getAllByRole('img', { name: 'blank' })).toHaveLength(1);
    expect(container.querySelector('#d')).toHaveClass('dialogue');
    expect(container.querySelector('#a')).toHaveClass('reader-aside');
    expect(screen.getByText('In the picture:')).toBeInTheDocument();
    expect(screen.getByText(/compare with the original page/i)).toBeInTheDocument();
  });
});
