import React from 'react';
import { ProgressInfo } from '../types';

interface ProgressScreenProps {
  progress: ProgressInfo;
  fileName: string;
  onCancel: () => void;
}

export const ProgressScreen: React.FC<ProgressScreenProps> = ({
  progress,
  fileName,
  onCancel,
}) => {
  return (
    <section
      className="progress-container"
      aria-labelledby="progress-title"
      role="region"
    >
      <div className="progress-header">
        <div>
          <h2 id="progress-title" style={{ fontSize: '1.5rem', marginBottom: '4px' }}>
            Converting Document
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>
            {fileName}
          </p>
        </div>
        <span
          style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-primary)' }}
          aria-hidden="true"
        >
          {progress.percent}%
        </span>
      </div>

      <div
        className="progress-message"
        aria-live="polite"
        aria-atomic="true"
      >
        {progress.humanMessage || 'Preparing conversion...'}
      </div>

      <div className="progress-bar-wrapper">
        <div
          className="progress-fill"
          style={{ width: `${Math.min(100, Math.max(0, progress.percent))}%` }}
          role="progressbar"
          aria-valuenow={progress.percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Conversion progress"
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-start', marginTop: '12px' }}>
        <button
          type="button"
          className="secondary-btn"
          onClick={onCancel}
          aria-label="Cancel current document conversion"
        >
          Cancel conversion
        </button>
      </div>
    </section>
  );
};
