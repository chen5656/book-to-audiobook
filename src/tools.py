from pydub import AudioSegment

def split_text_into_parts(text, n_parts):
    """
    Splits text into a list of n_parts approximately equal chunks,
    without breaking words mid-way.

    Args:
        text (str): The text to split.
        n_parts (int): Number of parts to split into.

    Returns:
        list: Text split into n_parts chunks.
    """
    text = text.strip()
    part_size = len(text) // n_parts

    parts = []
    start = 0

    for i in range(n_parts):
        end = start + part_size

        if end < len(text):
            while end < len(text) and text[end] not in [' ', '\n']:
                end += 1

        parts.append(text[start:end].strip())
        start = end

    return parts

def combine_audio_files(files, output_file):
    """
    Combines multiple MP3 audio files into a single file.

    Args:
        files (list): Paths of the audio files to combine.
        output_file (str): Path of the combined audio file to save.
    """
    combined_audio = AudioSegment.empty()

    for file in files:
        audio = AudioSegment.from_mp3(file)
        combined_audio += audio

    combined_audio.export(output_file, format="mp3")
    print(f"Combined file saved to: {output_file}")
