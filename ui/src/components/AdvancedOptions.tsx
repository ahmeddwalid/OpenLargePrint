import React, { useState } from 'react';
import { RoutingMode } from '../types';
import {
  checkForUpdates,
  isAutoUpdateEnabled,
  setAutoUpdateEnabled,
  CURRENT_VERSION,
} from '../api/update-checker';

interface AdvancedOptionsProps {
  routingMode: RoutingMode;
  onRoutingModeChange: (mode: RoutingMode) => void;
  pageRange: string;
  onPageRangeChange: (range: string) => void;
}

export const AdvancedOptions: React.FC<AdvancedOptionsProps> = ({
  routingMode,
  onRoutingModeChange,
  pageRange,
  onPageRangeChange,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [autoUpdate, setAutoUpdate] = useState<boolean>(() => isAutoUpdateEnabled());
  const [isCheckingUpdate, setIsCheckingUpdate] = useState(false);
  const [manualCheckStatus, setManualCheckStatus] = useState<string | null>(null);

  const handleCheckUpdatesNow = async () => {
    setIsCheckingUpdate(true);
    setManualCheckStatus('Connecting to update server...');
    try {
      const res = await checkForUpdates(true);
      if (res.available && res.latestVersion) {
        setManualCheckStatus(`New version ${res.latestVersion} is available.`);
      } else {
        setManualCheckStatus(`Up to date. You are using version ${CURRENT_VERSION}.`);
      }
    } catch {
      setManualCheckStatus('Could not check for updates at this time.');
    } finally {
      setIsCheckingUpdate(false);
    }
  };

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
        <span>{isOpen ? 'Hide advanced settings' : 'More options (page range, recognition mode)'}</span>
      </button>

      {isOpen && (
        <div id="advanced-options-content" className="disclosure-body">
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
              <option value="max_accuracy">Maximum Accuracy (Default — 300 DPI, multi-core accelerated)</option>
              <option value="auto">Automatic (Balanced)</option>
              <option value="native_only">Fast Digital Extraction Only (skips scanned pages)</option>
              <option value="ocr_scanned_only">Force Scanned Recognition</option>
            </select>
          </div>

          {/* Software updates */}
          <div style={{ marginTop: '8px', paddingTop: '12px', borderTop: '1px solid var(--border-color)' }}>
            <div style={{ fontWeight: 600, marginBottom: '8px' }}>Software updates</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', minHeight: '36px' }}>
              <input
                type="checkbox"
                checked={autoUpdate}
                onChange={(e) => {
                  setAutoUpdate(e.target.checked);
                  setAutoUpdateEnabled(e.target.checked);
                }}
                style={{ width: '18px', height: '18px' }}
              />
              <span>Check for updates automatically on startup</span>
            </label>

            <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={handleCheckUpdatesNow}
                disabled={isCheckingUpdate}
                style={{
                  minHeight: '44px',
                  padding: '0 16px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                  backgroundColor: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  fontWeight: 600,
                  cursor: isCheckingUpdate ? 'wait' : 'pointer',
                }}
              >
                {isCheckingUpdate ? 'Checking for updates...' : 'Check for updates now'}
              </button>
              {manualCheckStatus && (
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }} aria-live="polite">
                  {manualCheckStatus}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
