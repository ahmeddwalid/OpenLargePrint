/**
 * Type definitions for OpenLargePrint Web/Desktop UI.
 * Adheres to SPEC.md (UI-001..006, A11Y-001..005, OUT-002..011) and DESIGN.md §2, §9.
 */

export type TextSize = 18 | 20 | 24 | 28;
export type PaperSize = 'A4' | 'A3';
export type OutputFormat = 'pdf' | 'docx' | 'html' | 'searchable_pdf';
export type RoutingMode = 'auto' | 'native_only' | 'ocr_scanned_only' | 'max_accuracy';
export type AppTheme = 'auto' | 'light' | 'sepia' | 'dark';

export interface ImageAsset {
  asset_id?: string;
  file_path?: string;
  data_url?: string;
  mime_type?: string;
  width?: number;
  height?: number;
  alt_text?: string;
}

export interface DocumentBlock {
  id: string;
  block_type: 'heading' | 'paragraph' | 'list_item' | 'table' | 'figure' | 'caption' | 'quote' | 'page_marker' | 'code' | 'page_header' | 'page_footer' | 'footnote' | 'marginalia' | 'toc_entry' | 'decorative';
  text?: string;
  source_page?: number;
  bbox?: [number, number, number, number];
  heading_level?: number;
  table_data?: string[][];
  caption?: string;
  image_asset?: ImageAsset;
  warnings?: string[];
  reading_order_index?: number;
  confidence?: number;
}

export interface DocumentIR {
  schema_version: string;
  source_file: string;
  source_mime: string;
  page_count: number;
  blocks: DocumentBlock[];
  warnings?: string[];
  reading_order?: string[];
}

export interface ReviewItem {
  id: string;
  source_page: number;
  block_id?: string;
  reason: string;
  original_snippet: string;
  original_preview?: string;
  converted_text: string;
  status: 'pending' | 'accepted' | 'retried';
}

export interface ConversionSettings {
  textSize: TextSize;
  customBodyPt?: number | null;
  customLineSpacing?: number;
  textEdits?: Record<string, string>;
  paperSize: PaperSize;
  outputFormat: OutputFormat;
  routingMode: RoutingMode;
  pageRange: string;
  outputPath?: string;
  monochrome?: boolean;
}

export interface ProgressInfo {
  currentPage: number;
  totalPages: number;
  stage: string;
  humanMessage: string;
  percent: number;
}

export interface InspectResult {
  filePath: string;
  mimeType: string;
  pageCount: number;
  detectedType: 'native_pdf' | 'scanned_pdf' | 'docx' | 'pptx' | 'unknown';
  estimatedDurationSeconds?: number;
}
