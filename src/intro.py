from src.metadata import BookMetadata


def build_intro_text(metadata: BookMetadata) -> str:
    parts = [metadata.title or "Audiobook"]
    if metadata.subtitle:
        parts.append(metadata.subtitle)

    intro = ". ".join(parts) + "."
    if metadata.author:
        intro += f" De {metadata.author}."

    return intro