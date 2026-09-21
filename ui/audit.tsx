import React from 'react';
import { createRoot } from 'react-dom/client';
import { I18nProvider } from './src/i18n/i18n';
import { ReviewScreen } from './src/components/ReviewScreen';
import { ReaderView } from './src/components/ReaderView';
import { ProgressScreen } from './src/components/ProgressScreen';
import './src/styles/theme.css';
import data from './audit-data.json';
const query = new URLSearchParams(location.search);
document.documentElement.setAttribute('data-theme', query.get('theme') || 'sepia');
document.documentElement.style.fontSize = query.get('scale') || '100%';
const noop = () => {};
const items = data.review_items.map((item, index) => ({id: String(index), block_id: item.block_id || undefined, source_page: item.page_number, reason: item.reason, converted_text: item.converted_text, original_snippet: '', original_preview: data.review_previews[String(item.page_number)],status:'pending' as const}));
const ir = {schema_version:'1.0.0',source_file:'scanned_english.pdf',source_mime:'application/pdf',page_count:1,blocks:data.document_ir.blocks.map(block=>({id:block.id,block_type:block.type==='text'?'paragraph':block.type,heading_level:block.level,text:block.text||'',source_page:block.source_page}))};
const view=query.get('view');
createRoot(document.getElementById('audit')!).render(<I18nProvider><div className="app-container">
{view==='reader' ? <ReaderView documentIR={ir as never} initialSize={20} currentTheme="sepia" onThemeChange={noop} onBack={noop} onExport={noop}/> : view==='progress' ? <ProgressScreen fileName="scanned_english.pdf" progress={{currentPage:1,totalPages:2,stage:'ocr',humanMessage:'Recognizing scanned text, page 1 of 2',percent:50}} onCancel={noop}/> : <ReviewScreen reviewItems={view==='complete'?[]:items} onAccept={noop} onRetry={async()=>null} onFinish={noop}/>}</div></I18nProvider>);
