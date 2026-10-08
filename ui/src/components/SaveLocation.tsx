import React from 'react';
import { OutputFormat } from '../types';
import { sidecar } from '../api/sidecarClient';
import { describePath, extensionFor } from '../api/settings';
import { useI18n } from '../i18n/i18n';

interface SaveLocationProps {
  outputPath: string;
  outputFormat: OutputFormat;
  isCustom: boolean;
  onChoose: (path: string) => void;
  onReset: () => void;
}

/** One line: where the file will be saved, with a way to change it. */
export const SaveLocation: React.FC<SaveLocationProps> = ({ outputPath, outputFormat, isCustom, onChoose, onReset }) => {
  const { t } = useI18n();
  const { folder, name } = describePath(outputPath);

  const choose = async () => {
    const ext = extensionFor(outputFormat);
    const chosen = await sidecar.chooseSaveLocation(name, ext, folder || undefined);
    if (chosen) onChoose(chosen);
  };

  return (
    <div className="save-line">
      <div className="save-target" aria-live="polite">
        <span className="save-label">{t('save.label')}</span>
        <span className="save-name">{name}</span>
        {folder && <span className="save-folder" title={folder}>{t('save.in_folder', { folder })}</span>}
      </div>
      <div className="save-actions">
        <button type="button" className="secondary-btn" onClick={choose}>
          {t('save.change')}
        </button>
        {isCustom && (
          <button type="button" className="link-btn" onClick={onReset}>
            {t('save.reset')}
          </button>
        )}
      </div>
    </div>
  );
};
