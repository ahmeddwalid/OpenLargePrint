import React, { useEffect, useState } from 'react';
import { AdvancedOptions } from './components/AdvancedOptions';
import { DocumentTypeSelector } from './components/DocumentTypeSelector';
import { ExportLocationPicker, LocationPreset } from './components/ExportLocationPicker';
import { FilePicker } from './components/FilePicker';
import { PaperSizeSelector } from './components/PaperSizeSelector';
import { ProgressScreen } from './components/ProgressScreen';
import { ReaderView } from './components/ReaderView';
import { RecentDocuments, RecentDocumentItem } from './components/RecentDocuments';
import { ReviewScreen } from './components/ReviewScreen';
import { TextSizeSelector } from './components/TextSizeSelector';
import { UpdateNotification } from './components/UpdateNotification';
import { sidecar } from './api/sidecarClient';
import { UpdateInfo, checkForUpdates, isUpdateDismissed } from './api/update-checker';
import { useI18n, Locale } from './i18n/i18n';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import {
  AppTheme,
  ConversionSettings,
  DocumentIR,
  OutputFormat,
  PaperSize,
  ProgressInfo,
  ReviewItem,
  RoutingMode,
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
  const { t, locale, direction, setLocale } = useI18n();

  // Theme State (A11Y-004)
  const [theme, setTheme] = useState<AppTheme>(() => {
    const saved = localStorage.getItem('openlargeprint_theme');
    if (saved === 'auto' || saved === 'light' || saved === 'sepia' || saved === 'dark') {
      return saved;
    }
    return 'sepia';
  });

  // Document Selection & Settings State (UI-001, UI-006)
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [textSize, setTextSize] = useState<TextSize>(20); // 20pt default per OUT-006
  const [paperSize, setPaperSize] = useState<PaperSize>('A4'); // A4 default per UI-006
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('pdf');
  const [locationPreset, setLocationPreset] = useState<LocationPreset>('downloads');
  const [customOutputPath, setCustomOutputPath] = useState<string | null>(null);
  const [systemPaths, setSystemPaths] = useState<{ downloads: string; desktop: string; documents: string } | null>(null);
  const [routingMode, setRoutingMode] = useState<RoutingMode>('max_accuracy');
  const [pageRange, setPageRange] = useState<string>('');
  const [monochrome, setMonochrome] = useState<boolean>(false);

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

  // Fetch native desktop system paths (Downloads, Desktop, Documents)
  useEffect(() => {
    sidecar.getSystemPaths().then((paths) => {
      setSystemPaths(paths);
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

  const getProposedExportPath = (): string => {
    const ext = outputFormat === 'docx' ? 'docx' : outputFormat === 'html' ? 'html' : 'pdf';

    if (locationPreset === 'custom' && customOutputPath) {
      const lastDot = customOutputPath.lastIndexOf('.');
      if (lastDot > 0) {
        return `${customOutputPath.substring(0, lastDot)}.${ext}`;
      }
      return `${customOutputPath}.${ext}`;
    }

    const docName = selectedFile ? selectedFile.name : 'document';
    const lastDot = docName.lastIndexOf('.');
    const stem = lastDot > 0 ? docName.substring(0, lastDot) : docName;
    const targetFileName = `${stem}-largeprint.${ext}`;

    const nativePath = (selectedFile as any)?.nativePath;
    const isWindows = typeof window !== 'undefined' && (Boolean(systemPaths?.downloads?.includes('\\')) || (nativePath && nativePath.includes('\\')));
    const separator = isWindows ? '\\' : '/';

    if (locationPreset === 'downloads' && systemPaths?.downloads) {
      return `${systemPaths.downloads}${separator}${targetFileName}`;
    }

    if (locationPreset === 'desktop' && systemPaths?.desktop) {
      return `${systemPaths.desktop}${separator}${targetFileName}`;
    }

    if (locationPreset === 'source' && nativePath) {
      const parts = nativePath.split(separator);
      parts.pop();
      const parentDir = parts.join(separator);
      return `${parentDir}${separator}${targetFileName}`;
    }

    // Default fallback to Downloads if available
    if (systemPaths?.downloads) {
      return `${systemPaths.downloads}${separator}${targetFileName}`;
    }
    return targetFileName;
  };

  const handleFormatChange = (newFormat: OutputFormat) => {
    setOutputFormat(newFormat);
    if (customOutputPath) {
      const ext = newFormat === 'docx' ? 'docx' : newFormat === 'html' ? 'html' : 'pdf';
      const lastDot = customOutputPath.lastIndexOf('.');
      if (lastDot > 0) {
        setCustomOutputPath(`${customOutputPath.substring(0, lastDot)}.${ext}`);
      }
    }
  };

  const handleStartConversion = async () => {
    if (!selectedFile) return;

    setErrorMessage(null);
    setViewMode('progress');
    setProgress({
      currentPage: 0,
      totalPages: 0,
      stage: 'starting',
      humanMessage: 'Inspecting document and preparing conversion...',
      percent: 0,
    });

    const targetOutputPath = customOutputPath || getProposedExportPath();
    const settings: ConversionSettings = {
      textSize,
      paperSize,
      outputFormat,
      routingMode,
      pageRange,
      monochrome,
      outputPath: targetOutputPath,
    };

    const targetDocPath = (selectedFile as any)?.nativePath || selectedFile.name;
    await sidecar.startConversion(targetDocPath, settings, {
      onProgress: (p) => {
        setProgress(p);
      },
      onCheckpoint: (page, count) => {
        console.log(`Checkpoint saved: page ${page} with ${count} blocks`);
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

  const handleRetryReviewItem = async (item: ReviewItem) => {
    const updated = await sidecar.retryPage(item.source_page, true);
    if (updated.blocks.length > 0) {
      const newText = updated.blocks[0].text || '';
      handleAcceptReviewItem(item.id, newText);
    }
  };

  const handleFinishReview = () => {
    setViewMode('reader');
  };

  const handleExportReader = (selectedPagesOnly?: number[]) => {
    const targetDesc = selectedPagesOnly
      ? `pages ${selectedPagesOnly.join(', ')}`
      : 'the complete document';
    alert(
      `Ready to print or save ${targetDesc} at ${textSize}pt on ${paperSize} paper.\nFile: ${
        exportedFilePath || 'output.pdf'
      }`
    );
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
            alt="OpenLargePrint Logo"
            style={{ width: '48px', height: '48px', borderRadius: '8px', objectFit: 'contain' }}
          />
          <div>
            <h1>{t('app.title')}</h1>
            <p>{t('app.subtitle')}</p>
          </div>
        </div>

        <div className="header-controls">
          <label htmlFor="global-theme-toggle" style={{ fontSize: '15px', fontWeight: 600 }}>
            {t('theme.label')}
          </label>
          <select
            id="global-theme-toggle"
            value={theme}
            onChange={(e) => setTheme(e.target.value as AppTheme)}
            style={{
              padding: '6px 12px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="light">{t('theme.light')}</option>
            <option value="auto">{t('theme.auto')}</option>
            <option value="sepia">{t('theme.sepia')}</option>
            <option value="dark">{t('theme.dark')}</option>
          </select>

          <label htmlFor="global-lang-select" style={{ fontSize: '15px', fontWeight: 600 }}>
            {t('lang.label')}
          </label>
          <select
            id="global-lang-select"
            value={locale}
            onChange={(e) => setLocale(e.target.value as Locale)}
            style={{
              padding: '6px 12px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="en">{t('lang.en')}</option>
            <option value="ar">{t('lang.ar')}</option>
          </select>
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

            {/* Step 2: Font size selection (OUT-006) */}
            <TextSizeSelector value={textSize} onChange={(size) => setTextSize(size)} />

            {/* Step 2.5: Direct choice of A4 vs A3 paper size (UI-006) */}
            <PaperSizeSelector value={paperSize} onChange={(size) => setPaperSize(size)} />

            {/* Step 3: Export Format Selector (Default: PDF) */}
            <DocumentTypeSelector
              value={outputFormat}
              onChange={handleFormatChange}
            />

            {/* Step 4: Export Location Picker */}
            <ExportLocationPicker
              outputPath={getProposedExportPath()}
              defaultFileName={selectedFile ? selectedFile.name : 'document'}
              outputFormat={outputFormat}
              preset={locationPreset}
              onPresetChange={(newPreset) => {
                setLocationPreset(newPreset);
                if (newPreset !== 'custom') {
                  setCustomOutputPath(null);
                }
              }}
              onCustomPathSelected={(chosenPath) => {
                setCustomOutputPath(chosenPath);
                setLocationPreset('custom');
              }}
            />

            {/* Step 5: Convert Action */}
            <div style={{ marginTop: '28px', display: 'flex', alignItems: 'center', gap: '16px' }}>
              <button
                type="button"
                className="primary-btn"
                disabled={!selectedFile}
                onClick={handleStartConversion}
                aria-label={
                  selectedFile
                    ? t('convert.aria_ready', {
                        fileName: selectedFile.name,
                        textSize: String(textSize),
                        paperSize,
                        format: outputFormat.toUpperCase(),
                      })
                    : t('convert.aria_no_file')
                }
              >
                {t('convert.button')}
              </button>
            </div>

            {/* Collapsible Disclosure for Advanced Settings (UI-001) */}
            <AdvancedOptions
              routingMode={routingMode}
              onRoutingModeChange={setRoutingMode}
              pageRange={pageRange}
              onPageRangeChange={setPageRange}
              monochrome={monochrome}
              onMonochromeChange={setMonochrome}
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
            onRetry={handleRetryReviewItem}
            onFinish={handleFinishReview}
          />
        )}

        {/* View Mode 4: In-App Reader (OUT-002) */}
        {viewMode === 'reader' && documentIR && (
          <ReaderView
            documentIR={documentIR}
            initialSize={textSize}
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
