import os
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

os.environ["TK_SILENCE_DEPRECATION"] = "1"

from src.chapter_loader import load_chapters
from src.chapter_pipeline import batch_convert_chapters

BG = "#f5f6f8"
CARD = "#ffffff"
TEXT = "#1f2328"
MUTED = "#6b7280"
ACCENT = "#2563eb"
FONT = "PingFang SC"

VOICES = [
    ("zh-CN-YunjianNeural", "云健 · 男声，沉稳（普通话）"),
    ("zh-CN-YunxiNeural", "云希 · 男声，年轻（普通话）"),
    ("zh-CN-YunyangNeural", "云扬 · 男声，播音腔（普通话）"),
    ("zh-CN-XiaoxiaoNeural", "晓晓 · 女声，温柔（普通话）"),
    ("zh-TW-HsiaoChenNeural", "曉臻 · 女声（台湾国语）"),
    ("en-US-AndrewNeural", "Andrew · 男声（英语）"),
    ("en-US-AvaNeural", "Ava · 女声（英语）"),
]
VOICE_PREVIEW = Path(__file__).resolve().parent.parent / "docs" / "voice-preview.html"
RATES = [("-10%", "慢 -10%"), ("+0%", "正常 +0%"), ("+10%", "+10%"), ("+20%", "+20%"),
         ("+30%", "+30%"), ("+40%", "+40%"), ("+50%", "快 +50%"), ("+75%", "+75%"),
         ("+100%", "很快 +100%")]


class GeneratorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("有声书生成器 · 按章节批量生成")
        self.geometry("760x820")
        self.minsize(680, 700)
        self.configure(bg=BG)
        self.chapters = []
        self._setup_style()
        self._create_widgets()

    def _setup_style(self):
        s = ttk.Style(self)
        s.configure("Horizontal.TProgressbar", thickness=10)

    def _label(self, parent, text, kind="body"):
        fonts = {"title": (FONT, 20, "bold"), "sub": (FONT, 12), "step": (FONT, 14, "bold"),
                 "hint": (FONT, 11), "body": (FONT, 13)}
        colors = {"step": ACCENT, "hint": MUTED, "sub": MUTED}
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=colors.get(kind, TEXT),
                        font=fonts[kind], justify=tk.LEFT, anchor=tk.W)

    def _entry(self, parent):
        return tk.Entry(parent, bg=CARD, fg=TEXT, font=(FONT, 13), relief=tk.SOLID, bd=1,
                        highlightthickness=0, insertbackground=TEXT)

    def _button(self, parent, text, command, primary=False):
        # tk.Button ignores bg on macOS, so use a clickable Label to get real colors
        bg, fg = (ACCENT, "#ffffff") if primary else ("#e5e7eb", TEXT)
        btn = tk.Label(parent, text=text, bg=bg, fg=fg, cursor="hand2",
                       font=(FONT, 15 if primary else 12, "bold" if primary else "normal"),
                       padx=14, pady=10 if primary else 4)
        btn.enabled = True
        btn.bind("<Button-1>", lambda e: btn.enabled and command())
        return btn

    def _set_enabled(self, btn, enabled, text=None):
        btn.enabled = enabled
        btn.config(bg=ACCENT if enabled else "#9db6ef")
        if text:
            btn.config(text=text)

    def _card(self, parent, step, title, hint):
        card = tk.Frame(parent, bg=CARD, padx=16, pady=14, highlightthickness=1, highlightbackground="#e5e7eb")
        card.pack(fill=tk.X, pady=(0, 12))
        card.columnconfigure(1, weight=1)
        self._label(card, f"{step}  {title}", "step").grid(row=0, column=0, columnspan=3, sticky=tk.W)
        h = self._label(card, hint, "hint")
        h.config(wraplength=660)
        h.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 10))
        return card

    def _create_widgets(self):
        # Scrollable page: a Canvas hosting the content frame, with a vertical scrollbar.
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        root = tk.Frame(canvas, bg=BG, padx=24, pady=20)
        window = canvas.create_window((0, 0), window=root, anchor=tk.NW)
        root.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))

        def _on_wheel(e):
            if isinstance(e.widget, tk.Text):  # let the log scroll itself
                return
            delta = e.delta if abs(e.delta) < 20 else e.delta // 120  # macOS vs Windows
            canvas.yview_scroll(-delta, "units")
        self.bind_all("<MouseWheel>", _on_wheel)
        self.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))  # Linux
        self.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))

        self._label(root, "有声书生成器", "title").pack(anchor=tk.W)
        self._label(root, "把电子书的每一章生成一个 MP3 文件。按 ①→④ 的顺序填写即可。", "sub").pack(anchor=tk.W, pady=(0, 14))

        # ① Book file
        c1 = self._card(root, "①", "选择电子书",
                        "支持 EPUB 或 TXT。选好后会自动读取书里的章节目录。")
        self.ent_file = self._entry(c1)
        self.ent_file.grid(row=2, column=0, columnspan=2, sticky=tk.EW, ipady=4)
        self._button(c1, "选择文件…", self._browse_file).grid(row=2, column=2, padx=(8, 0))
        self.lbl_chapters = self._label(c1, "尚未读取章节", "hint")
        self.lbl_chapters.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))

        # ② Chapter range
        c2 = self._card(root, "②", "选择要生成的章节范围",
                        "可以直接在框里输入章节号或标题关键字（如 994）来搜索，再从下拉列表里选。从「开始章节」到「结束章节」（都包含）逐章生成。中途停止后再次点击开始，已完成的章节会自动跳过。")
        self._label(c2, "开始章节").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.cmb_start = ttk.Combobox(c2)
        self.cmb_start.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=(12, 0), pady=4)
        self._label(c2, "结束章节").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.cmb_end = ttk.Combobox(c2)
        self.cmb_end.grid(row=3, column=1, columnspan=2, sticky=tk.EW, padx=(12, 0), pady=4)
        for cmb in (self.cmb_start, self.cmb_end):
            cmb.bind("<<ComboboxSelected>>", lambda e: self._update_range_label())
            cmb.bind("<KeyRelease>", lambda e, c=cmb: self._filter_chapters(e, c))
            cmb.bind("<FocusOut>", lambda e: self._update_range_label())
        self.lbl_range = self._label(c2, "", "hint")
        self.lbl_range.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))

        # ③ Voice
        c3 = self._card(root, "③", "声音与语速",
                        "朗读者：选择谁来读（中文书请选中文声音）。语速：正常为 +0%，数字越大读得越快。")
        self._label(c3, "朗读者").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.cmb_voice = ttk.Combobox(c3, state="readonly", values=[label for _, label in VOICES])
        self.cmb_voice.current(0)
        self.cmb_voice.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=(12, 0), pady=4)
        self._label(c3, "语速").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.var_rate = tk.StringVar(value="+0%")
        rate_box = tk.Frame(c3, bg=c3.cget("bg"))
        rate_box.grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=(12, 0), pady=4)
        for i, (value, label) in enumerate(RATES):
            tk.Radiobutton(rate_box, text=label, value=value, variable=self.var_rate,
                           bg=c3.cget("bg"), fg=TEXT, activebackground=c3.cget("bg"),
                           font=(FONT, 12)).grid(row=i // 5, column=i % 5, sticky=tk.W, padx=(0, 10))
        link = tk.Label(c3, text="▶ 试听所有声音和语速", bg=c3.cget("bg"), fg=ACCENT,
                        cursor="hand2", font=(FONT, 12, "underline"))
        link.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))
        link.bind("<Button-1>", lambda _e: self._open_voice_preview())

        # ④ Output
        c4 = self._card(root, "④", "保存位置",
                        "生成的 MP3 会放在这个文件夹里，文件名按章节编号，例如 0001.mp3。")
        self.ent_out = self._entry(c4)
        self.ent_out.insert(0, str(Path("./output_audiobooks").resolve()))
        self.ent_out.grid(row=2, column=0, columnspan=2, sticky=tk.EW, ipady=4)
        self._button(c4, "选择文件夹…", self._browse_output).grid(row=2, column=2, padx=(8, 0))

        # Action + progress
        self.btn_start = self._button(root, "开始生成", self._start_generation, primary=True)
        self.btn_start.pack(fill=tk.X, pady=(4, 10))
        self.progress_bar = ttk.Progressbar(root, mode="determinate")
        self.progress_bar.pack(fill=tk.X)
        self.lbl_status = self._label(root, "准备就绪", "sub")
        self.lbl_status.pack(anchor=tk.W, pady=(6, 6))

        self.txt_log = tk.Text(root, height=6, bg=CARD, fg=TEXT, font=("Menlo", 11), relief=tk.FLAT,
                               highlightthickness=1, highlightbackground="#e5e7eb", state=tk.DISABLED)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    # ---------- chapter loading ----------
    def _open_voice_preview(self):
        if not VOICE_PREVIEW.exists():
            messagebox.showinfo("试听页面不存在", "请先运行：python scripts/build_voice_preview.py")
            return
        webbrowser.open(VOICE_PREVIEW.as_uri())

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="选择电子书", filetypes=[("EPUB / TXT", "*.epub *.txt"), ("所有文件", "*.*")])
        if path:
            self.ent_file.delete(0, tk.END)
            self.ent_file.insert(0, path)
            self._load_chapters(path)

    def _load_chapters(self, path):
        self.lbl_chapters.config(text="正在读取章节…")
        self._set_enabled(self.btn_start, False)

        def _worker():
            try:
                chapters = load_chapters(path)
                self.after(0, lambda: self._on_chapters_loaded(chapters))
            except Exception as e:
                self.after(0, lambda: self._on_chapters_failed(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_chapters_loaded(self, chapters):
        self._set_enabled(self.btn_start, True)
        self.chapters = chapters
        if not chapters:
            self.lbl_chapters.config(text="没有识别到任何章节")
            self.cmb_start["values"] = self.cmb_end["values"] = []
            return
        labels = [f"第 {c.index} 个  ·  {" ".join(c.title.split())[:40]}" for c in chapters]
        self.chapter_labels = labels
        self.cmb_start["values"] = labels
        self.cmb_end["values"] = labels
        self.cmb_start.set(labels[0])
        self.cmb_end.set(labels[-1])
        self.lbl_chapters.config(text=f"✓ 共识别到 {len(chapters)} 个章节")
        self._update_range_label()

    def _chapter_pos(self, cmb):
        """Position of the selected chapter in self.chapters, or -1."""
        try:
            return self.chapter_labels.index(cmb.get())
        except (AttributeError, ValueError):
            return -1

    def _filter_chapters(self, event, cmb):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        query = cmb.get().strip()
        labels = getattr(self, "chapter_labels", [])
        matches = [l for l in labels if query in l.split("·", 1)[-1]] if query else labels
        cmb["values"] = matches or labels
        self._update_range_label()

    def _on_chapters_failed(self, err):
        self._set_enabled(self.btn_start, True)
        self.chapters = []
        self.lbl_chapters.config(text=f"读取失败：{err}")

    def _update_range_label(self):
        s, e = self._chapter_pos(self.cmb_start), self._chapter_pos(self.cmb_end)
        if s < 0 or e < 0:
            self.lbl_range.config(text="请从下拉列表中选择一个章节")
            return
        if e < s:
            self.lbl_range.config(text="⚠ 结束章节不能在开始章节之前")
        else:
            self.lbl_range.config(text=f"将生成 {e - s + 1} 个章节")

    # ---------- misc ----------
    def _browse_output(self):
        path = filedialog.askdirectory(title="选择保存文件夹")
        if path:
            self.ent_out.delete(0, tk.END)
            self.ent_out.insert(0, path)

    def _log(self, message: str):
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)

    def _update_progress(self, current: int, total: int, msg: str):
        def _update():
            # "Processing" fires before chapter `current` is done; the others fire after.
            done = current - 1 if msg.startswith("Processing") else current
            steps = done * 10 // total if total else 0  # one step per 1/10 of the files
            self.progress_bar["maximum"] = 10
            self.progress_bar["value"] = steps
            self.btn_start.config(text=f"正在生成  {'▰' * steps}{'▱' * (10 - steps)}  {steps * 10}%")
            self.lbl_status.config(text=f"进度 {done}/{total}")
            self._log(msg)
        self.after(0, _update)

    # ---------- run ----------
    def _start_generation(self):
        book_path = self.ent_file.get().strip()
        out_dir = self.ent_out.get().strip()

        if not book_path or not Path(book_path).exists():
            messagebox.showerror("缺少电子书", "请先在第 ① 步选择电子书文件。")
            return
        if not self.chapters:
            messagebox.showerror("没有章节", "还没有读取到章节，请重新选择电子书。")
            return
        s, e = self._chapter_pos(self.cmb_start), self._chapter_pos(self.cmb_end)
        if s < 0 or e < 0 or e < s:
            messagebox.showerror("章节范围有误", "请在第 ② 步选择正确的开始和结束章节。")
            return
        if not out_dir:
            messagebox.showerror("缺少保存位置", "请在第 ④ 步选择保存文件夹。")
            return

        start_ch = self.chapters[s].index
        ch_count = e - s + 1
        voice = VOICES[self.cmb_voice.current()][0]
        rate = self.var_rate.get()

        self._set_enabled(self.btn_start, False, "正在生成…")
        self._log(f"开始生成：第 {start_ch} 到第 {start_ch + ch_count - 1} 章，声音 {voice}，语速 {rate}")

        def _worker():
            try:
                files = batch_convert_chapters(
                    book_path=book_path,
                    output_dir=out_dir,
                    start_chapter=start_ch,
                    chapter_count=ch_count,
                    voice=voice,
                    rate=rate,
                    progress_callback=self._update_progress,
                )
                self.after(0, lambda: messagebox.showinfo("完成", f"已完成 {len(files)} 个章节。\n保存在：{out_dir}"))
            except Exception as err:
                self.after(0, lambda: messagebox.showerror("生成失败", str(err)))
            finally:
                def _reset():
                    self._set_enabled(self.btn_start, True, "开始生成")
                self.after(0, _reset)

        threading.Thread(target=_worker, daemon=True).start()


def main():
    app = GeneratorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
