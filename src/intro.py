from src.metadata import BookMetadata


def build_intro_text(metadata: BookMetadata) -> str:
    parts = [metadata.title or "Audiobook"]
    if metadata.subtitle:
        parts.append(metadata.subtitle)
    if metadata.author:
        parts.append(metadata.author)

    return ". ".join(parts) + "."