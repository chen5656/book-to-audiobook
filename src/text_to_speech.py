import os
import tempfile
import asyncio
from typing import Optional
from pydub import AudioSegment
import edge_tts


async def text_to_speech(text, output_file, voice, rate="+0%", pitch="+0Hz", volume="+0%", format="mp3"):
    """
    Converts text into an MP3 audio file.

    Args:
        text (str): Text to convert to audio.
        output_file (str): Output file path.
        voice (str): edge-tts voice id (required, no regional default).
        rate (str): Speech rate.
        pitch (str): Speech pitch.
        volume (str): Speech volume.
        format (str): Output audio format.
    """
    if os.path.exists(output_file):
        raise FileExistsError(
            f"{output_file} already exists. Delete it before regenerating."
        )

    num_characters = len(text)
    num_words = len(text.split())

    # Estimate audio duration (in seconds), assuming ~150 words per minute
    estimated_seconds = (num_words / 150) * 60

    print(f"Starting audiobook synthesis...")
    print(f"Characters: {num_characters}")
    print(f"Words: {num_words}")
    print(f"Estimated duration: {estimated_seconds / 60 / 60:.2f} hours")

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as temp_file:
        await communicate.save(temp_file.name)
        temp_path = temp_file.name

    audio = AudioSegment.from_file(temp_path)
    audio.export(output_file, format="mp3")

    os.remove(temp_path)
    print(f"Audio saved to: {output_file}")


async def list_voices(locale_prefix: Optional[str] = None) -> list:
    """
    Lists available edge-tts voices, optionally filtered by locale prefix
    (e.g. "pt" matches "pt-BR", "pt-PT").
    """
    voices = await edge_tts.list_voices()
    if not locale_prefix:
        return voices
    prefix = locale_prefix.lower()
    return [v for v in voices if v["Locale"].lower().startswith(prefix)]
