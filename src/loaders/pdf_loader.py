import re

import fitz


def load_pdf(path: str) -> str:
    doc = fitz.open(path)
    pages = []
    for page in doc:
        text = page.get_text("text")
        text = re.sub(r"\n?\s*\d+\s*$", "", text)
        pages.append(text)
    doc.close()

    return "\n".join(pages).strip()