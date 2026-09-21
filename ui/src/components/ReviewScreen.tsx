import React, { useState } from 'react';
import { ReviewItem } from '../types';
import { useI18n } from '../i18n/i18n';

interface ReviewScreenProps {
  reviewItems: ReviewItem[];
  onAccept: (itemId: string, editedText?: string) => void;
  onAcceptAll?: (currentId?: string, currentEditedText?: string) => void;
  onRetry: (item: ReviewItem) => Promise<string | null>;
  onFinish: () => void;
}

export const ReviewScreen: React.FC<ReviewScreenProps> = ({
  reviewItems,
  onAccept,
  onAcceptAll,
  onRetry,
  onFinish,
}) => {
  const { t } = useI18n();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const [editedText, setEditedText] = useState<string>('');
  const [retryResult, setRetryResult] = useState<string | null>(null);

  const currentItem = reviewItems[currentIndex] || null;

  React.useEffect(() => {
    if (currentItem) {
      setEditedText(currentItem.converted_text);
      setRetryResult(null);
    }
  }, [currentIndex, currentItem]);

  if (!currentItem || reviewItems.length === 0) {
    return (
      <div className="panel" role="status">
        <h2>{t('review.complete_title')}</h2>
        <p style={{ marginTop: '8px', marginBottom: '16px' }}>
          {t('review.complete_desc')}
        </p>
        <button
          type="button"
          className="primary-btn"
          onClick={onFinish}
          style={{ minHeight: '48px', padding: '0 24px' }}
        >
          {t('review.finish')}
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

  const handleAcceptAll = () => {
    if (onAcceptAll) {
      onAcceptAll(currentItem.id, editedText);
    } else {
      onFinish();
    }
  };

  const handleRetryCurrent = async () => {
    setIsRetrying(true);
    try {
      const result = await onRetry(currentItem);
      setRetryResult(result || 'Recognition could not be repeated. Your current correction is unchanged.');
    } catch {
      setRetryResult('Recognition could not be repeated. Your current correction is unchanged.');
    } finally {
      setIsRetrying(false);
    }
  };

  const pendingCount = reviewItems.filter((i) => i.status === 'pending').length;

  return (
    <section className="review-container" aria-labelledby="review-title">
      {/* Plain language banner UI-005 */}
      <div className="review-banner" role="alert">
        {t('review.banner', { count: pendingCount })}
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <h2 id="review-title" style={{ fontSize: '1.375rem' }}>
          Page {currentItem.source_page}: Section {currentIndex + 1} of {reviewItems.length}
        </h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
          <button
            type="button"
            className="secondary-btn"
            onClick={handleAcceptAll}
            aria-label={t('review.accept_all_aria')}
            style={{
              minHeight: '48px',
              padding: '0 16px',
              fontWeight: 600,
              backgroundColor: 'var(--bg-surface)',
              border: '2px solid var(--border-color)',
            }}
          >
            {t('review.accept_all')}
          </button>
          <button
            type="button"
            className="secondary-btn"
            onClick={handlePrev}
            disabled={currentIndex === 0}
            aria-label={t('review.previous')}
            style={{ minHeight: '48px', padding: '0 16px' }}
          >
            {t('review.previous')}
          </button>
          <button
            type="button"
            className="secondary-btn"
            onClick={handleNext}
            disabled={currentIndex === reviewItems.length - 1}
            aria-label={t('review.next')}
            style={{ minHeight: '48px', padding: '0 16px' }}
          >
            {t('review.next')}
          </button>
        </div>
      </div>

      <p style={{ color: 'var(--text-secondary)', marginTop: '6px' }}>
        <strong>{t('review.reason_label')}</strong> {currentItem.reason}
      </p>

      {/* Side-by-side split view UI-004 */}
      <div className="review-split">
        {/* Left: Original Scan/Page Crop */}
        <div className="review-pane" aria-labelledby="original-preview-title">
          <div id="original-preview-title" className="pane-title">
            {t('review.original_preview', { page: currentItem.source_page })}
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
            {currentItem.original_preview ? (
              <img src={currentItem.original_preview} alt={`Original page ${currentItem.source_page}`} style={{ width: '100%', height: 'auto' }} />
            ) : currentItem.original_snippet || 'Page preview unavailable. Compare this text with the original document.'}
          </div>
        </div>

        {/* Right: Converted Large-Print Output */}
        <div className="review-pane" aria-labelledby="converted-preview-title">
          <div id="converted-preview-title" className="pane-title">
            {t('review.converted_title')}
          </div>
          <label htmlFor="edit-converted-text" style={{ display: 'none' }}>
            {t('review.converted_title')}
          </label>
          <textarea
            id="edit-converted-text"
            className="pane-content"
            value={editedText}
            readOnly={!currentItem.block_id}
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

      {retryResult && (
        <section className="review-pane" aria-live="polite">
          <h3>Repeated recognition result</h3>
          <p>Compare this page result with the original. Copy any corrections into the section above before accepting.</p>
          <p style={{ whiteSpace: 'pre-wrap' }}>{retryResult}</p>
        </section>
      )}

      <div className="review-actions" style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <button
          type="button"
          className="secondary-btn"
          onClick={handleRetryCurrent}
          disabled={isRetrying}
          aria-label={t('review.retry')}
          style={{ minHeight: '48px', padding: '0 18px' }}
        >
          {isRetrying ? t('review.retrying') : t('review.retry')}
        </button>

        <button
          type="button"
          className="secondary-btn"
          onClick={handleAcceptAll}
          aria-label={t('review.accept_all_aria')}
          style={{
            minHeight: '48px',
            padding: '0 22px',
            fontWeight: 700,
            backgroundColor: 'var(--bg-surface)',
            border: '2px solid var(--border-color)',
          }}
        >
          {t('review.accept_all')}
        </button>

        <button
          type="button"
          className="primary-btn"
          onClick={handleAcceptCurrent}
          aria-label={t('review.accept_as_is')}
          style={{ minHeight: '48px', padding: '0 22px' }}
        >
          {t('review.accept_as_is')}
        </button>
      </div>
    </section>
  );
};
