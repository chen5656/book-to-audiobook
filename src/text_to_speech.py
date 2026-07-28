import os
import tempfile
import asyncio
from pydub import AudioSegment
import edge_tts
import re

async def text_to_speech(text, output_file, voice="pt-BR-AntonioNeural", rate="+75%", pitch="+0Hz", volume="+0%", format="mp3"):
    """
    Converte texto em um arquivo de áudio MP3.

    Args:
        text (str): Texto a ser convertido em áudio.
        output_file (str): Caminho do arquivo de saída.
        voice (str): Voz a ser utilizada.
        rate (str): Taxa de fala.
        pitch (str): Tom da fala.
        volume (str): Volume da fala.
        format (str): Formato de saída do arquivo de áudio.
    """
    if os.path.exists(output_file):
        raise FileExistsError(
            f"{output_file} already exists. Delete it before regenerating."
        )

    # Informações sobre o texto
    num_caracteres = len(text)
    num_palavras = len(text.split())
    num_frases = len(re.split(r'[.!?]+', text)) - 1  # Subtrai 1 para não contar a última parte
    num_capitulos = text.lower().count("Capítulo")  # Considera a palavra "capítulo" para contagem

    # Estima o tempo do áudio (em segundos)
    # Considera uma média de 150 palavras por minuto
    tempo_estimado = (num_palavras / 150) * 60  # Tempo estimado em segundos
    tamanho_estimado = (num_caracteres / 1000) * 2  # Estimativa de 2 KB por 1000 caracteres

    print(f"Iniciando a geração do audiolivro...")
    print(f"Número de caracteres: {num_caracteres}")
    print(f"Número de palavras: {num_palavras}")
    print(f"Número de frases: {num_frases}")
    print(f"Número de capítulos: {num_capitulos}")
    print(f"Tempo estimado do áudio: {tempo_estimado / 60 / 60:.2f} horas")
    print(f"Tamanho estimado do arquivo: {tamanho_estimado:.2f} KB")

    # Cria um objeto Communicate para conversão de texto em fala
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)

    # Salva o arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as temp_file:
        await communicate.save(temp_file.name)
        temp_path = temp_file.name

    # Converte para AudioSegment e salva no caminho especificado
    audio = AudioSegment.from_file(temp_path)
    audio.export(output_file, format="mp3")

    # Remove o arquivo temporário
    os.remove(temp_path)
    print(f"Áudio salvo em: {output_file}")

# Exemplo de uso
# asyncio.run(text_to_speech("Seu texto aqui.", "output.mp3"))
