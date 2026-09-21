import React, { useEffect, useState } from 'react';
import { AppTheme, DocumentBlock, DocumentIR } from '../types';
import { sidecar } from '../api/sidecarClient';
import { useI18n } from '../i18n/i18n';

interface ReaderViewProps {
  documentIR: DocumentIR;
  initialSize: number;
  currentTheme: AppTheme;
  exportedFilePath?: string | null;
  onThemeChange: (theme: AppTheme) => void;
  onBack: () => void;
  onExport: (selection: { pages?: number[]; fontPt: number; lineSpacing: number }) => void;
}

const HeadingBlock: React.FC<{
  level?: number;
  fontSize: number;
  text?: string;
}> = ({ level = 1, fontSize, text }) => {
  const boundedLevel = Math.min(6, Math.max(1, level));
  const style: React.CSSProperties = {
    marginTop: '1.2em',
    marginBottom: '0.6em',
    fontSize: `${fontSize * (boundedLevel === 1 ? 1.4 : 1.2)}px`,
    fontWeight: 700,
  };

  switch (boundedLevel) {
    case 1:
      return <h1 style={style}>{text}</h1>;
    case 2:
      return <h2 style={style}>{text}</h2>;
    case 3:
      return <h3 style={style}>{text}</h3>;
    case 4:
      return <h4 style={style}>{text}</h4>;
    case 5:
      return <h5 style={style}>{text}</h5>;
    default:
      return <h6 style={style}>{text}</h6>;
  }
};

export type ReaderFont = 'system' | 'hyperlegible' | 'lexend' | 'mono';

const FONT_FAMILIES: Record<ReaderFont, string> = {
  system: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  hyperlegible: '"Atkinson Hyperlegible", "Segoe UI", sans-serif',
  lexend: '"Lexend", "Segoe UI", sans-serif',
  mono: 'Consolas, "Courier New", monospace',
};

export const ReaderView: React.FC<ReaderViewProps> = ({
  documentIR,
  initialSize,
  currentTheme,
  exportedFilePath,
  onThemeChange,
  onBack,
  onExport,
}) => {
  const { t } = useI18n();
  const [fontSize, setFontSize] = useState<number>(initialSize);
  const [lineHeight, setLineHeight] = useState<number>(1.6);
  const [readingWidth, setReadingWidth] = useState<number>(85);
  const [readerFont, setReaderFont] = useState<ReaderFont>('system');
  const [showRuler, setShowRuler] = useState<boolean>(false);
  const [rulerTop, setRulerTop] = useState<number>(180);
  const [selectedPageFilter, setSelectedPageFilter] = useState<number | 'all'>('all');

  // Keep the print stylesheet's base size in sync with the chosen size (OUT-009).
  useEffect(() => {
    document.documentElement.style.setProperty('--print-font-size', `${fontSize}pt`);
  }, [fontSize]);

  const handleZoomIn = () => {
    setFontSize((prev) => Math.min(36, prev + 2));
  };

  const handleZoomOut = () => {
    setFontSize((prev) => Math.max(14, prev - 2));
  };

  const filteredBlocks = selectedPageFilter === 'all'
    ? documentIR.blocks
    : documentIR.blocks.filter((b) => b.source_page === selectedPageFilter);

  const pages = Array.from(
    new Set(documentIR.blocks.map((b) => b.source_page).filter((p): p is number => p !== undefined))
  ).sort((a, b) => a - b);

  return (
    <div
      className="reader-container"
      aria-label="Large-Print Reader"
      onMouseMove={(e) => {
        if (showRuler) {
          setRulerTop(e.clientY);
        }
      }}
    >
      {/* Export Success File Access Banner */}
      {exportedFilePath && (
        <aside
          aria-label="Exported file destination"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap',
            padding: '12px 18px',
            backgroundColor: 'var(--success-bg)',
            border: '1px solid var(--success-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--success-text)',
            fontSize: '15px',
            marginBottom: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
            <span style={{ fontWeight: 700, whiteSpace: 'nowrap' }}>{t('file.saved_file')}</span>
            <span
              style={{
                fontFamily: 'Consolas, monospace',
                fontSize: '13px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                direction: 'ltr',
              }}
              title={exportedFilePath}
            >
              {exportedFilePath}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
            <button
              type="button"
              className="primary-btn"
              onClick={() => sidecar.openPathInSystem(exportedFilePath)}
              style={{ minHeight: '38px', padding: '6px 14px', fontSize: '14px' }}
            >
              {t('file.open_file')}
            </button>
            <button
              type="button"
              className="secondary-btn"
              onClick={() => sidecar.revealInFolder(exportedFilePath)}
              style={{ minHeight: '38px', padding: '6px 14px', fontSize: '14px' }}
            >
              {t('file.show_in_folder')}
            </button>
          </div>
        </aside>
      )}

      {/* Floating Reading Ruler Line Focus Guide A11Y-001, A11Y-003 */}
      {showRuler && (
        <div
          className="reading-ruler"
          style={{ top: `${rulerTop}px` }}
          aria-hidden="true"
        />
      )}

      {/* Reader Controls Toolbar OUT-002 */}
      <nav
        className="reader-toolbar"
        aria-label="Reader adjustment controls"
        style={{ flexWrap: 'wrap', gap: '12px' }}
      >
        <button
          type="button"
          className="secondary-btn"
          onClick={onBack}
          aria-label="Back to document options"
        >
          ← Back
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 600, fontSize: '15px' }}>Text Size:</span>
          <button
            type="button"
            className="secondary-btn"
            onClick={handleZoomOut}
            aria-label="Decrease text size"
          >
            A-
          </button>
          <span style={{ minWidth: '48px', textAlign: 'center', fontWeight: 700 }} aria-live="polite">
            {fontSize} pt
          </span>
          <button
            type="button"
            className="secondary-btn"
            onClick={handleZoomIn}
            aria-label="Increase text size"
          >
            A+
          </button>
        </div>

        {/* Font Family Selection */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="reader-font-select" style={{ fontWeight: 600, fontSize: '15px' }}>
            Font:
          </label>
          <select
            id="reader-font-select"
            value={readerFont}
            onChange={(e) => setReaderFont(e.target.value as ReaderFont)}
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="system">System Clean</option>
            <option value="hyperlegible">Atkinson Hyperlegible</option>
            <option value="lexend">Lexend</option>
            <option value="mono">Monospace</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="line-spacing-select" style={{ fontWeight: 600, fontSize: '15px' }}>
            Spacing:
          </label>
          <select
            id="line-spacing-select"
            value={lineHeight}
            onChange={(e) => setLineHeight(parseFloat(e.target.value))}
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="1.4">1.4x (Standard)</option>
            <option value="1.6">1.6x (Comfortable)</option>
            <option value="1.8">1.8x (Spacious)</option>
            <option value="2.0">2.0x (Double)</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="reading-width-select" style={{ fontWeight: 600, fontSize: '15px' }}>
            Width:
          </label>
          <select
            id="reading-width-select"
            aria-label="Reading width"
            value={readingWidth}
            onChange={(e) => setReadingWidth(parseInt(e.target.value, 10))}
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="55">Narrow (55 characters)</option>
            <option value="70">Comfortable (70 characters)</option>
            <option value="85">Wide (85 characters)</option>
            <option value="110">Full width (110 characters)</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="theme-select" style={{ fontWeight: 600, fontSize: '15px' }}>
            Theme:
          </label>
          <select
            id="theme-select"
            value={currentTheme}
            onChange={(e) => onThemeChange(e.target.value as AppTheme)}
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="light">Light (Default)</option>
            <option value="auto">Auto (follow system)</option>
            <option value="sepia">Sepia</option>
            <option value="dark">Dark</option>
          </select>
        </div>

        {/* Reading ruler guide button */}
        <button
          type="button"
          className="secondary-btn"
          onClick={() => setShowRuler(!showRuler)}
          aria-pressed={showRuler}
          aria-label="Toggle horizontal line guide"
          style={{
            backgroundColor: showRuler ? 'var(--accent-primary)' : undefined,
            color: showRuler ? 'var(--accent-text)' : undefined,
          }}
        >
          Line guide {showRuler ? 'On' : 'Off'}
        </button>

        {/* Direct native print button */}
        <button
          type="button"
          className="secondary-btn"
          onClick={() => window.print()}
          aria-label="Directly print this large-print document using system printer"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <polyline points="6 9 6 2 18 2 18 9" />
            <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
            <rect x="6" y="14" width="12" height="8" />
          </svg>
          Print...
        </button>

        {pages.length > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label htmlFor="page-jump-select" style={{ fontWeight: 600, fontSize: '15px' }}>
              Page:
            </label>
            <select
              id="page-jump-select"
              value={selectedPageFilter}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedPageFilter(val === 'all' ? 'all' : parseInt(val, 10));
              }}
              style={{
                padding: '6px 10px',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <option value="all">All Pages ({pages.length})</option>
              {pages.map((p) => (
                <option key={p} value={p}>
                  Page {p}
                </option>
              ))}
            </select>
          </div>
        )}

        <button
          type="button"
          className="primary-btn"
          onClick={() => {
            onExport({
              pages: selectedPageFilter === 'all' ? undefined : [selectedPageFilter],
              fontPt: fontSize,
              lineSpacing: lineHeight,
            });
          }}
          aria-label="Export this view"
        >
          {selectedPageFilter === 'all' ? t('reader.save_document') : t('reader.save_page', { page: String(selectedPageFilter) })}
        </button>
      </nav>

      {/* Reader Body Content */}
      <main
        className="reader-body"
        style={{
          fontSize: `${fontSize}pt`,
          lineHeight: lineHeight,
          maxWidth: `${readingWidth}ch`,
          fontFamily: FONT_FAMILIES[readerFont],
        }}
        tabIndex={0}
        aria-label="Document Content"
      >
        {filteredBlocks.map((block: DocumentBlock) => {
          if (block.block_type === 'heading') {
            return (
              <HeadingBlock
                key={block.id}
                level={block.heading_level}
                fontSize={fontSize}
                text={block.text}
              />
            );
          }

          if (block.block_type === 'table' && block.table_data) {
            return (
              <div
                key={block.id}
                style={{
                  overflowX: 'auto',
                  margin: '1.5em 0',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  {block.caption && (
                    <caption
                      style={{
                        textAlign: 'left',
                        padding: '8px',
                        fontWeight: 700,
                        backgroundColor: 'var(--bg-surface-raised)',
                      }}
                    >
                      {block.caption}
                    </caption>
                  )}
                  <tbody>
                    {block.table_data.map((row, rIdx) => (
                      <tr
                        key={rIdx}
                        style={{
                          backgroundColor: rIdx === 0 ? 'var(--bg-surface-raised)' : 'transparent',
                          borderBottom: '1px solid var(--border-color)',
                        }}
                      >
                        {row.map((cell, cIdx) => (
                          rIdx === 0 ? (
                            <th
                              key={cIdx}
                              style={{
                                padding: '12px 16px',
                                textAlign: 'left',
                                borderRight: '1px solid var(--border-color)',
                                fontWeight: 700,
                              }}
                            >
                              {cell}
                            </th>
                          ) : (
                            <td
                              key={cIdx}
                              style={{
                                padding: '12px 16px',
                                textAlign: 'left',
                                borderRight: '1px solid var(--border-color)',
                                fontWeight: 400,
                              }}
                            >
                              {cell}
                            </td>
                          )
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }

          // Source page transition marker (OUT-005)
          if (block.block_type === 'page_marker') {
            return (
              <div
                key={block.id}
                role="separator"
                aria-label={block.text || `Original page ${block.source_page}`}
                style={{
                  margin: '2em 0 1.2em 0',
                  padding: '8px 16px',
                  border: '1px dashed var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  textAlign: 'center',
                  fontSize: '0.8em',
                  fontWeight: 700,
                  color: 'var(--text-muted)',
                }}
              >
                {block.text || `— Original Page ${block.source_page} —`}
              </div>
            );
          }

          // Figures / images (IMG-001)
          if (block.block_type === 'figure') {
            const src = block.image_asset?.data_url;
            if (!src) {
              return null;
            }
            return (
              <figure key={block.id} style={{ margin: '1.5em 0', textAlign: 'center' }}>
                <img
                  src={src}
                  alt={block.image_asset?.alt_text || `Figure from page ${block.source_page}`}
                  style={{
                    maxWidth: '100%',
                    height: 'auto',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                  }}
                />
                {block.caption && (
                  <figcaption
                    style={{
                      fontSize: '0.85em',
                      fontStyle: 'italic',
                      color: 'var(--text-muted)',
                      marginTop: '6px',
                    }}
                  >
                    {block.caption}
                  </figcaption>
                )}
              </figure>
            );
          }

          // Footnotes (FN-001)
          if (block.block_type === 'footnote') {
            return (
              <aside
                key={block.id}
                role="doc-footnote"
                style={{
                  fontSize: '0.85em',
                  fontStyle: 'italic',
                  color: 'var(--text-muted)',
                  borderTop: '1px solid var(--border-color)',
                  paddingTop: '8px',
                  marginTop: '1.5em',
                  marginBottom: '1em',
                }}
              >
                {block.text}
              </aside>
            );
          }

          // Captions
          if (block.block_type === 'caption') {
            return (
              <div
                key={block.id}
                style={{
                  fontWeight: 700,
                  fontSize: '0.9em',
                  textAlign: 'center',
                  margin: '12px 0 6px 0',
                }}
              >
                {block.text}
              </div>
            );
          }

          // Quotes
          if (block.block_type === 'quote') {
            return (
              <blockquote
                key={block.id}
                style={{
                  borderLeft: '4px solid var(--border-color)',
                  paddingLeft: '16px',
                  margin: '1em 0',
                  fontStyle: 'italic',
                  color: 'var(--text-muted)',
                }}
              >
                {block.text}
              </blockquote>
            );
          }

          // List items — rendered individually with a visible bullet
          if (block.block_type === 'list_item') {
            return (
              <div
                key={block.id}
                style={{
                  display: 'flex',
                  gap: '0.6em',
                  marginBottom: '0.4em',
                  paddingLeft: '0.5em',
                }}
              >
                <span aria-hidden="true">•</span>
                <span>{block.text}</span>
              </div>
            );
          }

          return (
            <p key={block.id} style={{ marginBottom: '1em' }}>
              {block.text}
            </p>
          );
        })}
      </main>
    </div>
  );
};
