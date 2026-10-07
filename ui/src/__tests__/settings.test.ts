import { afterEach, describe, expect, it } from 'vitest';
import { DEFAULT_SETTINGS, loadSettings, outputFileName, proposedOutputPath, saveSettings } from '../api/settings';

afterEach(() => localStorage.clear());

describe('remembered settings', () => {
  it('starts at 20 pt, PDF, A4', () => {
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it('remembers the last choices', () => {
    saveSettings({ textSize: 28, customBodyPt: null, paperSize: 'A3', outputFormat: 'docx' });
    expect(loadSettings()).toEqual({ textSize: 28, customBodyPt: null, paperSize: 'A3', outputFormat: 'docx' });
  });

  it('ignores damaged or out-of-range values', () => {
    localStorage.setItem('openlargeprint_settings', '{"textSize": 7, "customBodyPt": 400, "paperSize": "B5", "outputFormat": "exe"}');
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
    localStorage.setItem('openlargeprint_settings', 'not json');
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
  });
});

describe('where the large-print file is saved', () => {
  it('names the copy after the original', () => {
    expect(outputFileName('Contract Law.pdf', 'pdf')).toBe('Contract Law - large print.pdf');
    expect(outputFileName('Notes.v2.docx', 'html')).toBe('Notes.v2 - large print.html');
    expect(outputFileName('Scan.pdf', 'searchable_pdf')).toBe('Scan - searchable.pdf');
  });

  it('saves next to the original by default', () => {
    expect(proposedOutputPath({ sourceName: 'Book.pdf', sourcePath: 'C:\\Users\\Mona\\Books\\Book.pdf', format: 'docx' }))
      .toBe('C:\\Users\\Mona\\Books\\Book - large print.docx');
    expect(proposedOutputPath({ sourceName: 'Book.pdf', sourcePath: '/home/mona/Book.pdf', format: 'pdf' }))
      .toBe('/home/mona/Book - large print.pdf');
  });

  it('falls back to Downloads when the original folder is unknown', () => {
    expect(proposedOutputPath({ sourceName: 'Book.pdf', format: 'pdf', downloadsDir: '/home/mona/Downloads/' }))
      .toBe('/home/mona/Downloads/Book - large print.pdf');
  });

  it('keeps a chosen path, following the format', () => {
    expect(proposedOutputPath({ sourceName: 'Book.pdf', sourcePath: '/a/Book.pdf', format: 'html', customPath: '/b/my.copy/Mine.pdf' }))
      .toBe('/b/my.copy/Mine.html');
    expect(proposedOutputPath({ sourceName: 'Book.pdf', format: 'pdf', customPath: '/b/my.copy/Mine' }))
      .toBe('/b/my.copy/Mine.pdf');
  });
});
