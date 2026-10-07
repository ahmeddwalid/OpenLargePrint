/**
 * Arabic string table for OpenLargePrint UI (A11Y-005, LANG-001, LANG-002).
 * All user-facing text translated to standard Arabic.
 */

const ar: Record<string, string> = {
  // App header
  'app.title': 'طباعة كبيرة مفتوحة',
  'app.subtitle': 'تكبير المستندات بشكل ميسر',
  'app.skip_to_content': 'تخطي إلى المحتوى الرئيسي',

  // Theme selector
  'theme.label': 'الألوان',
  'theme.sepia': 'ورق دافئ (افتراضي)',
  'theme.light': 'فاتح',
  'theme.auto': 'حسب إعدادات الحاسوب',
  'theme.dark': 'داكن',

  // Direction toggle

  // Language selector
  'lang.label': 'اللغة',
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
  'textsize.step_label': 'اختر حجم الخط',
  'textsize.comfortable': 'مريح',
  'textsize.comfortable_detail': '18 نقطة',
  'textsize.large': 'كبير',
  'textsize.large_detail': '20 نقطة (افتراضي)',
  'textsize.extra_large': 'كبير جدًا',
  'textsize.extra_large_detail': '24 نقطة',
  'textsize.very_large': 'ضخم',
  'textsize.very_large_detail': '28 نقطة',

  // Paper size selector
  'paper.step_label': 'الورق',
  'paper.a4': 'A4',
  'paper.a4_detail': 'الورق العادي (افتراضي)',
  'paper.a3': 'A3',
  'paper.a3_detail': 'ضعف المساحة، للجداول العريضة',

  // Output format selector
  'format.step_label': 'الصيغة',
  'format.pdf': 'PDF',
  'format.pdf_detail': 'جاهز للطباعة',
  'format.docx': 'مستند Word',
  'format.docx_detail': 'قابل للتعديل',
  'format.html': 'صفحة قراءة',
  'format.html_detail': 'للقراءة على الشاشة مع تغيير الحجم في أي وقت',

  // Export location

  // Convert button
  'convert.button': 'أنشئ الطباعة الكبيرة',
  'convert.aria_ready': 'إنشاء نسخة {format} بطباعة كبيرة بحجم {textSize} نقطة من {fileName} على ورق {paperSize}',
  'convert.aria_no_file': 'اختر مستندًا أولًا للتحويل',

  // Advanced options
  'advanced.toggle': 'خيارات إضافية',
  'advanced.page_range_label': 'صفحات محددة فقط',
  'advanced.page_range_placeholder': 'مثال: 1-10، 15',

  // Progress screen
  'progress.starting': 'فحص المستند وتجهيز التحويل...',
  'progress.cancel': 'إلغاء',

  // Review screen
  'review.banner': 'مقاطع تحتاج مراجعة: {count}',
  'review.original_pane': 'الأصل',
  'review.converted_pane': 'المحوّل',
  'review.accept': 'قبول',
  'review.accept_as_is': 'قبول كما هو',
  'review.accept_all': 'موافق على الكل',
  'review.accept_all_aria': 'قبول جميع الأقسام المحددة للمراجعة والمتابعة إلى القارئ',
  'review.retry': 'إعادة التعرف على الصفحة',
  'review.retrying': 'جارٍ إعادة التعرف على الصفحة...',
  'review.finish': 'متابعة إلى القارئ',
  'review.previous': 'السابق',
  'review.next': 'التالي',
  'review.reason_label': 'السبب:',
  'review.original_preview': 'معاينة المصدر الأصلي (صفحة {page})',
  'review.converted_title': 'النص المكبّر المحوّل',
  'review.complete_title': 'اكتملت المراجعة',
  'review.complete_desc': 'تمت مراجعة وقبول جميع الأقسام المحددة.',

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
  'reader.contents': 'المحتويات',
  'reader.contents_aria': 'جدول المحتويات',
  'reader.search': 'بحث',
  'reader.search_placeholder': 'البحث في المستند...',
  'reader.search_prev': 'المطابقة السابقة',
  'reader.search_next': 'المطابقة التالية',
  'reader.search_close': 'إغلاق البحث',
  'reader.search_matches': '{current} من {total}',
  'reader.search_no_matches': 'لم يتم العثور على نتائج',
  'reader.tts_read': 'قراءة صوتية',
  'reader.tts_pause': 'إيقاف مؤقت',
  'reader.tts_resume': 'استئناف القراءة',
  'reader.tts_stop': 'إيقاف القراءة',
  'reader.tts_speed': 'السرعة',

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

  // Export & Print options
  'export.monochrome_label': 'صور بالأبيض والأسود',
  'export.monochrome_desc': 'لطابعات الليزر بالأبيض والأسود: تُطبع الصور بدرجات رمادية واضحة بدل الألوان.',
  'export.page_break_label': 'ابدأ كل صفحة أصلية في ورقة جديدة',
  'export.page_break_desc': 'يبقي كل صفحة من الكتاب منفصلة بدل أن يتدفق النص متصلًا.',
  'textsize.18': 'طباعة كبيرة',
  'textsize.20': 'الموصى به',
  'textsize.24': 'أكبر',
  'textsize.28': 'الأكبر',
  'textsize.custom': 'حجم آخر',
  'textsize.custom_label': 'الحجم بالنقاط',
  'textsize.custom_aria': 'حجم نص مخصص بالنقاط',
  'textsize.group_aria': 'خيارات حجم الخط',
  'step3.label': 'أنشئ نسخة الطباعة الكبيرة',
  'save.label': 'يُحفظ باسم',
  'save.in_folder': 'في {folder}',
  'save.change': 'احفظ في مكان آخر…',
  'save.reset': 'احفظ بجانب الملف الأصلي',
  'advanced.page_range_help': 'اتركه فارغًا لتحويل المستند كله.',
  'export.searchable_label': 'نسخة من الأصل قابلة للبحث بدلًا من ذلك',
  'export.searchable_desc': 'تبقى الصفحات الأصلية بحجمها، ويُضاف نص يمكن البحث فيه ونسخه. لا يُكبَّر النص.',
  'export.searchable_active': 'ستُنشأ نسخة قابلة للبحث من ملف PDF الأصلي. يبقى النص بحجمه الأصلي.',
  'settings.button': 'الإعدادات',
  'settings.updates': 'التحديثات',
  'settings.update_auto': 'ابحث عن إصدار جديد عند تشغيل البرنامج',
  'settings.update_check': 'ابحث عن إصدار جديد الآن',
  'settings.update_checking': 'جارٍ البحث…',
  'settings.update_available': 'الإصدار {version} متاح.',
  'settings.update_current': 'لديك أحدث إصدار ({version}).',
  'settings.update_failed': 'تعذّر البحث عن إصدار جديد. تحقق من الاتصال بالإنترنت.',
  'settings.version': 'OpenLargePrint {version}',
  'reader.in_picture': 'في الصورة:',
  'reader.page_marker': 'الصفحة الأصلية {page}',
  'reader.page_marker_printed': 'الصفحة الأصلية {page} (المطبوعة {printed})',
  'reader.font_serif': 'Georgia (بخطوط مذيّلة)',
  'reader.width_label': 'العرض',
  'reader.width_aria': 'عرض سطر القراءة',
  'reader.width_narrow': 'ضيق',
  'reader.width_medium': 'متوسط',
  'reader.width_wide': 'عريض',
  'reader.width_full': 'كامل العرض',
  'review.retry_title': 'أُعيد التعرف على الصفحة',
  'review.retry_help': 'قارن هذه النتيجة بالأصل. انسخ أي تصحيحات إلى النص أعلاه قبل القبول.',
};

export default ar;
