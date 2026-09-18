import React, { useEffect, useRef, useState } from 'react';
import { sidecar } from '../api/sidecarClient';

interface FilePickerProps {
  selectedFile: File | null;
  onFileSelect: (file: File) => void;
  onClear: () => void;
}

export const FilePicker: React.FC<FilePickerProps> = ({
  selectedFile,
  onFileSelect,
  onClear,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const win = typeof window !== 'undefined' ? (window as unknown as Record<string, any>) : undefined;
    if (!win?.__TAURI__?.event?.listen) {
      return;
    }

    let unlistenDrop: (() => void) | undefined;
    let unlistenEnter: (() => void) | undefined;
    let unlistenLeave: (() => void) | undefined;

    const setupTauriListeners = async () => {
      try {
        unlistenDrop = await win.__TAURI__.event.listen('tauri://drag-drop', async (event: any) => {
          setIsDragOver(false);
          const paths: string[] = event?.payload?.paths || [];
          if (paths.length > 0) {
            const rawPath = paths[0];
            const info = await sidecar.inspectFilePath(rawPath);
            if (info) {
              const fileObj = new File([''], info.name, { type: 'application/pdf' });
              (fileObj as any).nativePath = info.path;
              (fileObj as any).customSize = info.size;
              onFileSelect(fileObj);
            }
          }
        });

        unlistenEnter = await win.__TAURI__.event.listen('tauri://drag-enter', () => {
          setIsDragOver(true);
        });

        unlistenLeave = await win.__TAURI__.event.listen('tauri://drag-leave', () => {
          setIsDragOver(false);
        });
      } catch (e) {
        console.error('Failed to setup Tauri drag-drop listeners:', e);
      }
    };

    setupTauriListeners();

    return () => {
      if (unlistenDrop) unlistenDrop();
      if (unlistenEnter) unlistenEnter();
      if (unlistenLeave) unlistenLeave();
    };
  }, [onFileSelect]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const dropped = e.dataTransfer.files[0];
      const nativePath = (dropped as any).path || (dropped as any).nativePath;
      if (nativePath) {
        (dropped as any).nativePath = nativePath;
      }
      onFileSelect(dropped);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files[0]);
    }
  };

  const triggerFileInput = async () => {
    const nativeFile = await sidecar.openFileDialog();
    if (nativeFile) {
      const mockFile = new File([''], nativeFile.name, { type: 'application/pdf' });
      (mockFile as any).nativePath = nativeFile.path;
      (mockFile as any).customSize = nativeFile.size;
      onFileSelect(mockFile);
      return;
    }
    inputRef.current?.click();
  };

  const formatFileSize = (bytes: number): string => {
    if (!bytes || bytes <= 0) return '';
    if (bytes < 1024) return `${bytes} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    return `${mb.toFixed(1)} MB`;
  };

  return (
    <section className="decision-step" aria-labelledby="step-1-label">
      <h2 id="step-1-label" className="step-label">
        1. Choose document
      </h2>

      <input
        ref={inputRef}
        type="file"
        id="file-upload-input"
        accept=".pdf,.docx,.doc,.pptx,.ppt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation"
        onChange={handleFileChange}
        style={{ display: 'none' }}
        aria-label="Upload document file"
      />

      {!selectedFile ? (
        <div
          className={`dropzone ${isDragOver ? 'active' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={triggerFileInput}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              triggerFileInput();
            }
          }}
          tabIndex={0}
          role="button"
          aria-label="Drag and drop a PDF, Word, or PowerPoint document here, or press enter to browse files"
        >
          <svg
            width="40"
            height="40"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ marginBottom: '12px', opacity: 0.8 }}
            aria-hidden="true"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="12" y1="18" x2="12" y2="12" />
            <polyline points="9 15 12 12 15 15" />
          </svg>
          <p className="dropzone-prompt">
            {isDragOver ? 'Drop document here to load' : 'Drag a document here, or choose from your computer'}
          </p>
          <p className="dropzone-help">Supports PDF, Word (.docx), and PowerPoint (.pptx)</p>
          <button
            type="button"
            className="secondary-btn"
            onClick={(e) => {
              e.stopPropagation();
              triggerFileInput();
            }}
          >
            Browse files
          </button>
        </div>
      ) : (
        <div className="file-badge">
          <div className="file-info">
            <span className="file-name">{selectedFile.name}</span>
            <span className="file-meta">
              {(selectedFile as any).nativePath || formatFileSize((selectedFile as any).customSize || selectedFile.size)}
            </span>
          </div>
          <button
            type="button"
            className="secondary-btn"
            onClick={onClear}
            aria-label={`Remove selected file ${selectedFile.name}`}
          >
            Change document
          </button>
        </div>
      )}
    </section>
  );
};
