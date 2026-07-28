import re

from deep_translator import GoogleTranslator
from tqdm import tqdm


def split_into_sentences(texto: str) -> list:
    frases = re.split(r'(?<=[.!?]) +', texto)
    return [frase.strip() for frase in frases if frase.strip()]


def translate(texto_original: str, source: str, target: str, limite: int = 4000) -> str:
    tradutor = GoogleTranslator(source=source, target=target)

    frases = split_into_sentences(texto_original)

    partes = []
    lote_atual = ""

    for frase in frases:
        if len(lote_atual) + len(frase) + 1 <= limite:
            lote_atual = f"{lote_atual} {frase}".strip() if lote_atual else frase
        else:
            partes.append(lote_atual)
            lote_atual = frase

    if lote_atual:
        partes.append(lote_atual)

    partes_traduzidas = [
        tradutor.translate(parte) for parte in tqdm(partes, desc="Traduzindo lotes")
    ]

    return ''.join(partes_traduzidas)