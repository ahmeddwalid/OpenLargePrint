import React, { useEffect, useState } from 'react';
import { AdvancedOptions } from './components/AdvancedOptions';
import { FilePicker } from './components/FilePicker';
import { PaperSizeSelector } from './components/PaperSizeSelector';
import { ProgressScreen } from './components/ProgressScreen';
import { ReaderView } from './components/ReaderView';
import { ReviewScreen } from './components/ReviewScreen';
import { TextSizeSelector } from './components/TextSizeSelector';
import { sidecar } from './api/sidecarClient';
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

export const App: React.FC = () => {
  // Theme and Direction State
  const [theme, setTheme] = useState<AppTheme>('light');
  const [direction, setDirection] = useState<'ltr' | 'rtl'>('ltr');

  // Document Selection & Settings State (UI-001, UI-006)
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [textSize, setTextSize] = useState<TextSize>(20); // 20pt default per OUT-006
  const [paperSize, setPaperSize] = useState<PaperSize>('A4'); // A4 default per UI-006
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('pdf');
  const [routingMode, setRoutingMode] = useState<RoutingMode>('max_accuracy');
  const [pageRange, setPageRange] = useState<string>('');

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

  // Synchronize theme to document element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Synchronize reading direction
  useEffect(() => {
    document.documentElement.setAttribute('dir', direction);
  }, [direction]);

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

    const settings: ConversionSettings = {
      textSize,
      paperSize,
      outputFormat,
      routingMode,
      pageRange,
    };

    await sidecar.startConversion(selectedFile.name, settings, {
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
        setErrorMessage('Conversion was cancelled.');
        setViewMode('home');
      },
      onSuccess: (result) => {
        setDocumentIR(result.documentIR);
        setExportedFilePath(result.outputPath);
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
    <div className="app-container">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* Global Application Header */}
      <header className="app-header" role="banner">
        <div className="app-title-group">
          <h1>OpenLargePrint</h1>
          <p>Accessible document enlargement for low vision</p>
        </div>

        <div className="header-controls">
          <label htmlFor="global-theme-toggle" style={{ fontSize: '15px', fontWeight: 600 }}>
            Contrast:
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
            <option value="light">Warm Parchment</option>
            <option value="sepia">Sepia Book</option>
            <option value="dark">High-Contrast Dark</option>
          </select>

          <button
            type="button"
            className="secondary-btn"
            onClick={() => setDirection((prev) => (prev === 'ltr' ? 'rtl' : 'ltr'))}
            aria-label={`Switch layout reading direction to ${direction === 'ltr' ? 'Right-to-Left' : 'Left-to-Right'}`}
            style={{ minHeight: '38px', padding: '6px 12px', fontSize: '14px' }}
          >
            {direction === 'ltr' ? 'RTL' : 'LTR'}
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main id="main-content" tabIndex={-1}>
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
              onClear={() => setSelectedFile(null)}
            />

            {/* Step 2: Font size selection (OUT-006) */}
            <TextSizeSelector value={textSize} onChange={(size) => setTextSize(size)} />

            {/* Step 2.5: Direct choice of A4 vs A3 paper size (UI-006) */}
            <PaperSizeSelector value={paperSize} onChange={(size) => setPaperSize(size)} />

            {/* Step 3: Convert Action */}
            <div style={{ marginTop: '28px', display: 'flex', alignItems: 'center', gap: '16px' }}>
              <button
                type="button"
                className="primary-btn"
                disabled={!selectedFile}
                onClick={handleStartConversion}
                aria-label={
                  selectedFile
                    ? `Convert ${selectedFile.name} to ${textSize} point large print on ${paperSize} paper`
                    : 'Choose a document first to convert'
                }
              >
                Convert to Large Print
              </button>
            </div>

            {/* Collapsible Disclosure for Advanced Settings (UI-001) */}
            <AdvancedOptions
              format={outputFormat}
              onFormatChange={setOutputFormat}
              routingMode={routingMode}
              onRoutingModeChange={setRoutingMode}
              pageRange={pageRange}
              onPageRangeChange={setPageRange}
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
            onThemeChange={setTheme}
            onBack={() => setViewMode('home')}
            onExport={handleExportReader}
          />
        )}
      </main>
    </div>
  );
};
