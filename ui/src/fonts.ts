/**
 * Reading fonts the reader can choose for the large-print copy (OUT-001, LANG-001).
 *
 * The list matches the engine's font registry (exporters/fonts.py); a test keeps
 * the two in step. Each entry's description is translated under `font.<id>`.
 */

export interface ReadingFont {
  id: string;
  family: string;
}

export const LATIN_FONTS: ReadingFont[] = [
  { id: 'atkinson', family: 'Atkinson Hyperlegible' },
  { id: 'lexend', family: 'Lexend' },
  { id: 'andika', family: 'Andika' },
  { id: 'noto-sans', family: 'Noto Sans' },
  { id: 'noto-serif', family: 'Noto Serif' },
];

export const ARABIC_FONTS: ReadingFont[] = [
  { id: 'noto-sans-arabic', family: 'Noto Sans Arabic' },
  { id: 'noto-naskh-arabic', family: 'Noto Naskh Arabic' },
  { id: 'amiri', family: 'Amiri' },
  { id: 'ibm-plex-sans-arabic', family: 'IBM Plex Sans Arabic' },
  { id: 'tajawal', family: 'Tajawal' },
  { id: 'readex-pro', family: 'Readex Pro' },
];

export const DEFAULT_LATIN_FONT = 'atkinson';
export const DEFAULT_ARABIC_FONT = 'noto-sans-arabic';

export function latinFont(id: string | null | undefined): ReadingFont {
  return LATIN_FONTS.find((f) => f.id === id) ?? LATIN_FONTS[0];
}

export function arabicFont(id: string | null | undefined): ReadingFont {
  return ARABIC_FONTS.find((f) => f.id === id) ?? ARABIC_FONTS[0];
}

/** CSS font stack: the chosen Latin face, then the chosen Arabic face for Arabic letters. */
export function fontStack(latinId: string, arabicId: string): string {
  return `"${latinFont(latinId).family}", "${arabicFont(arabicId).family}", "DejaVu Sans", sans-serif`;
}
