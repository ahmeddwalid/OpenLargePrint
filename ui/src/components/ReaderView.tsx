import React, { useState } from 'react';
import { AppTheme, DocumentBlock, DocumentIR } from '../types';

interface ReaderViewProps {
  documentIR: DocumentIR;
  initialSize: number;
  currentTheme: AppTheme;
  onThemeChange: (theme: AppTheme) => void;
  onBack: () => void;
  onExport: (selectedPagesOnly?: number[]) => void;
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

export const ReaderView: React.FC<ReaderViewProps> = ({
  documentIR,
  initialSize,
  currentTheme,
  onThemeChange,
  onBack,
  onExport,
}) => {
  const [fontSize, setFontSize] = useState<number>(initialSize);
  const [lineHeight, setLineHeight] = useState<number>(1.6);
  const [selectedPageFilter, setSelectedPageFilter] = useState<number | 'all'>('all');

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
    <div className="reader-container" aria-label="Large-Print Reader">
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
            <option value="light">Warm Parchment (Default)</option>
            <option value="sepia">Sepia Book</option>
            <option value="dark">High-Contrast Dark</option>
          </select>
        </div>

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
            if (selectedPageFilter === 'all') {
              onExport();
            } else {
              onExport([selectedPageFilter]);
            }
          }}
          aria-label="Export or print this view"
        >
          {selectedPageFilter === 'all' ? 'Export / Print Document' : `Export Page ${selectedPageFilter}`}
        </button>
      </nav>

      {/* Reader Body Content */}
      <main
        className="reader-body"
        style={{
          fontSize: `${fontSize}px`,
          lineHeight: lineHeight,
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
