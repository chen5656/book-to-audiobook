from pydub import AudioSegment

from src.tools import combinar_arquivos_audio, dividir_texto_em_partes


def test_dividir_texto_em_partes_does_not_break_words():
    texto = "one two three four five six seven eight nine ten"

    partes = dividir_texto_em_partes(texto, 3)

    assert len(partes) == 3
    rejoined = " ".join(partes)
    for word in texto.split():
        assert word in rejoined.split()


def test_dividir_texto_em_partes_covers_full_text():
    texto = "alpha beta gamma delta epsilon"

    partes = dividir_texto_em_partes(texto, 2)

    assert "".join(partes).replace(" ", "") == texto.replace(" ", "")


def test_combinar_arquivos_audio_concatenates_files(tmp_path):
    file_a = tmp_path / "a.mp3"
    file_b = tmp_path / "b.mp3"
    output = tmp_path / "combined.mp3"

    AudioSegment.silent(duration=500).export(str(file_a), format="mp3")
    AudioSegment.silent(duration=700).export(str(file_b), format="mp3")

    combinar_arquivos_audio([str(file_a), str(file_b)], str(output))

    assert output.exists()
    combined = AudioSegment.from_mp3(str(output))
    assert len(combined) >= 1000