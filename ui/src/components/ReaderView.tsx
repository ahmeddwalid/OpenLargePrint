import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AppTheme, DocumentBlock, DocumentIR, InlineStyle } from '../types';
import { sidecar } from '../api/sidecarClient';
import { useI18n } from '../i18n/i18n';

interface ReaderViewProps {
  documentIR: DocumentIR;
  initialSize: number;
  currentTheme: AppTheme;
  exportedFilePath?: string | null;
  onThemeChange: (theme: AppTheme) => void;
  onBack: () => void;
  onExport: (selection: { pages?: number[]; fontPt: number; lineSpacing: number }) => void;
}

export type ReaderFont = 'system' | 'hyperlegible' | 'lexend' | 'mono';

const FONT_FAMILIES: Record<ReaderFont, string> = {
  system: 'var(--font-family)',
  hyperlegible: 'var(--font-family-arabic)',
  lexend: 'Georgia, serif',
  mono: 'Consolas, "Courier New", monospace',
};

const HighlightedText: React.FC<{
  text: string;
  searchQuery: string;
  isActiveMatch?: boolean;
}> = ({ text, searchQuery, isActiveMatch = false }) => {
  const trimmed = searchQuery.trim();
  if (!trimmed || trimmed.length < 2) {
    return <>{text}</>;
  }

  const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escaped})`, 'gi');
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, index) => {
        if (part.toLowerCase() === trimmed.toLowerCase()) {
          return (
            <mark
              key={index}
              className={isActiveMatch ? 'reader-search-highlight-active' : 'reader-search-highlight'}
            >
              {part}
            </mark>
          );
        }
        return <React.Fragment key={index}>{part}</React.Fragment>;
      })}
    </>
  );
};

const BLANK_TOKEN = '______';

/**
 * Block text with its emphasis (bold / italic / underline spans from the IR),
 * answer blanks drawn as lines, and search highlighting.
 */
const RichText: React.FC<{
  text: string;
  styles?: InlineStyle[];
  offset?: number;
  searchQuery: string;
  isActiveMatch?: boolean;
}> = ({ text, styles = [], offset = 0, searchQuery, isActiveMatch = false }) => {
  const cuts = new Set<number>([0, text.length]);
  for (const style of styles) {
    for (const edge of [style.start - offset, style.end - offset]) {
      if (edge > 0 && edge < text.length) cuts.add(edge);
    }
  }
  const edges = Array.from(cuts).sort((a, b) => a - b);
  const pieces: React.ReactNode[] = [];
  for (let i = 0; i < edges.length - 1; i++) {
    const start = edges[i];
    const end = edges[i + 1];
    const covering = styles.filter((st) => st.start - offset <= start && st.end - offset >= end);
    const parts = text.substring(start, end).split(BLANK_TOKEN);
    let node: React.ReactNode = parts.map((part, index) => (
      <React.Fragment key={index}>
        {index > 0 && <span className="reader-blank" role="img" aria-label="blank" />}
        <HighlightedText text={part} searchQuery={searchQuery} isActiveMatch={isActiveMatch} />
      </React.Fragment>
    ));
    if (covering.some((st) => st.underline)) node = <u>{node}</u>;
    if (covering.some((st) => st.italic)) node = <em>{node}</em>;
    if (covering.some((st) => st.bold)) node = <strong>{node}</strong>;
    pieces.push(<React.Fragment key={start}>{node}</React.Fragment>);
  }
  return <>{pieces}</>;
};

/** Plain-language note under a block that needs checking against the original. */
const BlockNote: React.FC<{ block: DocumentBlock }> = ({ block }) => {
  const warning = block.warnings?.[0];
  if (!warning) return null;
  return <p className="reader-note">{warning}</p>;
};

const HeadingBlock: React.FC<{
  id: string;
  level?: number;
  fontSize: number;
  text?: string;
  className?: string;
  searchQuery?: string;
  isActiveMatch?: boolean;
  styles?: InlineStyle[];
}> = ({ id, level = 1, fontSize, text = '', className, searchQuery = '', isActiveMatch = false, styles }) => {
  const boundedLevel = Math.min(6, Math.max(1, level));
  const style: React.CSSProperties = {
    marginTop: '1.2em',
    marginBottom: '0.6em',
    fontSize: `${fontSize / 12 * (boundedLevel === 1 ? 1.4 : 1.2)}rem`,
    fontWeight: 700,
  };
  const content = <RichText text={text} styles={styles} searchQuery={searchQuery} isActiveMatch={isActiveMatch} />;

  switch (boundedLevel) {
    case 1:
      return <h1 id={id} tabIndex={-1} className={className} style={style}>{content}</h1>;
    case 2:
      return <h2 id={id} tabIndex={-1} className={className} style={style}>{content}</h2>;
    case 3:
      return <h3 id={id} tabIndex={-1} className={className} style={style}>{content}</h3>;
    case 4:
      return <h4 id={id} tabIndex={-1} className={className} style={style}>{content}</h4>;
    case 5:
      return <h5 id={id} tabIndex={-1} className={className} style={style}>{content}</h5>;
    default:
      return <h6 id={id} tabIndex={-1} className={className} style={style}>{content}</h6>;
  }
};

export const ReaderView: React.FC<ReaderViewProps> = ({
  documentIR,
  initialSize,
  currentTheme,
  exportedFilePath,
  onThemeChange,
  onBack,
  onExport,
}) => {
  const { t } = useI18n();
  const [fontSize, setFontSize] = useState<number>(initialSize);
  const [lineHeight, setLineHeight] = useState<number>(1.6);
  const [readingWidth, setReadingWidth] = useState<number>(85);
  const [readerFont, setReaderFont] = useState<ReaderFont>('system');
  const [showRuler, setShowRuler] = useState<boolean>(false);
  const [rulerTop, setRulerTop] = useState<number>(180);
  const [selectedPageFilter, setSelectedPageFilter] = useState<number | 'all'>('all');

  // Outline / TOC state (OUT-002, UI-001)
  const [showOutline, setShowOutline] = useState<boolean>(false);

  // In-reader search state (A11Y-002, A11Y-003)
  const [showSearch, setShowSearch] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeMatchIndex, setActiveMatchIndex] = useState<number>(0);

  // Local Text-to-Speech (TTS) state (OUT-002, A11Y-002)
  const [ttsState, setTtsState] = useState<'idle' | 'playing' | 'paused'>('idle');
  const [speakingBlockId, setSpeakingBlockId] = useState<string | null>(null);
  const [speechRate, setSpeechRate] = useState<number>(1.0);
  const speakingIndexRef = useRef<number>(-1);

  // Keep the print stylesheet's base size in sync with the chosen size (OUT-009).
  useEffect(() => {
    document.documentElement.style.setProperty('--print-font-size', `${fontSize}pt`);
  }, [fontSize]);

  const handleZoomIn = () => {
    setFontSize((prev) => Math.min(36, prev + 2));
  };

  const handleZoomOut = () => {
    setFontSize((prev) => Math.max(14, prev - 2));
  };

  const printedPages = new Map((documentIR.pages || []).map((p) => [p.page_number, p.printed_page]));
  const pageLabel = (block: DocumentBlock): string => {
    const page = block.source_page ?? 0;
    const printed = printedPages.get(page);
    return printed && printed !== String(page)
      ? t('reader.page_marker_printed', { page, printed })
      : t('reader.page_marker', { page });
  };

  const filteredBlocks = selectedPageFilter === 'all'
    ? documentIR.blocks
    : documentIR.blocks.filter((b) => b.source_page === selectedPageFilter);

  const pages = Array.from(
    new Set(documentIR.blocks.map((b) => b.source_page).filter((p): p is number => p !== undefined))
  ).sort((a, b) => a - b);

  // Extract outline / TOC items from DocumentIR
  const outlineItems = documentIR.blocks.filter(
    (b) => (b.block_type === 'heading' && b.text) || b.block_type === 'page_marker'
  );

  // Search matching blocks
  const matchingBlocks = React.useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q || q.length < 2) {
      return [];
    }
    return filteredBlocks.filter(
      (b) => (b.text && b.text.toLowerCase().includes(q)) || (b.caption && b.caption.toLowerCase().includes(q))
    );
  }, [filteredBlocks, searchQuery]);

  const activeMatchBlock = matchingBlocks[activeMatchIndex] || null;

  // Jump to active search match
  const jumpToMatch = useCallback((index: number) => {
    if (matchingBlocks.length === 0) return;
    const bounded = (index + matchingBlocks.length) % matchingBlocks.length;
    setActiveMatchIndex(bounded);
    const targetBlock = matchingBlocks[bounded];
    if (targetBlock) {
      const el = document.getElementById(targetBlock.id);
      if (el) {
        el.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
        el.focus?.();
      }
    }
  }, [matchingBlocks]);

  // Global Ctrl+F / Cmd+F shortcut for in-reader search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        setShowSearch(true);
        setTimeout(() => {
          document.getElementById('reader-search-input')?.focus();
        }, 50);
      } else if (e.key === 'Escape') {
        if (showSearch) {
          setShowSearch(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showSearch]);

  // Readable text blocks for Text-to-Speech narration
  const readableBlocks = React.useMemo(() => {
    return filteredBlocks.filter(
      (b) => b.text && ['heading', 'paragraph', 'quote', 'list_item', 'footnote'].includes(b.block_type)
    );
  }, [filteredBlocks]);

  const stopSpeech = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setTtsState('idle');
    setSpeakingBlockId(null);
    speakingIndexRef.current = -1;
  }, []);

  const speakBlockAtIndex = useCallback((index: number) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }
    if (index < 0 || index >= readableBlocks.length) {
      stopSpeech();
      return;
    }

    speakingIndexRef.current = index;
    const currentBlock = readableBlocks[index];
    setSpeakingBlockId(currentBlock.id);

    const el = document.getElementById(currentBlock.id);
    if (el) {
      el.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(currentBlock.text || '');
    utterance.rate = speechRate;

    // Detect Arabic script to pick appropriate installed voice
    const hasArabic = /[\u0600-\u06FF]/.test(currentBlock.text || '');
    const voices = window.speechSynthesis.getVoices();
    const matchingVoice = voices.find((v) => (hasArabic ? v.lang.startsWith('ar') : v.lang.startsWith('en')));
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    utterance.onend = () => {
      speakBlockAtIndex(index + 1);
    };
    utterance.onerror = (e) => {
      if (e.error !== 'interrupted' && e.error !== 'canceled') {
        stopSpeech();
      }
    };

    window.speechSynthesis.speak(utterance);
    setTtsState('playing');
  }, [readableBlocks, speechRate, stopSpeech]);

  const handlePlayPauseSpeech = () => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }
    if (ttsState === 'playing') {
      window.speechSynthesis.pause();
      setTtsState('paused');
    } else if (ttsState === 'paused') {
      window.speechSynthesis.resume();
      setTtsState('playing');
    } else {
      speakBlockAtIndex(0);
    }
  };

  // Cleanup speech on unmount
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const handleJumpToOutline = (id: string, page?: number) => {
    if (selectedPageFilter !== 'all' && page !== undefined && selectedPageFilter !== page) {
      setSelectedPageFilter('all');
    }
    setTimeout(() => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
        el.focus?.();
      }
    }, 60);
  };

  return (
    <div
      className="reader-container"
      aria-label={t('reader.title_aria')}
      onMouseMove={(e) => {
        if (showRuler) {
          setRulerTop(e.clientY);
        }
      }}
    >
      {/* Export Success File Access Banner */}
      {exportedFilePath && (
        <aside
          aria-label="Exported file destination"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap',
            padding: '12px 18px',
            backgroundColor: 'var(--success-bg)',
            border: '1px solid var(--success-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--success-text)',
            fontSize: '0.9375rem',
            marginBottom: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
            <span style={{ fontWeight: 700, whiteSpace: 'nowrap' }}>{t('file.saved_file')}</span>
            <span
              style={{
                fontFamily: 'Consolas, monospace',
                fontSize: '0.8125rem',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                direction: 'ltr',
              }}
              title={exportedFilePath}
            >
              {exportedFilePath}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
            <button
              type="button"
              className="primary-btn"
              onClick={() => sidecar.openPathInSystem(exportedFilePath)}
              style={{ minHeight: '48px', padding: '6px 14px', fontSize: '0.875rem' }}
            >
              {t('file.open_file')}
            </button>
            <button
              type="button"
              className="secondary-btn"
              onClick={() => sidecar.revealInFolder(exportedFilePath)}
              style={{ minHeight: '48px', padding: '6px 14px', fontSize: '0.875rem' }}
            >
              {t('file.show_in_folder')}
            </button>
          </div>
        </aside>
      )}

      {/* Floating Reading Ruler Line Focus Guide A11Y-001, A11Y-003 */}
      {showRuler && (
        <div
          className="reading-ruler"
          style={{ top: `${rulerTop}px` }}
          aria-hidden="true"
        />
      )}

      {/* Reader Controls Toolbar OUT-002 */}
      <nav
        className="reader-toolbar"
        aria-label="Reader adjustment controls"
        style={{ flexWrap: 'wrap', gap: '12px' }}
      >
        <button
          type="button"
          className="secondary-btn"
          onClick={onBack}
          aria-label="Back to document options"
          style={{ minHeight: '48px' }}
        >
          {t('reader.back')}
        </button>

        {/* Contents / TOC Drawer Toggle */}
        {outlineItems.length > 0 && (
          <button
            type="button"
            className="secondary-btn"
            onClick={() => setShowOutline(!showOutline)}
            aria-expanded={showOutline}
            aria-controls="reader-outline-drawer"
            aria-label={t('reader.contents_aria')}
            style={{
              minHeight: '48px',
              backgroundColor: showOutline ? 'var(--accent-primary)' : undefined,
              color: showOutline ? 'var(--accent-text)' : undefined,
            }}
          >
            {t('reader.contents')}
          </button>
        )}

        {/* In-Reader Search Toggle */}
        <button
          type="button"
          className="secondary-btn"
          onClick={() => {
            const next = !showSearch;
            setShowSearch(next);
            if (next) {
              setTimeout(() => document.getElementById('reader-search-input')?.focus(), 50);
            }
          }}
          aria-expanded={showSearch}
          aria-controls="reader-search-toolbar"
          aria-label={t('reader.search')}
          style={{
            minHeight: '48px',
            backgroundColor: showSearch ? 'var(--accent-primary)' : undefined,
            color: showSearch ? 'var(--accent-text)' : undefined,
          }}
        >
          {t('reader.search')}
        </button>

        {/* Text-to-Speech (TTS) narration controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            type="button"
            className="secondary-btn"
            onClick={handlePlayPauseSpeech}
            aria-label={
              ttsState === 'playing'
                ? t('reader.tts_pause')
                : ttsState === 'paused'
                ? t('reader.tts_resume')
                : t('reader.tts_read')
            }
            style={{
              minHeight: '48px',
              backgroundColor: ttsState !== 'idle' ? 'var(--accent-primary)' : undefined,
              color: ttsState !== 'idle' ? 'var(--accent-text)' : undefined,
            }}
          >
            {ttsState === 'playing'
              ? t('reader.tts_pause')
              : ttsState === 'paused'
              ? t('reader.tts_resume')
              : t('reader.tts_read')}
          </button>

          {ttsState !== 'idle' && (
            <button
              type="button"
              className="secondary-btn"
              onClick={stopSpeech}
              aria-label={t('reader.tts_stop')}
              style={{ minHeight: '48px' }}
            >
              {t('reader.tts_stop')}
            </button>
          )}

          {ttsState !== 'idle' && (
            <select
              value={speechRate}
              onChange={(e) => setSpeechRate(parseFloat(e.target.value))}
              aria-label={t('reader.tts_speed')}
              style={{
                minHeight: '48px',
                padding: '6px 8px',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <option value="0.75">0.75x</option>
              <option value="1.0">1.0x</option>
              <option value="1.25">1.25x</option>
              <option value="1.5">1.5x</option>
            </select>
          )}
        </div>

        {/* Text Size Adjustment */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{t('reader.text_size')}</span>
          <button
            type="button"
            className="secondary-btn"
            onClick={handleZoomOut}
            aria-label={t('reader.zoom_out_aria')}
            style={{ minHeight: '48px', minWidth: '48px' }}
          >
            {t('reader.zoom_out')}
          </button>
          <span style={{ minWidth: '48px', textAlign: 'center', fontWeight: 700 }} aria-live="polite">
            {fontSize} pt
          </span>
          <button
            type="button"
            className="secondary-btn"
            onClick={handleZoomIn}
            aria-label={t('reader.zoom_in_aria')}
            style={{ minHeight: '48px', minWidth: '48px' }}
          >
            {t('reader.zoom_in')}
          </button>
        </div>

        {/* Font Family Selection */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="reader-font-select" style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
            {t('reader.font_label')}
          </label>
          <select
            id="reader-font-select"
            value={readerFont}
            onChange={(e) => setReaderFont(e.target.value as ReaderFont)}
            style={{
              minHeight: '48px',
              padding: '6px 10px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="system">Source Sans 3</option>
            <option value="hyperlegible">Noto Sans Arabic</option>
            <option value="lexend">Georgia</option>
            <option value="mono">Monospace</option>
          </select>
        </div>

        {/* Spacing Selection */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="line-spacing-select" style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
            {t('reader.spacing_label')}
          </label>
          <select
            id="line-spacing-select"
            value={lineHeight}
            onChange={(e) => setLineHeight(parseFloat(e.target.value))}
            style={{
              minHeight: '48px',
              padding: '6px 10px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="1.4">{t('reader.spacing_standard')}</option>
            <option value="1.6">{t('reader.spacing_comfortable')}</option>
            <option value="1.8">{t('reader.spacing_spacious')}</option>
            <option value="2.0">{t('reader.spacing_double')}</option>
          </select>
        </div>

        {/* Reading Width Selection */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="reading-width-select" style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
            Width:
          </label>
          <select
            id="reading-width-select"
            aria-label="Reading width"
            value={readingWidth}
            onChange={(e) => setReadingWidth(parseInt(e.target.value, 10))}
            style={{
              minHeight: '48px',
              padding: '6px 10px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="55">Narrow (55 ch)</option>
            <option value="70">Comfortable (70 ch)</option>
            <option value="85">Wide (85 ch)</option>
            <option value="110">Full width (110 ch)</option>
          </select>
        </div>

        {/* Theme Selection */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label htmlFor="theme-select" style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
            Theme:
          </label>
          <select
            id="theme-select"
            value={currentTheme}
            onChange={(e) => onThemeChange(e.target.value as AppTheme)}
            style={{
              minHeight: '48px',
              padding: '6px 10px',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="light">Light</option>
            <option value="auto">Auto (system)</option>
            <option value="sepia">Sepia</option>
            <option value="dark">Dark</option>
          </select>
        </div>

        {/* Reading ruler guide toggle */}
        <button
          type="button"
          className="secondary-btn"
          onClick={() => setShowRuler(!showRuler)}
          aria-pressed={showRuler}
          aria-label={t('reader.ruler_aria')}
          style={{
            minHeight: '48px',
            backgroundColor: showRuler ? 'var(--accent-primary)' : undefined,
            color: showRuler ? 'var(--accent-text)' : undefined,
          }}
        >
          {showRuler ? t('reader.ruler_on') : t('reader.ruler_off')}
        </button>

        {/* Direct print button */}
        <button
          type="button"
          className="secondary-btn"
          onClick={() => window.print()}
          aria-label={t('reader.print_aria')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', minHeight: '48px' }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <polyline points="6 9 6 2 18 2 18 9" />
            <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
            <rect x="6" y="14" width="12" height="8" />
          </svg>
          {t('reader.print')}
        </button>

        {pages.length > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label htmlFor="page-jump-select" style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
              {t('reader.page_label')}
            </label>
            <select
              id="page-jump-select"
              value={selectedPageFilter}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedPageFilter(val === 'all' ? 'all' : parseInt(val, 10));
              }}
              style={{
                minHeight: '48px',
                padding: '6px 10px',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <option value="all">{t('reader.all_pages', { count: String(pages.length) })}</option>
              {pages.map((p) => (
                <option key={p} value={p}>
                  Page {p}
                </option>
              ))}
            </select>
          </div>
        )}

        <button
          type="button"
          className="primary-btn"
          onClick={() => {
            onExport({
              pages: selectedPageFilter === 'all' ? undefined : [selectedPageFilter],
              fontPt: fontSize,
              lineSpacing: lineHeight,
            });
          }}
          aria-label="Export this view"
          style={{ minHeight: '48px' }}
        >
          {selectedPageFilter === 'all'
            ? t('reader.save_document')
            : t('reader.save_page', { page: String(selectedPageFilter) })}
        </button>
      </nav>

      {/* In-Reader High-Contrast Search Bar (A11Y-002, A11Y-003) */}
      {showSearch && (
        <div id="reader-search-toolbar" className="reader-search-toolbar" role="search" aria-label={t('reader.search')}>
          <input
            id="reader-search-input"
            type="search"
            className="reader-search-input"
            value={searchQuery}
            placeholder={t('reader.search_placeholder')}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setActiveMatchIndex(0);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                if (e.shiftKey) {
                  jumpToMatch(activeMatchIndex - 1);
                } else {
                  jumpToMatch(activeMatchIndex + 1);
                }
              }
            }}
            aria-label={t('reader.search_placeholder')}
          />

          <span className="reader-search-count" aria-live="polite">
            {searchQuery.trim().length >= 2
              ? matchingBlocks.length > 0
                ? t('reader.search_matches', {
                    current: String(activeMatchIndex + 1),
                    total: String(matchingBlocks.length),
                  })
                : t('reader.search_no_matches')
              : ''}
          </span>

          <button
            type="button"
            className="secondary-btn"
            disabled={matchingBlocks.length === 0}
            onClick={() => jumpToMatch(activeMatchIndex - 1)}
            aria-label={t('reader.search_prev')}
            style={{ minHeight: '44px', minWidth: '44px' }}
          >
            ↑
          </button>

          <button
            type="button"
            className="secondary-btn"
            disabled={matchingBlocks.length === 0}
            onClick={() => jumpToMatch(activeMatchIndex + 1)}
            aria-label={t('reader.search_next')}
            style={{ minHeight: '44px', minWidth: '44px' }}
          >
            ↓
          </button>

          <button
            type="button"
            className="secondary-btn"
            onClick={() => setShowSearch(false)}
            aria-label={t('reader.search_close')}
            style={{ minHeight: '44px' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Reader Layout Container (Outline Sidebar + Reading Body) */}
      <div className="reader-layout">
        {/* Document Outline / TOC Navigation Drawer */}
        {showOutline && (
          <aside
            id="reader-outline-drawer"
            className="reader-outline-drawer"
            role="navigation"
            aria-label={t('reader.contents_aria')}
          >
            <div className="reader-outline-header">
              <span className="reader-outline-title">{t('reader.contents')}</span>
              <button
                type="button"
                className="secondary-btn"
                onClick={() => setShowOutline(false)}
                aria-label="Close contents"
                style={{ minHeight: '36px', padding: '2px 8px', fontSize: '0.8125rem' }}
              >
                ✕
              </button>
            </div>
            <ul className="reader-outline-list">
              {outlineItems.map((item) => {
                const isHeading = item.block_type === 'heading';
                const level = item.heading_level || 1;
                const indent = isHeading ? `${(level - 1) * 12}px` : '4px';

                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="reader-outline-item-btn"
                      onClick={() => handleJumpToOutline(item.id, item.source_page)}
                      style={{ paddingLeft: indent }}
                    >
                      <span
                        style={{
                          fontWeight: isHeading && level <= 2 ? 700 : 400,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          maxWidth: '180px',
                        }}
                      >
                        {item.text || `Page ${item.source_page}`}
                      </span>
                      {item.source_page && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          p.{item.source_page}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </aside>
        )}

        {/* Reader Body Content */}
        <main
          className="reader-body"
          style={{
            fontSize: `${fontSize / 12}rem`,
            lineHeight: lineHeight,
            maxWidth: `${readingWidth}ch`,
            fontFamily: FONT_FAMILIES[readerFont],
          }}
          tabIndex={0}
          aria-label={t('reader.content_aria')}
        >
          {filteredBlocks.map((block: DocumentBlock) => {
            const isSpeaking = speakingBlockId === block.id;
            const isSearchMatch = activeMatchBlock?.id === block.id;
            const speakingClass = isSpeaking ? 'reader-block-speaking' : undefined;

            if (block.block_type === 'heading') {
              return (
                <HeadingBlock
                  key={block.id}
                  id={block.id}
                  level={block.heading_level}
                  fontSize={fontSize}
                  text={block.text}
                  styles={block.styles}
                  className={speakingClass}
                  searchQuery={searchQuery}
                  isActiveMatch={isSearchMatch}
                />
              );
            }

            if (block.block_type === 'table' && block.table_data) {
              return (
                <div
                  key={block.id}
                  id={block.id}
                  tabIndex={-1}
                  className={speakingClass}
                  style={{
                    overflowX: 'auto',
                    margin: '1.5em 0',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    {block.caption && (
                      <caption
                        style={{
                          textAlign: 'left',
                          padding: '8px',
                          fontWeight: 700,
                          backgroundColor: 'var(--bg-surface-raised)',
                        }}
                      >
                        <HighlightedText
                          text={block.caption}
                          searchQuery={searchQuery}
                          isActiveMatch={isSearchMatch}
                        />
                      </caption>
                    )}
                    <tbody>
                      {block.table_data.map((row, rIdx) => (
                        <tr
                          key={rIdx}
                          style={{
                            backgroundColor: rIdx === 0 ? 'var(--bg-surface-raised)' : 'transparent',
                            borderBottom: '1px solid var(--border-color)',
                          }}
                        >
                          {row.map((cell, cIdx) =>
                            rIdx === 0 ? (
                              <th
                                key={cIdx}
                                style={{
                                  padding: '12px 16px',
                                  textAlign: 'left',
                                  borderRight: '1px solid var(--border-color)',
                                  fontWeight: 700,
                                }}
                              >
                                <HighlightedText
                                  text={cell}
                                  searchQuery={searchQuery}
                                  isActiveMatch={isSearchMatch}
                                />
                              </th>
                            ) : (
                              <td
                                key={cIdx}
                                style={{
                                  padding: '12px 16px',
                                  textAlign: 'left',
                                  borderRight: '1px solid var(--border-color)',
                                  fontWeight: 400,
                                }}
                              >
                                <HighlightedText
                                  text={cell}
                                  searchQuery={searchQuery}
                                  isActiveMatch={isSearchMatch}
                                />
                              </td>
                            )
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            }

            // Source page transition marker (OUT-005)
            if (block.block_type === 'page_marker') {
              return (
                <div
                  key={block.id}
                  id={block.id}
                  tabIndex={-1}
                  role="separator"
                  aria-label={pageLabel(block)}
                  className={speakingClass}
                  style={{
                    margin: '2em 0 1.2em 0',
                    padding: '8px 16px',
                    border: '1px dashed var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    textAlign: 'center',
                    fontSize: '0.8em',
                    fontWeight: 700,
                    color: 'var(--text-muted)',
                  }}
                >
                  {pageLabel(block)}
                </div>
              );
            }

            // Figures / images (IMG-001)
            if (block.block_type === 'figure') {
              const src = block.image_asset?.data_url;
              if (!src) {
                return null;
              }
              return (
                <figure
                  key={block.id}
                  id={block.id}
                  tabIndex={-1}
                  className={speakingClass}
                  style={{ margin: '1.5em 0', textAlign: 'center' }}
                >
                  <img
                    src={src}
                    alt={block.image_asset?.alt_text || `Figure from page ${block.source_page}`}
                    style={{
                      maxWidth: '100%',
                      height: 'auto',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  />
                  {block.caption && (
                    <figcaption
                      style={{
                        fontSize: '0.85em',
                        fontStyle: 'italic',
                        color: 'var(--text-muted)',
                        marginTop: '6px',
                      }}
                    >
                      <HighlightedText
                        text={block.caption}
                        searchQuery={searchQuery}
                        isActiveMatch={isSearchMatch}
                      />
                    </figcaption>
                  )}
                  <BlockNote block={block} />
                </figure>
              );
            }

            // Footnotes (FN-001)
            if (block.block_type === 'footnote') {
              return (
                <aside
                  key={block.id}
                  id={block.id}
                  tabIndex={-1}
                  role="doc-footnote"
                  className={speakingClass}
                  style={{
                    fontSize: '0.85em',
                    fontStyle: 'italic',
                    color: 'var(--text-muted)',
                    borderTop: '1px solid var(--border-color)',
                    paddingTop: '8px',
                    marginTop: '1.5em',
                    marginBottom: '1em',
                  }}
                >
                  <RichText
                    text={block.text || ''}
                    styles={block.styles}
                    searchQuery={searchQuery}
                    isActiveMatch={isSearchMatch}
                  />
                </aside>
              );
            }

            // Boxed notes and page notes (ASIDE)
            if (block.block_type === 'aside') {
              return (
                <div
                  key={block.id}
                  id={block.id}
                  tabIndex={-1}
                  className={[block.role === 'page_note' ? 'reader-note' : 'reader-aside', speakingClass].filter(Boolean).join(' ')}
                >
                  <RichText
                    text={block.text || ''}
                    styles={block.styles}
                    searchQuery={searchQuery}
                    isActiveMatch={isSearchMatch}
                  />
                </div>
              );
            }

            // Captions
            if (block.block_type === 'caption') {
              return (
                <div
                  key={block.id}
                  id={block.id}
                  tabIndex={-1}
                  className={speakingClass}
                  style={{
                    fontStyle: 'italic',
                    fontSize: '0.9em',
                    color: 'var(--text-secondary)',
                    margin: '6px 0 1em 0',
                  }}
                >
                  {block.role === 'figure_text' && <strong>{t('reader.in_picture')} </strong>}
                  <RichText
                    text={block.text || ''}
                    styles={block.styles}
                    searchQuery={searchQuery}
                    isActiveMatch={isSearchMatch}
                  />
                </div>
              );
            }

            // Quotes
            if (block.block_type === 'quote') {
              return (
                <blockquote
                  key={block.id}
                  id={block.id}
                  tabIndex={-1}
                  className={speakingClass}
                  style={{
                    borderLeft: '4px solid var(--border-color)',
                    paddingLeft: '16px',
                    margin: '1em 0',
                    fontStyle: 'italic',
                    color: 'var(--text-muted)',
                  }}
                >
                  <RichText
                    text={block.text || ''}
                    styles={block.styles}
                    searchQuery={searchQuery}
                    isActiveMatch={isSearchMatch}
                  />
                </blockquote>
              );
            }

            // List items keep the source's own marker ("1", "a)", "A:"), with a hanging indent.
            if (block.block_type === 'list_item') {
              const text = block.text || '';
              const marker = block.list_marker && text.startsWith(block.list_marker) ? block.list_marker : null;
              const rest = marker ? text.substring(marker.length).replace(/^\s+/, '') : text;
              const offset = text.length - rest.length;
              return (
                <div
                  key={block.id}
                  id={block.id}
                  tabIndex={-1}
                  className={['reader-item', block.role === 'dialogue' ? 'dialogue' : '', speakingClass].filter(Boolean).join(' ')}
                  style={{ marginInlineStart: `${Math.min(4, block.indent_level || 0) * 1.6}em` }}
                >
                  <span className="reader-item-marker">{marker ?? ''}</span>
                  <span>
                    <RichText
                      text={rest}
                      styles={block.styles}
                      offset={offset}
                      searchQuery={searchQuery}
                      isActiveMatch={isSearchMatch}
                    />
                    <BlockNote block={block} />
                  </span>
                </div>
              );
            }

            return (
              <p
                key={block.id}
                id={block.id}
                tabIndex={-1}
                className={speakingClass}
                style={{ marginBottom: '1em', whiteSpace: 'pre-line' }}
              >
                <RichText
                  text={block.text || ''}
                  styles={block.styles}
                  searchQuery={searchQuery}
                  isActiveMatch={isSearchMatch}
                />
                <BlockNote block={block} />
              </p>
            );
          })}
        </main>
      </div>
    </div>
  );
};
