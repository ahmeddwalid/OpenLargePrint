import React, { useState } from 'react';
import { DocumentIR, OutputFormat, TextSize } from '../types';
import { sidecar } from '../api/sidecarClient';
import { useI18n } from '../i18n/i18n';

export interface RecentDocumentItem {
  id: string;
  timestamp: number;
  dateFormatted: string;
  sourceName: string;
  sourcePath?: string;
  outputPath: string;
  format: OutputFormat;
  textSize: TextSize;
  documentIR?: DocumentIR;
}

interface RecentDocumentsProps {
  items: RecentDocumentItem[];
  onOpenInReader?: (ir: DocumentIR, outputPath: string) => void;
  onClearHistory: () => void;
}

export const RecentDocuments: React.FC<RecentDocumentsProps> = ({
  items,
  onOpenInReader,
  onClearHistory,
}) => {
  const { t } = useI18n();
  const [isOpen, setIsOpen] = useState(false);

  if (!items || items.length === 0) {
    return null;
  }

  const handleOpenFile = async (outputPath: string) => {
    await sidecar.openPathInSystem(outputPath);
  };

  return (
    <div
      className="recent-documents-shelf"
      style={{
        marginTop: '32px',
        paddingTop: '20px',
        borderTop: '1px solid var(--border-color)',
      }}
    >
      <button
        type="button"
        className="disclosure-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-controls="recent-documents-content"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontWeight: 600,
          fontSize: '1rem',
          color: 'var(--text-primary)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '8px 0',
          minHeight: '48px',
        }}
      >
        <span>{isOpen ? '▾' : '▸'}</span>
        <span>Recent conversions ({items.length})</span>
      </button>

      {isOpen && (
        <div id="recent-documents-content" style={{ marginTop: '12px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {items.map((item) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  backgroundColor: 'var(--bg-surface-raised)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  gap: '12px',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ flex: 1, minWidth: '220px' }}>
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: '1rem',
                      color: 'var(--text-primary)',
                      wordBreak: 'break-all',
                    }}
                  >
                    {item.sourceName}
                  </div>
                  <div
                    style={{
                      fontSize: '0.8125rem',
                      color: 'var(--text-secondary)',
                      marginTop: '4px',
                      fontFamily: 'Consolas, monospace',
                      wordBreak: 'break-all',
                    }}
                  >
                    {item.outputPath}
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {item.dateFormatted} • {item.textSize} • {item.format.toUpperCase()}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {item.documentIR && onOpenInReader && (
                    <button
                      type="button"
                      className="secondary-btn"
                      onClick={() => onOpenInReader(item.documentIR!, item.outputPath)}
                      style={{ minHeight: '48px', padding: '8px 14px' }}
                      aria-label={`Open ${item.sourceName} in Large Print Reader`}
                    >
                      Reader
                    </button>
                  )}
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={() => handleOpenFile(item.outputPath)}
                    style={{ minHeight: '48px', padding: '8px 14px' }}
                    aria-label={`Open output file ${item.outputPath}`}
                  >
                    {t('file.open_file')}
                  </button>
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={() => sidecar.revealInFolder(item.outputPath)}
                    style={{ minHeight: '48px', padding: '8px 14px' }}
                    aria-label={`Show output file in folder: ${item.outputPath}`}
                  >
                    {t('file.show_in_folder')}
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="text-btn"
              onClick={onClearHistory}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-secondary)',
                fontSize: '0.875rem',
                cursor: 'pointer',
                textDecoration: 'underline',
                minHeight: '48px',
                padding: '8px',
              }}
            >
              Clear recent history
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
