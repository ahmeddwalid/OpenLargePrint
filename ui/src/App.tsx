import React, { useEffect, useState } from 'react';
import { AdvancedOptions } from './components/AdvancedOptions';
import { DocumentTypeSelector } from './components/DocumentTypeSelector';
import { FilePicker } from './components/FilePicker';
import { PaperSizeSelector } from './components/PaperSizeSelector';
import { ProgressScreen } from './components/ProgressScreen';
import { ReaderView } from './components/ReaderView';
import { RecentDocuments, RecentDocumentItem } from './components/RecentDocuments';
import { ReviewScreen } from './components/ReviewScreen';
import { SaveLocation } from './components/SaveLocation';
import { SettingsMenu } from './components/SettingsMenu';
import { TextSizeSelector } from './components/TextSizeSelector';
import { UpdateNotification } from './components/UpdateNotification';
import { sidecar } from './api/sidecarClient';
import { UpdateInfo, checkForUpdates, isUpdateDismissed } from './api/update-checker';
import { loadSettings, proposedOutputPath, saveSettings, SavedSettings } from './api/settings';
import { useI18n } from './i18n/i18n';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import {
  AppTheme,
  ConversionSettings,
  DocumentIR,
  OutputFormat,
  PaperSize,
  ProgressInfo,
  ReviewItem,
  TextSize,
} from './types';

type ViewMode = 'home' | 'progress' | 'review' | 'reader';

const RECENT_DOCS_KEY = 'openlargeprint_recent_docs';

function loadRecentDocs(): RecentDocumentItem[] {
  try {
    const raw = localStorage.getItem(RECENT_DOCS_KEY);
    if (raw) {
      return JSON.parse(raw);
    }
  } catch (e) {
    console.error('Failed to parse recent docs:', e);
  }
  return [];
}

function saveRecentDocs(items: RecentDocumentItem[]) {
  try {
    localStorage.setItem(RECENT_DOCS_KEY, JSON.stringify(items));
  } catch (e) {
    try {
      const trimmed = items.map((it, idx) => (idx === 0 ? it : { ...it, documentIR: undefined }));
      localStorage.setItem(RECENT_DOCS_KEY, JSON.stringify(trimmed));
    } catch (e2) {
      console.error('Failed to save recent docs:', e2);
    }
  }
}

export const App: React.FC = () => {
  // i18n for translations and direction
  const { t, locale, direction } = useI18n();

  // Theme State (A11Y-004)
  const [theme, setTheme] = useState<AppTheme>(() => {
    const saved = localStorage.getItem('openlargeprint_theme');
    if (saved === 'auto' || saved === 'light' || saved === 'sepia' || saved === 'dark') {
      return saved;
    }
    return 'sepia';
  });

  // Document Selection & Settings State (UI-001, UI-006). The three main
  // choices are remembered; 20 pt, PDF and A4 are the first-run defaults.
  const [initialSettings] = useState<SavedSettings>(loadSettings);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [textSize, setTextSize] = useState<TextSize>(initialSettings.textSize);
  const [customBodyPt, setCustomBodyPt] = useState<number | null>(initialSettings.customBodyPt);
  const [paperSize, setPaperSize] = useState<PaperSize>(initialSettings.paperSize);
  const [mainFormat, setMainFormat] = useState<Exclude<OutputFormat, 'searchable_pdf'>>(initialSettings.outputFormat);
  const [customOutputPath, setCustomOutputPath] = useState<string | null>(null);
  const [downloadsDir, setDownloadsDir] = useState<string | null>(null);
  const [pageRange, setPageRange] = useState<string>('');
  const [monochrome, setMonochrome] = useState<boolean>(false);
  const [pageBreakOnSourcePage, setPageBreakOnSourcePage] = useState<boolean>(false);
  const [searchableOriginal, setSearchableOriginal] = useState<boolean>(false);
  const outputFormat: OutputFormat = searchableOriginal ? 'searchable_pdf' : mainFormat;

  useEffect(() => {
    saveSettings({ textSize, customBodyPt, paperSize, outputFormat: mainFormat });
  }, [textSize, customBodyPt, paperSize, mainFormat]);

  // Workflow State
  const [viewMode, setViewMode] = useState<ViewMode>('home');
  const [progress, setProgress] = useState<ProgressInfo>({
    currentPage: 0,
    totalPages: 0,
    stage: 'idle',
    humanMessage: '',
    percent: 0,
  });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [documentIR, setDocumentIR] = useState<DocumentIR | null>(null);
  const [exportedFilePath, setExportedFilePath] = useState<string | null>(null);
  const [recentDocs, setRecentDocs] = useState<RecentDocumentItem[]>([]);

  // Load recent documents on startup
  useEffect(() => {
    setRecentDocs(loadRecentDocs());
  }, []);

  // Synchronize theme to document element and persist preference
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('openlargeprint_theme', theme);
  }, [theme]);

  // The Downloads folder is the fallback when the original's folder is unknown.
  useEffect(() => {
    sidecar.getSystemPaths().then((paths) => {
      setDownloadsDir(paths.downloads || null);
    });
  }, []);

  // Check for CLI argument file (e.g. from Windows Explorer right-click "Enlarge with OpenLargePrint")
  useEffect(() => {
    sidecar.getCliArgFile().then((argFile) => {
      if (argFile) {
        const mockFile = new File([''], argFile.name, { type: 'application/pdf' });
        (mockFile as any).nativePath = argFile.path;
        (mockFile as any).customSize = argFile.size;
        setSelectedFile(mockFile);
      }
    });
  }, []);

  // Background update check (SEC-009: completely separate from document conversion)
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);

  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const res = await checkForUpdates(false);
        if (res.available && res.latestVersion && !isUpdateDismissed(res.latestVersion)) {
          setUpdateInfo(res);
        }
      } catch {
        // Quiet fallback if offline or unreachable
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  const getProposedExportPath = (): string =>
    proposedOutputPath({
      sourceName: selectedFile ? selectedFile.name : 'document',
      sourcePath: (selectedFile as any)?.nativePath,
      format: outputFormat,
      customPath: customOutputPath,
      downloadsDir,
    });

  const handleStartConversion = async () => {
    if (!selectedFile) return;

    setErrorMessage(null);
    setViewMode('progress');
    setProgress({
      currentPage: 0,
      totalPages: 0,
      stage: 'starting',
      humanMessage: t('progress.starting'),
      percent: 0,
    });

    const targetOutputPath = getProposedExportPath();
    const settings: ConversionSettings = {
      textSize,
      customBodyPt,
      paperSize,
      outputFormat,
      pageRange,
      monochrome,
      pageBreakOnSourcePage,
      outputPath: targetOutputPath,
    };

    const targetDocPath = (selectedFile as any)?.nativePath || selectedFile.name;
    await sidecar.startConversion(targetDocPath, settings, {
      onProgress: (p) => {
        setProgress(p);
      },
      onError: (err) => {
        setErrorMessage(err);
        setViewMode('home');
      },
      onCancelled: () => {
        setErrorMessage(t('error.conversion_cancelled'));
        setViewMode('home');
      },
      onSuccess: (result) => {
        setDocumentIR(result.documentIR);
        setExportedFilePath(result.outputPath);

        // Record in recent documents shelf (UI-001)
        const newItem: RecentDocumentItem = {
          id: `rec-${Date.now()}`,
          timestamp: Date.now(),
          dateFormatted: new Date().toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          }),
          sourceName: selectedFile ? selectedFile.name : 'document',
          sourcePath: (selectedFile as any)?.nativePath,
          outputPath: result.outputPath,
          format: outputFormat,
          textSize,
          documentIR: result.documentIR,
        };
        const updated = [newItem, ...recentDocs.filter((d) => d.outputPath !== result.outputPath)].slice(0, 5);
        setRecentDocs(updated);
        saveRecentDocs(updated);

        if (result.reviewItems && result.reviewItems.length > 0) {
          setReviewItems(result.reviewItems);
          setViewMode('review');
        } else {
          setViewMode('reader');
        }
      },
    });
  };

  const handleCancelConversion = () => {
    sidecar.cancelConversion();
  };

  useKeyboardShortcuts({
    onConvert: () => {
      if (viewMode === 'home' && selectedFile) {
        handleStartConversion();
      }
    },
    onCancel: () => {
      if (viewMode === 'progress') {
        handleCancelConversion();
      }
    },
  });

  const handleAcceptReviewItem = (itemId: string, editedText?: string) => {
    setReviewItems((prev) =>
      prev.map((item) => {
        if (item.id === itemId) {
          return {
            ...item,
            status: 'accepted',
            converted_text: editedText !== undefined ? editedText : item.converted_text,
          };
        }
        return item;
      })
    );

    // Update the block in DocumentIR if edited
    if (documentIR && editedText !== undefined) {
      const item = reviewItems.find((i) => i.id === itemId);
      if (item && item.block_id) {
        setDocumentIR({
          ...documentIR,
          blocks: documentIR.blocks.map((b) =>
            b.id === item.block_id ? { ...b, text: editedText } : b
          ),
        });
      }
    }
  };

  const handleAcceptAllReviewItems = (currentId?: string, currentEditedText?: string) => {
    setReviewItems((prev) =>
      prev.map((item) => {
        if (item.id === currentId && currentEditedText !== undefined) {
          return {
            ...item,
            status: 'accepted',
            converted_text: currentEditedText,
          };
        }
        return {
          ...item,
          status: 'accepted',
        };
      })
    );

    if (documentIR && currentId && currentEditedText !== undefined) {
      const item = reviewItems.find((i) => i.id === currentId);
      if (item && item.block_id) {
        setDocumentIR({
          ...documentIR,
          blocks: documentIR.blocks.map((b) =>
            b.id === item.block_id ? { ...b, text: currentEditedText } : b
          ),
        });
      }
    }

    setViewMode('reader');
  };

  const handleRetryReviewItem = async (item: ReviewItem): Promise<string | null> => {
    const updated = await sidecar.retryPage(item.source_page, false);
    return updated?.text || null;
  };

  const handleFinishReview = () => {
    setViewMode('reader');
  };

  const handleExportReader = async (selection: {
    pages?: number[];
    fontPt: number;
    lineSpacing: number;
  }) => {
    if (!selectedFile) {
      return;
    }

    const targetOutputPath = getProposedExportPath();
    const settings: ConversionSettings = {
      textSize,
      customBodyPt: selection.fontPt,
      customLineSpacing: selection.lineSpacing,
      textEdits: Object.fromEntries((documentIR?.blocks || [])
        .filter((block) => typeof block.text === 'string' && block.block_type !== 'table' && block.block_type !== 'page_marker')
        .map((block) => [block.id, block.text as string])),
      paperSize,
      outputFormat,
      pageRange: selection.pages ? selection.pages.join(',') : '',
      monochrome,
      pageBreakOnSourcePage,
      outputPath: targetOutputPath,
    };

    const targetDocPath = (selectedFile as any)?.nativePath || selectedFile.name;
    setErrorMessage(null);

    // Preferred path: re-render from the already-built document (no re-extraction/OCR).
    const handled = await sidecar.exportFromIR(targetDocPath, settings, {
      onError: (err) => setErrorMessage(err),
      onSuccess: (result) => setExportedFilePath(result.outputPath),
    });
    if (handled) {
      return;
    }

    // Fallback (no desktop bridge, or the document is no longer loaded): full conversion.
    await sidecar.startConversion(targetDocPath, settings, {
      onProgress: () => {
        /* keep the reader visible while re-exporting */
      },
      onError: (err) => setErrorMessage(err),
      onCancelled: () => setErrorMessage(t('error.conversion_cancelled')),
      onSuccess: (result) => {
        // Only update the exported location; keep the full reader content intact.
        setExportedFilePath(result.outputPath);
      },
    });
  };

  return (
    <div className="app-container" dir={direction} lang={locale}>
      <a href="#main-content" className="skip-link">
        {t('app.skip_to_content')}
      </a>

      {/* Global Application Header */}
      <header className="app-header" role="banner">
        <div className="app-title-group" style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <img
            src="/logo.svg"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).src = '/logo.png';
            }}
            alt=""
            className="app-logo"
          />
          <div>
            <h1>{t('app.title')}</h1>
            <p>{t('app.subtitle')}</p>
          </div>
        </div>

        <div className="header-controls">
          <SettingsMenu theme={theme} onThemeChange={setTheme} />
        </div>
      </header>

      {/* Main Content Area */}
      <main id="main-content" tabIndex={-1}>
        {updateInfo && (
          <UpdateNotification
            updateInfo={updateInfo}
            onDismiss={() => setUpdateInfo(null)}
          />
        )}

        {errorMessage && (
          <div
            className="panel"
            style={{
              backgroundColor: 'var(--warning-bg)',
              borderColor: 'var(--warning-border)',
              color: 'var(--warning-text)',
              marginBottom: '20px',
              fontWeight: 600,
            }}
            role="alert"
          >
            {errorMessage}
          </div>
        )}

        {/* View Mode 1: Home Screen (UI-001, UI-006) */}
        {viewMode === 'home' && (
          <div className="panel">
            {/* Step 1: File selection */}
            <FilePicker
              selectedFile={selectedFile}
              onFileSelect={(file) => setSelectedFile(file)}
              onClear={() => {
                setSelectedFile(null);
                setCustomOutputPath(null);
              }}
            />

            {/* Step 2: Text size (OUT-006) */}
            <TextSizeSelector
              value={textSize}
              onChange={(size) => setTextSize(size)}
              customBodyPt={customBodyPt}
              onCustomBodyPtChange={setCustomBodyPt}
            />

            {/* Step 3: Format, paper and where it is saved, then convert (UI-001, UI-006) */}
            <section className="decision-step" aria-labelledby="step-3-label">
              <h2 id="step-3-label" className="step-label">3. {t('step3.label')}</h2>
              {!searchableOriginal && (
                <div className="choice-columns">
                  <DocumentTypeSelector value={mainFormat} onChange={setMainFormat} />
                  <PaperSizeSelector value={paperSize} onChange={(size) => setPaperSize(size)} />
                </div>
              )}
              {searchableOriginal && <p className="field-help">{t('export.searchable_active')}</p>}
              {selectedFile && (
                <SaveLocation
                  outputPath={getProposedExportPath()}
                  outputFormat={outputFormat}
                  isCustom={customOutputPath !== null}
                  onChoose={setCustomOutputPath}
                  onReset={() => setCustomOutputPath(null)}
                />
              )}
              <button
                type="button"
                className="primary-btn convert-btn"
                disabled={!selectedFile}
                onClick={handleStartConversion}
                aria-label={
                  selectedFile
                    ? t('convert.aria_ready', {
                        fileName: selectedFile.name,
                        textSize: String(customBodyPt ?? textSize),
                        paperSize,
                        format: t(`format.${mainFormat}`),
                      })
                    : t('convert.aria_no_file')
                }
              >
                {t('convert.button')}
              </button>
            </section>

            <AdvancedOptions
              pageRange={pageRange}
              onPageRangeChange={setPageRange}
              monochrome={monochrome}
              onMonochromeChange={setMonochrome}
              pageBreakOnSourcePage={pageBreakOnSourcePage}
              onPageBreakOnSourcePageChange={setPageBreakOnSourcePage}
              searchableOriginal={searchableOriginal}
              onSearchableOriginalChange={setSearchableOriginal}
            />

            {/* Recent Documents Shelf (UI-001) */}
            <RecentDocuments
              items={recentDocs}
              onOpenInReader={(ir, path) => {
                setDocumentIR(ir);
                setExportedFilePath(path);
                setViewMode('reader');
              }}
              onClearHistory={() => {
                setRecentDocs([]);
                localStorage.removeItem(RECENT_DOCS_KEY);
              }}
            />
          </div>
        )}

        {/* View Mode 2: Live Progress Reporting (UI-002) */}
        {viewMode === 'progress' && (
          <ProgressScreen
            progress={progress}
            fileName={selectedFile ? selectedFile.name : 'Document'}
            onCancel={handleCancelConversion}
          />
        )}

        {/* View Mode 3: Side-by-Side Review Screen (UI-004, UI-005) */}
        {viewMode === 'review' && (
          <ReviewScreen
            reviewItems={reviewItems}
            onAccept={handleAcceptReviewItem}
            onAcceptAll={handleAcceptAllReviewItems}
            onRetry={handleRetryReviewItem}
            onFinish={handleFinishReview}
          />
        )}

        {/* View Mode 4: In-App Reader (OUT-002) */}
        {viewMode === 'reader' && documentIR && (
          <ReaderView
            documentIR={documentIR}
            initialSize={customBodyPt ?? textSize}
            currentTheme={theme}
            exportedFilePath={exportedFilePath}
            onThemeChange={setTheme}
            onBack={() => setViewMode('home')}
            onExport={handleExportReader}
          />
        )}
      </main>
    </div>
  );
};
