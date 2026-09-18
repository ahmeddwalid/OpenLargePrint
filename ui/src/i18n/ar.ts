/**
 * Arabic string table for OpenLargePrint UI (A11Y-005, LANG-001, LANG-002).
 * All user-facing text translated to standard Arabic.
 */

const ar: Record<string, string> = {
  // App header
  'app.title': 'طباعة كبيرة مفتوحة',
  'app.subtitle': 'تكبير المستندات لضعاف البصر',
  'app.skip_to_content': 'تخطي إلى المحتوى الرئيسي',

  // Theme selector
  'theme.label': 'المظهر:',
  'theme.light': 'فاتح (افتراضي)',
  'theme.auto': 'تلقائي (حسب النظام)',
  'theme.sepia': 'بني داكن',
  'theme.dark': 'داكن',

  // Direction toggle
  'dir.toggle_to_rtl': 'تبديل اتجاه القراءة إلى اليمين لليسار',
  'dir.toggle_to_ltr': 'تبديل اتجاه القراءة إلى اليسار لليمين',
  'dir.rtl_label': 'عربي',
  'dir.ltr_label': 'LTR',

  // Language selector
  'lang.label': 'اللغة:',
  'lang.en': 'English',
  'lang.ar': 'العربية',

  // File picker
  'file.step_label': 'اختر مستندًا',
  'file.dropzone_prompt': 'اسحب ملفًا هنا، أو انقر للتصفح',
  'file.dropzone_help': 'الصيغ المدعومة: PDF، DOCX، PPTX، DOC، PPT',
  'file.browse_button': 'تصفح الملفات',
  'file.clear_button': 'إزالة',
  'file.size_label': 'الحجم:',

  // Text size selector
  'textsize.step_label': 'حجم الخط',
  'textsize.comfortable': 'مريح',
  'textsize.comfortable_detail': '18 نقطة',
  'textsize.large': 'كبير',
  'textsize.large_detail': '20 نقطة (افتراضي)',
  'textsize.extra_large': 'كبير جدًا',
  'textsize.extra_large_detail': '24 نقطة',
  'textsize.very_large': 'ضخم',
  'textsize.very_large_detail': '28 نقطة',

  // Paper size selector
  'paper.step_label': 'حجم الورق',
  'paper.a4': 'A4',
  'paper.a4_detail': '210 × 297 ملم (افتراضي)',
  'paper.a3': 'A3',
  'paper.a3_detail': '297 × 420 ملم',

  // Output format selector
  'format.step_label': 'صيغة الإخراج',
  'format.pdf': 'PDF',
  'format.pdf_detail': 'مستند جاهز للطباعة',
  'format.docx': 'Word',
  'format.docx_detail': 'مستند قابل للتحرير',
  'format.html': 'قارئ',
  'format.html_detail': 'عرض في التطبيق',

  // Export location
  'export.step_label': 'حفظ في',
  'export.downloads': 'التنزيلات',
  'export.desktop': 'سطح المكتب',
  'export.source': 'نفس مجلد الملف الأصلي',
  'export.custom': 'اختر موقعًا...',
  'export.output_path': 'ملف الإخراج:',

  // Convert button
  'convert.button': 'تحويل إلى طباعة كبيرة',
  'convert.aria_ready': 'تحويل {fileName} إلى طباعة كبيرة بحجم {textSize} نقطة على ورق {paperSize} بصيغة {format}',
  'convert.aria_no_file': 'اختر مستندًا أولًا للتحويل',

  // Advanced options
  'advanced.toggle': 'خيارات إضافية',
  'advanced.routing_label': 'وضع المعالجة',
  'advanced.routing_auto': 'تلقائي',
  'advanced.routing_native': 'نص أصلي فقط',
  'advanced.routing_ocr': 'التعرف الضوئي فقط',
  'advanced.routing_max': 'أقصى دقة',
  'advanced.page_range_label': 'نطاق الصفحات',
  'advanced.page_range_placeholder': 'مثال: 1-10، 15، 20-30',

  // Progress screen
  'progress.starting': 'فحص المستند وتجهيز التحويل...',
  'progress.cancel': 'إلغاء',

  // Review screen
  'review.banner': '{count} صفحات قد تحتاج مراجعة',
  'review.original_pane': 'الأصل',
  'review.converted_pane': 'المحوّل',
  'review.accept': 'قبول',
  'review.retry': 'إعادة المحاولة بدقة أعلى',
  'review.finish': 'متابعة إلى القارئ',

  // Reader view
  'reader.back': 'رجوع ←',
  'reader.text_size': 'حجم الخط:',
  'reader.zoom_out': 'أ-',
  'reader.zoom_out_aria': 'تصغير حجم الخط',
  'reader.zoom_in': 'أ+',
  'reader.zoom_in_aria': 'تكبير حجم الخط',
  'reader.font_label': 'الخط:',
  'reader.font_system': 'خط النظام',
  'reader.font_hyperlegible': 'Atkinson Hyperlegible',
  'reader.font_lexend': 'Lexend',
  'reader.font_mono': 'خط ثابت العرض',
  'reader.spacing_label': 'التباعد:',
  'reader.spacing_standard': '1.4x (قياسي)',
  'reader.spacing_comfortable': '1.6x (مريح)',
  'reader.spacing_spacious': '1.8x (واسع)',
  'reader.spacing_double': '2.0x (مضاعف)',
  'reader.ruler_on': 'خط التوجيه مفعّل',
  'reader.ruler_off': 'خط التوجيه معطّل',
  'reader.ruler_aria': 'تبديل خط التوجيه الأفقي',
  'reader.print': 'طباعة...',
  'reader.print_aria': 'طباعة هذا المستند مباشرة باستخدام طابعة النظام',
  'reader.page_label': 'الصفحة:',
  'reader.all_pages': 'جميع الصفحات ({count})',
  'reader.save_document': 'حفظ المستند',
  'reader.save_page': 'حفظ الصفحة {page}',
  'reader.content_aria': 'محتوى المستند',
  'reader.title_aria': 'قارئ الطباعة الكبيرة',

  // Recent documents
  'recent.title': 'المستندات الأخيرة',
  'recent.clear': 'مسح السجل',
  'recent.open_reader': 'فتح في القارئ',
  'recent.empty': 'لا توجد تحويلات سابقة',

  // Errors
  'error.conversion_cancelled': 'تم إلغاء التحويل.',
  'error.unsupported_type': 'صيغة الملف هذه غير مدعومة.',

  // File actions
  'file.open_file': 'فتح الملف',
  'file.show_in_folder': 'عرض في المجلد',
  'file.saved_file': 'الملف المحفوظ:',
};

export default ar;
