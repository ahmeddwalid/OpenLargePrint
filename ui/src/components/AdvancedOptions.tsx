import React, { useState } from 'react';
import { OutputFormat, RoutingMode } from '../types';

interface AdvancedOptionsProps {
  format: OutputFormat;
  onFormatChange: (format: OutputFormat) => void;
  routingMode: RoutingMode;
  onRoutingModeChange: (mode: RoutingMode) => void;
  pageRange: string;
  onPageRangeChange: (range: string) => void;
}

export const AdvancedOptions: React.FC<AdvancedOptionsProps> = ({
  format,
  onFormatChange,
  routingMode,
  onRoutingModeChange,
  pageRange,
  onPageRangeChange,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="advanced-options-section" style={{ marginTop: '12px' }}>
      <button
        type="button"
        className="disclosure-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-controls="advanced-options-content"
      >
        <span>{isOpen ? '▾' : '▸'}</span>
        <span>{isOpen ? 'Hide advanced settings' : 'More options (format, page range, mode)'}</span>
      </button>

      {isOpen && (
        <div id="advanced-options-content" className="disclosure-body">
          {/* Format selection */}
          <div>
            <label htmlFor="output-format-select" style={{ display: 'block', fontWeight: 600, marginBottom: '6px' }}>
              Output format
            </label>
            <select
              id="output-format-select"
              value={format}
              onChange={(e) => onFormatChange(e.target.value as OutputFormat)}
              style={{
                width: '100%',
                maxWidth: '320px',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <option value="pdf">Printable PDF (Default)</option>
              <option value="html">Interactive Web Document (HTML)</option>
              <option value="epub">E-Reader Book (EPUB)</option>
            </select>
          </div>

          {/* Page Range */}
          <div>
            <label htmlFor="page-range-input" style={{ display: 'block', fontWeight: 600, marginBottom: '6px' }}>
              Page selection (optional)
            </label>
            <input
              id="page-range-input"
              type="text"
              placeholder="e.g. 1-10 or leave blank for all pages"
              value={pageRange}
              onChange={(e) => onPageRangeChange(e.target.value)}
              style={{
                width: '100%',
                maxWidth: '320px',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
              }}
            />
          </div>

          {/* Routing mode */}
          <div>
            <label htmlFor="routing-mode-select" style={{ display: 'block', fontWeight: 600, marginBottom: '6px' }}>
              Recognition mode
            </label>
            <select
              id="routing-mode-select"
              value={routingMode}
              onChange={(e) => onRoutingModeChange(e.target.value as RoutingMode)}
              style={{
                width: '100%',
                maxWidth: '320px',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <option value="auto">Automatic (Best accuracy and speed)</option>
              <option value="native_only">Fast Digital Extraction Only (skips scanned pages)</option>
              <option value="ocr_scanned_only">Force Scanned Recognition</option>
              <option value="max_accuracy">Maximum Accuracy (Deep table & layout recognition)</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
};
