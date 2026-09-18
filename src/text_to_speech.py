import os
import asyncio
from typing import Optional
import edge_tts


async def text_to_speech(text, output_file, voice, rate="+0%", pitch="+0Hz", volume="+0%", format="mp3"):
    """
    Converts text into an MP3 audio file cleanly without loading raw PCM audio into RAM.

    Args:
        text (str): Text to convert to audio.
        output_file (str): Output file path.
        voice (str): edge-tts voice id (required).
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
    estimated_seconds = (num_words / 150) * 60

    print(f"Starting synthesis ({num_characters} chars, est. {estimated_seconds / 60:.1f} min)...")

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)

    if format.lower() == "mp3":
        # Save directly to output MP3 file to prevent raw PCM memory bloat
        await communicate.save(output_file)
    else:
        import tempfile
        from pydub import AudioSegment
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".mp3") as temp_file:
            temp_path = temp_file.name
        try:
            await communicate.save(temp_path)
            audio = AudioSegment.from_file(temp_path)
            audio.export(output_file, format=format)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    print(f"Audio saved to: {output_file}")


async def list_voices(locale_prefix: Optional[str] = None) -> list:
    """
    Lists available edge-tts voices, optionally filtered by locale prefix.
    """
    voices = await edge_tts.list_voices()
    if not locale_prefix:
        return voices
    prefix = locale_prefix.lower()
    return [v for v in voices if v["Locale"].lower().startswith(prefix)]
