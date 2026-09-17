import React, { useRef, useState } from 'react';

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

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files[0]);
    }
  };

  const triggerFileInput = () => {
    inputRef.current?.click();
  };

  const formatFileSize = (bytes: number): string => {
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
          <p className="dropzone-prompt">Drag a document here, or choose from your computer</p>
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
            <span className="file-meta">{formatFileSize(selectedFile.size)}</span>
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
