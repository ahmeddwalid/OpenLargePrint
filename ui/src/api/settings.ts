/**
 * Remembered choices and the default save location (UI-001, UI-006).
 *
 * The reader should not have to make the same three choices every time, so the
 * last text size, format and paper size are kept on this computer. The large-print
 * file is saved next to the original as "<name> - large print.<ext>" unless the
 * reader picks another place.
 */

import { OutputFormat, PaperSize, TextSize } from '../types';

export interface SavedSettings {
  textSize: TextSize;
  customBodyPt: number | null;
  paperSize: PaperSize;
  outputFormat: Exclude<OutputFormat, 'searchable_pdf'>;
}

export const DEFAULT_SETTINGS: SavedSettings = {
  textSize: 20,
  customBodyPt: null,
  paperSize: 'A4',
  outputFormat: 'pdf',
};

const SETTINGS_KEY = 'openlargeprint_settings';
const TEXT_SIZES: TextSize[] = [18, 20, 24, 28];

export function loadSettings(): SavedSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    const data = JSON.parse(raw) ?? {};
    const custom = Number(data.customBodyPt);
    return {
      textSize: TEXT_SIZES.includes(data.textSize) ? data.textSize : DEFAULT_SETTINGS.textSize,
      customBodyPt: Number.isFinite(custom) && custom >= 14 && custom <= 48 ? custom : null,
      paperSize: data.paperSize === 'A3' ? 'A3' : 'A4',
      outputFormat: data.outputFormat === 'docx' || data.outputFormat === 'html' ? data.outputFormat : 'pdf',
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(settings: SavedSettings): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Storage can be full or disabled; the choices simply are not remembered.
  }
}

export function extensionFor(format: OutputFormat): string {
  return format === 'docx' ? 'docx' : format === 'html' ? 'html' : 'pdf';
}

function splitPath(path: string): { folder: string; separator: string; name: string } {
  const separator = path.includes('\\') ? '\\' : '/';
  const index = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
  return {
    folder: index >= 0 ? path.substring(0, index) : '',
    separator,
    name: index >= 0 ? path.substring(index + 1) : path,
  };
}

/** Path or file name without its extension (a dot in a folder name is not an extension). */
function stem(path: string): string {
  const nameStart = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\')) + 1;
  const dot = path.lastIndexOf('.');
  return dot > nameStart ? path.substring(0, dot) : path;
}

/** "Contract Law.pdf" -> "Contract Law - large print.pdf" (or "- searchable" for the searchable copy). */
export function outputFileName(sourceName: string, format: OutputFormat): string {
  const suffix = format === 'searchable_pdf' ? 'searchable' : 'large print';
  return `${stem(sourceName)} - ${suffix}.${extensionFor(format)}`;
}

/**
 * Where the converted file goes: the reader's own choice if they made one
 * (with the extension kept in step with the format), otherwise beside the
 * original, otherwise in Downloads.
 */
export function proposedOutputPath(options: {
  sourceName: string;
  sourcePath?: string | null;
  format: OutputFormat;
  customPath?: string | null;
  downloadsDir?: string | null;
}): string {
  const { sourceName, sourcePath, format, customPath, downloadsDir } = options;
  const ext = extensionFor(format);
  if (customPath) {
    return `${stem(customPath)}.${ext}`;
  }
  const fileName = outputFileName(sourceName, format);
  if (sourcePath) {
    const { folder, separator } = splitPath(sourcePath);
    if (folder) return `${folder}${separator}${fileName}`;
  }
  if (downloadsDir) {
    const separator = downloadsDir.includes('\\') ? '\\' : '/';
    return `${downloadsDir.replace(/[\\/]+$/, '')}${separator}${fileName}`;
  }
  return fileName;
}

export function describePath(path: string): { folder: string; name: string } {
  const { folder, name } = splitPath(path);
  return { folder, name };
}
