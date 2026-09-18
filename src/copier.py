import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple


def natural_sort_key(s: str) -> List:
    """
    Sort key for natural alphanumeric sorting (e.g., 1.mp3 < 2.mp3 < 10.mp3).
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", str(s))]


def find_external_drives() -> List[Tuple[str, str]]:
    """
    Detects external drives and mounted removable media across OS platforms.
    Returns a list of tuples: (display_name, path_str).
    """
    drives: List[Tuple[str, str]] = []

    if sys.platform == "darwin":
        volumes = Path("/Volumes")
        if volumes.exists():
            for p in volumes.iterdir():
                if p.is_dir() and not p.is_symlink():
                    name = p.name
                    # Exclude primary system drive
                    if name in ("Macintosh HD", "Macintosh HD - Data"):
                        continue
                    drives.append((name, str(p)))
    elif sys.platform.startswith("linux"):
        for base in ["/media", "/run/media", "/mnt"]:
            bp = Path(base)
            if bp.exists():
                for root, dirs, _files in os.walk(bp):
                    for d in dirs:
                        dp = Path(root) / d
                        if dp.is_mount() or root != base:
                            drives.append((dp.name, str(dp)))
    elif sys.platform == "win32":
        import string
        from ct.windll import kernel32  # type: ignore # fallback check
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                drives.append((f"Drive ({letter}:)", drive_path))

    return drives


def copy_audio_files_to_device(
    source_dir: str,
    target_dir: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[str]:
    """
    Copies audio files (.mp3) from source_dir to target_dir in strict natural numerical order.
    Preserves exact sequential order required by FAT-based swimming MP3 players.
    """
    src_path = Path(source_dir)
    tgt_path = Path(target_dir)

    if not src_path.exists() or not src_path.is_dir():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    tgt_path.mkdir(parents=True, exist_ok=True)

    # Collect MP3 files
    mp3_files = [f for f in src_path.iterdir() if f.is_file() and f.suffix.lower() == ".mp3"]
    mp3_files.sort(key=lambda f: natural_sort_key(f.name))

    total = len(mp3_files)
    copied_files: List[str] = []

    for idx, src_file in enumerate(mp3_files, start=1):
        dst_file = tgt_path / src_file.name

        if progress_callback:
            progress_callback(idx, total, f"Copying {src_file.name} ({idx}/{total})...")

        # Copy file cleanly
        shutil.copyfile(str(src_file), str(dst_file))
        # Ensure timestamp ordering gap for simple MP3 player directory indexers
        time.sleep(0.05)

        copied_files.append(str(dst_file))

        if progress_callback:
            progress_callback(idx, total, f"Finished copying {src_file.name}")

    return copied_files
