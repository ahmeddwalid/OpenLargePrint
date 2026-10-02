from pathlib import Path
import json
import pypdfium2 as pdfium
import pytest
from openlargeprint.qa.corpus_builder import BenchmarkCorpusBuilder
from openlargeprint.qa.metrics import calculate_reading_order_accuracy, calculate_table_structural_score


def test_mixed_document_has_native_cover_and_text_free_scan(tmp_path):
    path = BenchmarkCorpusBuilder(tmp_path).build_mixed_digital_scan()
    with pdfium.PdfDocument(path) as pdf:
        assert pdf[0].get_textpage().count_chars() > 0
        assert pdf[1].get_textpage().count_chars() == 0
        assert len(list(pdf[1].get_objects())) > 0


def test_rotated_fixture_has_visible_nonblank_content(tmp_path):
    path = BenchmarkCorpusBuilder(tmp_path).build_rotated_page()
    with pdfium.PdfDocument(path) as pdf:
        page = pdf[0]
        assert page.get_rotation() == 90
        image = page.render(scale=1).to_pil().convert('L')
        assert image.getextrema()[0] < 100
    assert path.with_suffix('.txt').read_text().strip()


def test_mixed_bidi_reference_and_embedded_original(tmp_path):
    builder = BenchmarkCorpusBuilder(tmp_path)
    path = builder.build_mixed_bidi()
    text = path.with_suffix('.txt').read_text(encoding='utf-8')
    assert any('\u0600' <= char <= '\u06ff' for char in text)
    assert 'Civil Code' in text
    figure = builder.build_images_captions()
    with pdfium.PdfDocument(figure) as pdf:
        assert any(isinstance(obj, pdfium.PdfImage) for obj in pdf[0].get_objects())


def test_two_columns_do_not_overlap_and_have_reference(tmp_path):
    path = BenchmarkCorpusBuilder(tmp_path).build_two_column_law()
    with pdfium.PdfDocument(path) as pdf:
        text = pdf[0].get_textpage()
        bounds = [text.get_rect(i) for i in range(text.count_rects())]
        assert all(right < 310 or left >= 320 for left, bottom, right, top in bounds)
    assert path.with_suffix('.txt').exists()


def test_reference_manifest_for_every_content_case(tmp_path):
    cases = BenchmarkCorpusBuilder(tmp_path).build_all()
    for name, path in cases.items():
        if name == 'malformed_pdf':
            continue
        reference = json.loads(path.with_suffix('.reference.json').read_text(encoding='utf-8'))
        assert reference['reading_order']
        assert reference['source_pages']
        assert isinstance(reference['image_count'], int)
        assert path.with_suffix('.txt').exists()


def test_reading_order_penalizes_inserted_duplicate_content():
    assert calculate_reading_order_accuracy(['a', 'b'], ['a', 'b', 'a']) < 1


def test_table_content_is_case_sensitive_and_missing_cells_penalized():
    assert calculate_table_structural_score([['Law']], [['law']]) < 1
    assert calculate_table_structural_score([['a', 'b'], ['c', 'd']], [['a'], ['c']]) < .8


def test_canonical_transcript_uses_cells_once_and_ignores_markdown():
    import openlargeprint.qa.benchmark as benchmark
    from openlargeprint.ir.models import Block, BlockType, DocumentIR, DocumentMetadata, TableCell, TableStructure
    table = TableStructure(rows=[[TableCell(text='Party'), TableCell(text='Role')], [TableCell(text='Applicant'), TableCell(text='Owner')]])
    doc = DocumentIR(metadata=DocumentMetadata(), blocks=[Block(id='t', type=BlockType.TABLE, source_page=1, table_structure=table, text=table.to_markdown_table())])
    extractor = getattr(benchmark, '_document_transcript', None)
    assert extractor is not None
    assert extractor(doc) == 'Party Role Applicant Owner'

def test_arabic_sentence_fits_inside_fixture_page(tmp_path):
    builder = BenchmarkCorpusBuilder(tmp_path)
    image = builder.render_arabic_page()
    assert builder.arabic_font(28).getlength(builder._ARABIC_PAGE_LINES[1]) + 120 <= image.width

def test_markdown_only_table_transcript_omits_formatting():
    from openlargeprint.qa.benchmark import _document_transcript
    from openlargeprint.ir.models import Block, BlockType, DocumentIR, DocumentMetadata
    doc = DocumentIR(metadata=DocumentMetadata(), blocks=[Block(id='t', type=BlockType.TABLE, source_page=1, text='| Party | Role |\n| --- | :---: |\n| Applicant | Owner |')])
    assert _document_transcript(doc) == 'Party Role Applicant Owner'


def test_reference_metrics_reject_scrambled_order_and_wrong_table_content():
    from openlargeprint.qa.benchmark import _reference_measurements
    from openlargeprint.ir.models import Block, BlockType, DocumentIR, DocumentMetadata, TableCell, TableStructure
    doc = DocumentIR(metadata=DocumentMetadata(), blocks=[Block(id='b', type=BlockType.PARAGRAPH, source_page=1, text='Second clause.'), Block(id='a', type=BlockType.PARAGRAPH, source_page=1, text='First clause.'), Block(id='t', type=BlockType.TABLE, source_page=1, table_structure=TableStructure(rows=[[TableCell(text='law')]]))])
    measured = _reference_measurements(doc, {'reading_order': ['First clause.', 'Second clause.'], 'tables': [[['Law']]], 'source_pages': [1], 'image_count': 0})
    assert measured['reading_order_accuracy'] < 1
    assert measured['table_structural_accuracy'] < 1
    assert measured['page_anchor_fidelity'] == 0
    assert measured['image_content_retention'] is None

def test_image_reference_requires_original_pixels_not_just_image_count(tmp_path):
    from PIL import Image
    from openlargeprint.qa.benchmark import _reference_measurements
    from openlargeprint.ir.models import Block, BlockType, DocumentIR, DocumentMetadata, ImageAsset
    builder = BenchmarkCorpusBuilder(tmp_path)
    images = builder._figure_images()
    blocks = []
    for index in range(2):
        path = tmp_path / f'figure{index}.png'
        image = images[index] if index == 0 else Image.new('RGB', images[index].size, 'red')
        image.save(path)
        blocks.append(Block(id=str(index), type=BlockType.IMAGE, source_page=1, image_asset=ImageAsset(asset_id=str(index), file_path=str(path), width=image.width, height=image.height)))
    measured = _reference_measurements(DocumentIR(metadata=DocumentMetadata(), blocks=blocks), {'reading_order': ['Caption'], 'source_pages': [1], 'image_count': 2, 'image_pixel_hashes': builder._figure_hashes()})
    assert measured['image_content_retention'] == .5


def test_reference_rejects_unexpected_table():
    from openlargeprint.qa.benchmark import _reference_measurements
    from openlargeprint.ir.models import Block, BlockType, DocumentIR, DocumentMetadata, TableCell, TableStructure
    doc = DocumentIR(metadata=DocumentMetadata(), blocks=[Block(id='t', type=BlockType.TABLE, source_page=1, table_structure=TableStructure(rows=[[TableCell(text='Prose')]]))])
    measured = _reference_measurements(doc, {'reading_order': ['Prose'], 'tables': [], 'source_pages': [1], 'image_count': 0})
    assert measured['table_structural_accuracy'] == 0


def test_image_reference_rejects_reshaped_pixels(tmp_path):
    from PIL import Image
    from openlargeprint.qa.benchmark import _reference_measurements
    from openlargeprint.ir.models import Block, BlockType, DocumentIR, DocumentMetadata, ImageAsset
    builder = BenchmarkCorpusBuilder(tmp_path)
    original = builder._figure_images()[0]
    reshaped = Image.frombytes('RGB', (original.height, original.width), original.tobytes())
    path = tmp_path / 'distorted.png'
    reshaped.save(path)
    doc = DocumentIR(metadata=DocumentMetadata(), blocks=[Block(id='i', type=BlockType.IMAGE, source_page=1, image_asset=ImageAsset(asset_id='i', file_path=str(path), width=reshaped.width, height=reshaped.height))])
    measured = _reference_measurements(doc, {'reading_order': ['Caption'], 'source_pages': [1], 'image_count': 2, 'image_pixel_hashes': builder._figure_hashes()})
    assert measured['image_content_retention'] == 0
