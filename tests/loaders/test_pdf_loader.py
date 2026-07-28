import fitz

from src.loaders.pdf_loader import load_pdf


def _build_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world.")
    page.insert_text((72, 700), "42")  # simulated page-number footer
    path = tmp_path / "test.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_load_pdf_extracts_text(tmp_path):
    path = _build_pdf(tmp_path)

    result = load_pdf(path)

    assert "Hello world." in result


def test_load_pdf_strips_trailing_page_number(tmp_path):
    path = _build_pdf(tmp_path)

    result = load_pdf(path)

    assert result.strip().splitlines()[-1] != "42"