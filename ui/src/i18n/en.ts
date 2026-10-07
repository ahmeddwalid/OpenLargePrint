/**
 * English string table for OpenLargePrint UI.
 * All user-facing text must live here for i18n support (A11Y-005, LANG-001).
 */

const en: Record<string, string> = {
  // App header
  'app.title': 'OpenLargePrint',
  'app.subtitle': 'Accessible document enlargement',
  'app.skip_to_content': 'Skip to main content',

  // Theme selector
  'theme.label': 'Colours',
  'theme.sepia': 'Warm paper (default)',
  'theme.light': 'Light',
  'theme.auto': 'Follow the computer',
  'theme.dark': 'Dark',

  // Direction toggle

  // Language selector
  'lang.label': 'Language',
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
  'textsize.step_label': 'Choose text size',
  'textsize.comfortable': 'Comfortable',
  'textsize.comfortable_detail': '18 pt',
  'textsize.large': 'Large',
  'textsize.large_detail': '20 pt (default)',
  'textsize.extra_large': 'Extra Large',
  'textsize.extra_large_detail': '24 pt',
  'textsize.very_large': 'Very Large',
  'textsize.very_large_detail': '28 pt',

  // Paper size selector
  'paper.step_label': 'Paper',
  'paper.a4': 'A4',
  'paper.a4_detail': 'Standard paper (default)',
  'paper.a3': 'A3',
  'paper.a3_detail': 'Twice the size, for wide tables',

  // Output format selector
  'format.step_label': 'Format',
  'format.pdf': 'PDF',
  'format.pdf_detail': 'Ready to print',
  'format.docx': 'Word document',
  'format.docx_detail': 'Can be edited',
  'format.html': 'Reader page',
  'format.html_detail': 'Read on screen, change size any time',

  // Export location

  // Convert button
  'convert.button': 'Make large print',
  'convert.aria_ready': 'Make a {textSize} point large-print {format} of {fileName} on {paperSize} paper',
  'convert.aria_no_file': 'Choose a document first to convert',

  // Advanced options
  'advanced.toggle': 'More options',
  'advanced.page_range_label': 'Only some pages',
  'advanced.page_range_placeholder': 'For example 1-10, 15',

  // Progress screen
  'progress.starting': 'Inspecting document and preparing conversion...',
  'progress.cancel': 'Cancel',

  // Review screen
  'review.banner': 'Sections needing review: {count}',
  'review.original_pane': 'ORIGINAL',
  'review.converted_pane': 'CONVERTED',
  'review.accept': 'Accept',
  'review.accept_as_is': 'Accept as-is',
  'review.accept_all': 'Okay to all',
  'review.accept_all_aria': 'Accept all flagged sections and continue to reader',
  'review.retry': 'Recognize this page again',
  'review.retrying': 'Re-recognizing page...',
  'review.finish': 'Continue to Reader',
  'review.previous': 'Previous',
  'review.next': 'Next',
  'review.reason_label': 'Reason:',
  'review.original_preview': 'Original Source Preview (Page {page})',
  'review.converted_title': 'Converted Large-Print Text',
  'review.complete_title': 'Review Complete',
  'review.complete_desc': 'All flagged sections have been reviewed and accepted.',

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
  'reader.contents': 'Contents',
  'reader.contents_aria': 'Table of Contents',
  'reader.search': 'Search',
  'reader.search_placeholder': 'Search in document...',
  'reader.search_prev': 'Previous match',
  'reader.search_next': 'Next match',
  'reader.search_close': 'Close search',
  'reader.search_matches': '{current} of {total}',
  'reader.search_no_matches': 'No matches found',
  'reader.tts_read': 'Read aloud',
  'reader.tts_pause': 'Pause reading',
  'reader.tts_resume': 'Resume reading',
  'reader.tts_stop': 'Stop reading',
  'reader.tts_speed': 'Speed',

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

  // Export & Print options
  'export.monochrome_label': 'Black and white pictures',
  'export.monochrome_desc': 'For black-and-white laser printers: pictures are printed in clear greys instead of colour.',
  'export.page_break_label': 'Start each original page on a new sheet',
  'export.page_break_desc': 'Keeps each page of the book separate instead of letting the text flow on.',
  'textsize.18': 'Large print',
  'textsize.20': 'Recommended',
  'textsize.24': 'Bigger',
  'textsize.28': 'Biggest',
  'textsize.custom': 'Other size',
  'textsize.custom_label': 'Size in points',
  'textsize.custom_aria': 'Custom body text size in points',
  'textsize.group_aria': 'Text size options',
  'step3.label': 'Make the large-print copy',
  'save.label': 'Saves as',
  'save.in_folder': 'in {folder}',
  'save.change': 'Save somewhere else…',
  'save.reset': 'Save next to the original',
  'advanced.page_range_help': 'Leave empty to convert the whole document.',
  'export.searchable_label': 'Searchable copy of the original instead',
  'export.searchable_desc': 'Keeps the original pages and their size, and adds text that can be searched and copied. The text is not made larger.',
  'export.searchable_active': 'A searchable copy of the original PDF will be made. Its text stays the original size.',
  'settings.button': 'Settings',
  'settings.updates': 'Updates',
  'settings.update_auto': 'Look for a new version when the app starts',
  'settings.update_check': 'Look for a new version now',
  'settings.update_checking': 'Looking…',
  'settings.update_available': 'Version {version} is available.',
  'settings.update_current': 'You have the newest version ({version}).',
  'settings.update_failed': 'Could not look for a new version. Check the internet connection.',
  'settings.version': 'OpenLargePrint {version}',
  'reader.in_picture': 'In the picture:',
  'reader.page_marker': 'Original page {page}',
  'reader.page_marker_printed': 'Original page {page} (printed {printed})',
};

export default en;
