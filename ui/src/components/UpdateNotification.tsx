import React, { useState } from 'react';
import { UpdateInfo, dismissUpdate, installUpdate, openReleasePage } from '../api/update-checker';
import { useI18n } from '../i18n/i18n';

interface UpdateNotificationProps {
  updateInfo: UpdateInfo;
  onDismiss?: () => void;
}

type Phase = { kind: 'idle' } | { kind: 'downloading'; percent: number } | { kind: 'starting' } | { kind: 'failed'; reason: string };

export const UpdateNotification: React.FC<UpdateNotificationProps> = ({ updateInfo, onDismiss }) => {
  const { t } = useI18n();
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' });
  const [showNotes, setShowNotes] = useState(false);

  if (!updateInfo.available || !updateInfo.latestVersion) {
    return null;
  }

  const busy = phase.kind === 'downloading' || phase.kind === 'starting';
  const installLabel = !updateInfo.canInstall
    ? t('update.download_page')
    : updateInfo.installKind === 'app_image'
      ? t('update.install_restart')
      : t('update.install');

  const handleInstall = async () => {
    if (!updateInfo.canInstall) {
      openReleasePage().catch(() => setPhase({ kind: 'failed', reason: t('update.browser_failed') }));
      return;
    }
    setPhase({ kind: 'downloading', percent: 0 });
    try {
      await installUpdate((downloaded, total) => {
        if (total > 0 && downloaded >= total) setPhase({ kind: 'starting' });
        else setPhase({ kind: 'downloading', percent: total > 0 ? Math.floor((downloaded / total) * 100) : 0 });
      });
      setPhase({ kind: 'starting' });
    } catch (err) {
      setPhase({ kind: 'failed', reason: err instanceof Error ? err.message : String(err) });
    }
  };

  const handleDismiss = () => {
    dismissUpdate(updateInfo.latestVersion as string);
    onDismiss?.();
  };

  const status =
    phase.kind === 'downloading' ? t('update.downloading', { percent: String(phase.percent) })
      : phase.kind === 'starting' ? t('update.starting')
        : phase.kind === 'failed' ? t('update.failed', { reason: phase.reason })
          : !updateInfo.canInstall ? t(updateInfo.installKind === 'manual' ? 'update.manual_hint' : 'update.page_hint')
            : updateInfo.downloadSize ? t('update.size', { size: String(Math.round(updateInfo.downloadSize / 1048576)) })
              : null;

  return (
    <section className="update-banner" aria-labelledby="update-title">
      <div className="update-banner-row">
        <div>
          <h2 id="update-title" className="update-title">
            {t('update.title', { version: updateInfo.latestVersion })}
          </h2>
          <p className="field-help">{t('update.current', { version: updateInfo.currentVersion })}</p>
        </div>
        <div className="update-actions">
          {updateInfo.releaseNotes && (
            <button type="button" className="secondary-btn" aria-expanded={showNotes} onClick={() => setShowNotes(!showNotes)}>
              {showNotes ? t('update.notes_hide') : t('update.notes_show')}
            </button>
          )}
          <button type="button" className="primary-btn" disabled={busy} onClick={handleInstall}>
            {phase.kind === 'failed' ? t('update.retry') : installLabel}
          </button>
          <button type="button" className="secondary-btn" disabled={busy} onClick={handleDismiss}>
            {t('update.later')}
          </button>
        </div>
      </div>
      {phase.kind === 'downloading' && (
        <progress className="update-progress" max={100} value={phase.percent} aria-label={t('update.progress_aria')} />
      )}
      {status && (
        <p className={phase.kind === 'failed' ? 'update-status failed' : 'update-status'} role={phase.kind === 'failed' ? 'alert' : undefined} aria-live="polite">
          {status}
        </p>
      )}
      {showNotes && updateInfo.releaseNotes && <div className="update-notes">{updateInfo.releaseNotes}</div>}
    </section>
  );
};
