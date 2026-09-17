import React, { useState } from 'react';
import { ReviewItem } from '../types';

interface ReviewScreenProps {
  reviewItems: ReviewItem[];
  onAccept: (itemId: string, editedText?: string) => void;
  onRetry: (item: ReviewItem) => Promise<void>;
  onFinish: () => void;
}

export const ReviewScreen: React.FC<ReviewScreenProps> = ({
  reviewItems,
  onAccept,
  onRetry,
  onFinish,
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const [editedText, setEditedText] = useState<string>('');

  const currentItem = reviewItems[currentIndex] || null;

  React.useEffect(() => {
    if (currentItem) {
      setEditedText(currentItem.converted_text);
    }
  }, [currentIndex, currentItem]);

  if (!currentItem || reviewItems.length === 0) {
    return (
      <div className="panel" role="status">
        <h2>Review Complete</h2>
        <p style={{ marginTop: '8px', marginBottom: '16px' }}>
          All flagged sections have been reviewed and accepted.
        </p>
        <button type="button" className="primary-btn" onClick={onFinish}>
          Continue to Large-Print Reader
        </button>
      </div>
    );
  }

  const handleNext = () => {
    if (currentIndex < reviewItems.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const handleAcceptCurrent = () => {
    onAccept(currentItem.id, editedText);
    if (currentIndex < reviewItems.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      onFinish();
    }
  };

  const handleRetryCurrent = async () => {
    setIsRetrying(true);
    try {
      await onRetry(currentItem);
    } finally {
      setIsRetrying(false);
    }
  };

  const pendingCount = reviewItems.filter((i) => i.status === 'pending').length;

  return (
    <section className="review-container" aria-labelledby="review-title">
      {/* Plain language banner UI-005 */}
      <div className="review-banner" role="alert">
        {pendingCount === 1
          ? '1 section may need your review before reading or printing'
          : `${pendingCount} sections may need your review before reading or printing`}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 id="review-title" style={{ fontSize: '22px' }}>
          Page {currentItem.source_page}: Section {currentIndex + 1} of {reviewItems.length}
        </h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className="secondary-btn"
            onClick={handlePrev}
            disabled={currentIndex === 0}
            aria-label="Previous flagged section"
          >
            Previous
          </button>
          <button
            type="button"
            className="secondary-btn"
            onClick={handleNext}
            disabled={currentIndex === reviewItems.length - 1}
            aria-label="Next flagged section"
          >
            Next
          </button>
        </div>
      </div>

      <p style={{ color: 'var(--text-secondary)' }}>
        Reason: {currentItem.reason}
      </p>

      {/* Side-by-side split view UI-004 */}
      <div className="review-split">
        {/* Left: Original Scan/Page Crop */}
        <div className="review-pane" aria-labelledby="original-preview-title">
          <div id="original-preview-title" className="pane-title">
            Original Source Preview (Page {currentItem.source_page})
          </div>
          <div
            className="pane-content"
            style={{
              backgroundColor: 'var(--bg-primary)',
              padding: '16px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-color)',
              fontFamily: 'monospace',
              whiteSpace: 'pre-wrap',
            }}
          >
            {currentItem.original_snippet}
          </div>
        </div>

        {/* Right: Converted Large-Print Output */}
        <div className="review-pane" aria-labelledby="converted-preview-title">
          <div id="converted-preview-title" className="pane-title">
            Converted Large-Print Text
          </div>
          <label htmlFor="edit-converted-text" style={{ display: 'none' }}>
            Edit converted text
          </label>
          <textarea
            id="edit-converted-text"
            className="pane-content"
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            style={{
              width: '100%',
              minHeight: '260px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              padding: '12px',
              fontFamily: 'inherit',
              resize: 'vertical',
            }}
          />
        </div>
      </div>

      {/* Action buttons */}
      <div className="review-actions">
        <button
          type="button"
          className="secondary-btn"
          onClick={handleRetryCurrent}
          disabled={isRetrying}
          aria-label="Retry recognition with maximum accuracy"
        >
          {isRetrying ? 'Re-recognizing page...' : 'Retry with Maximum Accuracy'}
        </button>

        <button
          type="button"
          className="primary-btn"
          onClick={handleAcceptCurrent}
          aria-label="Accept this section and continue"
        >
          Accept as-is
        </button>
      </div>
    </section>
  );
};
