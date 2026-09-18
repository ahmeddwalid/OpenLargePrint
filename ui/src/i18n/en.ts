/**
 * English string table for OpenLargePrint UI.
 * All user-facing text must live here for i18n support (A11Y-005, LANG-001).
 */

const en: Record<string, string> = {
  // App header
  'app.title': 'OpenLargePrint',
  'app.subtitle': 'Accessible document enlargement for low vision',
  'app.skip_to_content': 'Skip to main content',

  // Theme selector
  'theme.label': 'Theme:',
  'theme.light': 'Light (Default)',
  'theme.auto': 'Auto (follow system)',
  'theme.sepia': 'Sepia',
  'theme.dark': 'Dark',

  // Direction toggle
  'dir.toggle_to_rtl': 'Switch layout reading direction to Right-to-Left',
  'dir.toggle_to_ltr': 'Switch layout reading direction to Left-to-Right',
  'dir.rtl_label': 'RTL',
  'dir.ltr_label': 'LTR',

  // Language selector
  'lang.label': 'Language:',
  'lang.en': 'English',
  'lang.ar': 'العربية',

  // File picker
  'file.step_label': 'Choose a document',
  'file.dropzone_prompt': 'Drop a file here, or click to browse',
  'file.dropzone_help': 'Supported: PDF, DOCX, PPTX, DOC, PPT',
  'file.browse_button': 'Browse files',
  'file.clear_button': 'Remove',
  'file.size_label': 'Size:',

  // Text size selector
  'textsize.step_label': 'Text size',
  'textsize.comfortable': 'Comfortable',
  'textsize.comfortable_detail': '18 pt',
  'textsize.large': 'Large',
  'textsize.large_detail': '20 pt (default)',
  'textsize.extra_large': 'Extra Large',
  'textsize.extra_large_detail': '24 pt',
  'textsize.very_large': 'Very Large',
  'textsize.very_large_detail': '28 pt',

  // Paper size selector
  'paper.step_label': 'Paper size',
  'paper.a4': 'A4',
  'paper.a4_detail': '210 × 297 mm (default)',
  'paper.a3': 'A3',
  'paper.a3_detail': '297 × 420 mm',

  // Output format selector
  'format.step_label': 'Output format',
  'format.pdf': 'PDF',
  'format.pdf_detail': 'Print-ready document',
  'format.docx': 'Word',
  'format.docx_detail': 'Editable document',
  'format.html': 'Reader',
  'format.html_detail': 'View in app',

  // Export location
  'export.step_label': 'Save to',
  'export.downloads': 'Downloads',
  'export.desktop': 'Desktop',
  'export.source': 'Same folder as original',
  'export.custom': 'Choose location...',
  'export.output_path': 'Output file:',

  // Convert button
  'convert.button': 'Convert to Large Print',
  'convert.aria_ready': 'Convert {fileName} to {textSize} point large print on {paperSize} paper as {format}',
  'convert.aria_no_file': 'Choose a document first to convert',

  // Advanced options
  'advanced.toggle': 'More options',
  'advanced.routing_label': 'Processing mode',
  'advanced.routing_auto': 'Automatic',
  'advanced.routing_native': 'Native text only',
  'advanced.routing_ocr': 'OCR scanned only',
  'advanced.routing_max': 'Maximum accuracy',
  'advanced.page_range_label': 'Page range',
  'advanced.page_range_placeholder': 'e.g. 1-10, 15, 20-30',

  // Progress screen
  'progress.starting': 'Inspecting document and preparing conversion...',
  'progress.cancel': 'Cancel',

  // Review screen
  'review.banner': '{count} pages may need review',
  'review.original_pane': 'ORIGINAL',
  'review.converted_pane': 'CONVERTED',
  'review.accept': 'Accept',
  'review.retry': 'Retry at higher accuracy',
  'review.finish': 'Continue to Reader',

  // Reader view
  'reader.back': '← Back',
  'reader.text_size': 'Text Size:',
  'reader.zoom_out': 'A-',
  'reader.zoom_out_aria': 'Decrease text size',
  'reader.zoom_in': 'A+',
  'reader.zoom_in_aria': 'Increase text size',
  'reader.font_label': 'Font:',
  'reader.font_system': 'System Clean',
  'reader.font_hyperlegible': 'Atkinson Hyperlegible',
  'reader.font_lexend': 'Lexend',
  'reader.font_mono': 'Monospace',
  'reader.spacing_label': 'Spacing:',
  'reader.spacing_standard': '1.4x (Standard)',
  'reader.spacing_comfortable': '1.6x (Comfortable)',
  'reader.spacing_spacious': '1.8x (Spacious)',
  'reader.spacing_double': '2.0x (Double)',
  'reader.ruler_on': 'Line guide On',
  'reader.ruler_off': 'Line guide Off',
  'reader.ruler_aria': 'Toggle horizontal line guide',
  'reader.print': 'Print...',
  'reader.print_aria': 'Directly print this large-print document using system printer',
  'reader.page_label': 'Page:',
  'reader.all_pages': 'All Pages ({count})',
  'reader.save_document': 'Save Document',
  'reader.save_page': 'Save Page {page}',
  'reader.content_aria': 'Document Content',
  'reader.title_aria': 'Large-Print Reader',

  // Recent documents
  'recent.title': 'Recent documents',
  'recent.clear': 'Clear history',
  'recent.open_reader': 'Open in Reader',
  'recent.empty': 'No recent conversions',

  // Errors
  'error.conversion_cancelled': 'Conversion was cancelled.',
  'error.unsupported_type': 'This file type is not supported.',

  // File actions
  'file.open_file': 'Open File',
  'file.show_in_folder': 'Show in Folder',
  'file.saved_file': 'Saved file:',
};

export default en;
