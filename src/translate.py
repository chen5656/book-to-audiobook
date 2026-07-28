import re

from deep_translator import GoogleTranslator
from tqdm import tqdm


def split_into_sentences(text: str) -> list:
    sentences = re.split(r'(?<=[.!?]) +', text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def translate(original_text: str, source: str, target: str, limit: int = 4000) -> str:
    translator = GoogleTranslator(source=source, target=target)

    sentences = split_into_sentences(original_text)

    batches = []
    current_batch = ""

    for sentence in sentences:
        if len(current_batch) + len(sentence) + 1 <= limit:
            current_batch = f"{current_batch} {sentence}".strip() if current_batch else sentence
        else:
            batches.append(current_batch)
            current_batch = sentence

    if current_batch:
        batches.append(current_batch)

    translated_batches = [
        translator.translate(batch) for batch in tqdm(batches, desc="Translating batches")
    ]

    return ''.join(translated_batches)
