import pytest

import src.translate as translate_module
from src.translate import split_into_sentences, translate


class _FakeTranslator:
    def __init__(self, source, target):
        self.source = source
        self.target = target

    def translate(self, text):
        return f"[{self.source}->{self.target}] {text}"


def test_split_into_sentences_splits_on_punctuation():
    result = split_into_sentences("Hello world. How are you? Fine!")

    assert result == ["Hello world.", "How are you?", "Fine!"]


def test_translate_requires_source_and_target():
    with pytest.raises(TypeError):
        translate("Hello world.")


def test_translate_passes_source_and_target_through(monkeypatch):
    monkeypatch.setattr(translate_module, "GoogleTranslator", _FakeTranslator)

    result = translate("Hello world.", source="en", target="pt", limite=4000)

    assert result == "[en->pt] Hello world."


def test_translate_batches_respect_limite(monkeypatch):
    captured_batches = []

    class _RecordingTranslator(_FakeTranslator):
        def translate(self, text):
            captured_batches.append(text)
            return text

    monkeypatch.setattr(translate_module, "GoogleTranslator", _RecordingTranslator)

    long_text = "Sentence one. Sentence two. Sentence three."
    translate(long_text, source="en", target="pt", limite=15)

    assert len(captured_batches) > 1
    assert all(len(batch) <= 15 for batch in captured_batches)