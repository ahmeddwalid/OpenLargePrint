import React, { useState } from 'react';
import { UpdateInfo, dismissUpdate } from '../api/update-checker';

interface UpdateNotificationProps {
  updateInfo: UpdateInfo;
  onDismiss?: () => void;
}

export const UpdateNotification: React.FC<UpdateNotificationProps> = ({
  updateInfo,
  onDismiss,
}) => {
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const [showNotes, setShowNotes] = useState(false);

  if (!updateInfo.available || !updateInfo.latestVersion) {
    return null;
  }

  const handleInstallUpdate = async () => {
    if (!updateInfo.downloadUrl || !updateInfo.expectedSha256) {
      if (updateInfo.releaseUrl) {
        window.open(updateInfo.releaseUrl, '_blank');
      }
      return;
    }

    setIsUpdating(true);
    setUpdateStatus('Downloading installer...');

    try {
      const tauri = (window as unknown as { __TAURI__?: { core?: { invoke: (cmd: string, args: Record<string, unknown>) => Promise<unknown> } } }).__TAURI__;

      if (tauri?.core?.invoke) {
        setUpdateStatus('Downloading update package...');
        await tauri.core.invoke('download_and_apply_update', {
          downloadUrl: updateInfo.downloadUrl,
          expectedSha256: updateInfo.expectedSha256,
        });
        setUpdateStatus('Launching installer...');
      } else {
        // Fallback for browser / non-Tauri mode
        window.open(updateInfo.downloadUrl, '_blank');
        setIsUpdating(false);
      }
    } catch (err) {
      console.error('Update installation error:', err);
      setUpdateStatus('Automatic update could not start. Opening release page.');
      setTimeout(() => {
        if (updateInfo.releaseUrl) {
          window.open(updateInfo.releaseUrl, '_blank');
        }
        setIsUpdating(false);
      }, 1500);
    }
  };

  const handleDismiss = () => {
    if (updateInfo.latestVersion) {
      dismissUpdate(updateInfo.latestVersion);
    }
    if (onDismiss) {
      onDismiss();
    }
  };

  return (
    <div
      role="region"
      aria-label="Software update announcement"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '2px solid var(--border-color)',
        borderRadius: 'var(--radius-md)',
        padding: '16px 20px',
        margin: '16px 0',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-primary)' }}>
            OpenLargePrint {updateInfo.latestVersion} is available
          </div>
          <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Current installed version: {updateInfo.currentVersion}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {updateInfo.releaseNotes && (
            <button
              type="button"
              onClick={() => setShowNotes(!showNotes)}
              style={{
                minHeight: '48px',
                padding: '0 16px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-color)',
                backgroundColor: 'transparent',
                color: 'var(--text-primary)',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {showNotes ? 'Hide notes' : 'View changes'}
            </button>
          )}

          <button
            type="button"
            disabled={isUpdating}
            onClick={handleInstallUpdate}
            style={{
              minHeight: '48px',
              padding: '0 20px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              backgroundColor: 'var(--accent-primary)',
              color: 'var(--accent-text)',
              fontWeight: 700,
              cursor: isUpdating ? 'wait' : 'pointer',
              opacity: isUpdating ? 0.7 : 1,
            }}
          >
            {isUpdating ? (updateStatus ?? 'Updating...') : updateInfo.downloadUrl && updateInfo.expectedSha256 ? 'Download and install update' : 'View release downloads'}
          </button>

          <button
            type="button"
            onClick={handleDismiss}
            style={{
              minHeight: '48px',
              padding: '0 16px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-color)',
              backgroundColor: 'transparent',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
            }}
            aria-label="Dismiss update notification"
          >
            Dismiss
          </button>
        </div>
      </div>

      {updateStatus && (
        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }} aria-live="polite">
          {updateStatus}
        </div>
      )}

      {showNotes && updateInfo.releaseNotes && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--bg-primary)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-color)',
            maxHeight: '200px',
            overflowY: 'auto',
            fontSize: '0.9rem',
            whiteSpace: 'pre-wrap',
            color: 'var(--text-primary)',
          }}
        >
          {updateInfo.releaseNotes}
        </div>
      )}
    </div>
  );
};
