import React from 'react';
import { OutputFormat } from '../types';
import { sidecar } from '../api/sidecarClient';

export type LocationPreset = 'downloads' | 'desktop' | 'source' | 'custom';

interface ExportLocationPickerProps {
  outputPath: string;
  defaultFileName: string;
  outputFormat: OutputFormat;
  preset: LocationPreset;
  onPresetChange: (preset: LocationPreset) => void;
  onCustomPathSelected: (customPath: string) => void;
}

export const ExportLocationPicker: React.FC<ExportLocationPickerProps> = ({
  outputPath,
  defaultFileName,
  outputFormat,
  preset,
  onPresetChange,
  onCustomPathSelected,
}) => {
  const handleBrowseCustom = async () => {
    const ext = outputFormat === 'docx' ? 'docx' : outputFormat === 'html' ? 'html' : 'pdf';
    let baseName = defaultFileName;
    if (baseName.lastIndexOf('.') > 0) {
      baseName = baseName.substring(0, baseName.lastIndexOf('.'));
    }
    const proposedName = `${baseName}.${ext}`;

    const chosen = await sidecar.chooseSaveLocation(proposedName, ext);
    if (chosen) {
      onCustomPathSelected(chosen);
    }
  };

  const PRESETS: { id: LocationPreset; label: string; description: string }[] = [
    { id: 'downloads', label: 'Downloads', description: 'Save into your Downloads folder (Default)' },
    { id: 'desktop', label: 'Desktop', description: 'Save directly onto your Windows Desktop' },
    { id: 'source', label: 'Source folder', description: 'Save in the same folder as the original document' },
    { id: 'custom', label: 'Custom...', description: 'Choose a custom folder or custom file name' },
  ];

  return (
    <section className="decision-step" aria-labelledby="step-destination-label">
      <h2 id="step-destination-label" className="step-label">
        Save location
      </h2>
      <div
        className="export-location-card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          padding: '16px 18px',
          backgroundColor: 'var(--bg-primary)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)',
        }}
      >
        {/* Segmented location buttons A11Y-001 */}
        <div
          role="radiogroup"
          aria-label="Export location destination presets"
          style={{
            display: 'flex',
            gap: '8px',
            flexWrap: 'wrap',
          }}
        >
          {PRESETS.map((p) => {
            const isActive = preset === p.id;
            return (
              <button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={isActive}
                onClick={() => {
                  if (p.id === 'custom') {
                    handleBrowseCustom();
                  } else {
                    onPresetChange(p.id);
                  }
                }}
                style={{
                  minHeight: '48px',
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-sm)',
                  border: `2px solid ${isActive ? 'var(--accent-primary)' : 'var(--border-color)'}`,
                  backgroundColor: isActive ? 'var(--accent-primary)' : 'var(--bg-surface)',
                  color: isActive ? 'var(--accent-text)' : 'var(--text-primary)',
                  fontWeight: 600,
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                title={p.description}
              >
                {p.label}
              </button>
            );
          })}
        </div>

        {/* Live resolved output file path */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              flex: '1 1 280px',
              minHeight: '48px',
              padding: '10px 14px',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              fontFamily: 'Consolas, "Courier New", monospace',
              fontSize: '0.875rem',
              color: 'var(--text-primary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              display: 'flex',
              alignItems: 'center',
            }}
            title={outputPath}
          >
            {outputPath || 'No destination selected'}
          </div>

          {preset === 'custom' && (
            <button
              type="button"
              className="secondary-btn"
              onClick={handleBrowseCustom}
              aria-label="Change custom export destination folder or file name"
              style={{ minHeight: '48px' }}
            >
              Browse...
            </button>
          )}
        </div>

        <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', margin: '0' }}>
          {preset === 'downloads' && 'Default: Output file will be saved directly in your Downloads folder.'}
          {preset === 'desktop' && 'Output file will be saved directly on your Desktop for easy access.'}
          {preset === 'source' && 'Output file will be saved in the same directory as your original document.'}
          {preset === 'custom' && 'Custom destination folder and file name selected.'}
        </p>
      </div>
    </section>
  );
};
