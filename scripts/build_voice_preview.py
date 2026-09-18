"""Generate docs/voice-preview.html: one playable sample per GUI voice x rate.

Re-run after changing VOICES or RATES in src/gui_generator.py:
    python scripts/build_voice_preview.py
"""
import asyncio
import base64
import html
import sys
import tempfile
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.gui_generator import RATES, VOICES  # noqa: E402

OUT = ROOT / "docs" / "voice-preview.html"
SAMPLES = {
    "zh": "第一章。那天早上，天刚蒙蒙亮，他推开窗户，看见远处的山在雾里若隐若现。",
    "en": "Chapter one. That morning, just before dawn, he opened the window and saw the distant hills fading in and out of the mist.",
}


async def synth(text, voice, rate, path):
    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


async def main():
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for voice, label in VOICES:
            text = SAMPLES[voice[:2]]
            cells = []
            for rate, rate_label in RATES:
                mp3 = Path(tmp) / f"{voice}_{rate}.mp3"
                await synth(text, voice, rate, mp3)
                b64 = base64.b64encode(mp3.read_bytes()).decode()
                cells.append(f'<td><div class="r">{html.escape(rate_label)}</div>'
                             f'<audio controls preload="none" src="data:audio/mpeg;base64,{b64}"></audio></td>')
                print(f"  {voice} {rate}")
            rows.append(f"<tr><th>{html.escape(label)}<br><code>{voice}</code></th>{''.join(cells)}</tr>")

    OUT.write_text(f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>声音试听</title>
<style>
:root{{--bg:#f5f6f8;--card:#fff;--fg:#1f2328;--mu:#6b7280;--bd:#e5e7eb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161616;--card:#1f1f1f;--fg:#eee;--mu:#9ca3af;--bd:#333}}}}
body{{background:var(--bg);color:var(--fg);font-family:"PingFang SC",system-ui,sans-serif;margin:24px 16px}}
.wrap{{max-width:1200px;margin:auto;background:var(--card);border-radius:12px;padding:20px;overflow-x:auto}}
p{{color:var(--mu)}} table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid var(--bd);padding:10px;text-align:left;vertical-align:top}}
th{{min-width:170px}} code{{color:var(--mu);font-size:12px}} .r{{color:var(--mu);font-size:13px;margin-bottom:4px}}
audio{{width:100%;min-width:170px}}
</style></head><body><div class="wrap">
<h2>声音 × 语速试听</h2>
<p>中文示例：“{SAMPLES["zh"]}”<br>English sample: “{SAMPLES["en"]}”</p>
<table>{''.join(rows)}</table>
</div></body></html>
""", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
