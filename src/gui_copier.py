import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

os.environ["TK_SILENCE_DEPRECATION"] = "1"

from src.copier import copy_audio_files_to_device, find_external_drives


class CopierGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Swimming MP3 Player - File Copier Tool")
        self.geometry("680x520")
        self.resizable(True, True)

        self.configure(bg="#ececec")
        self._create_widgets()
        self._refresh_drives()

    def _create_widgets(self):
        main_frame = tk.Frame(self, bg="#ececec", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Source Audio Directory
        lbl_src = tk.Label(main_frame, text="Source MP3 Folder:", bg="#ececec", fg="#000000", font=("Helvetica", 11, "bold"))
        lbl_src.grid(row=0, column=0, sticky=tk.W, pady=6)
        self.ent_src = tk.Entry(main_frame, width=40, bg="#ffffff", fg="#000000", font=("Helvetica", 11), relief=tk.SOLID, bd=1)
        self.ent_src.insert(0, str(Path("./output_audiobooks").resolve()))
        self.ent_src.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=6, padx=8)
        btn_browse_src = tk.Button(main_frame, text="Browse...", command=self._browse_source, bg="#e1e1e1", fg="#000000", font=("Helvetica", 10), relief=tk.RAISED)
        btn_browse_src.grid(row=0, column=2, pady=6)

        # External Drive Selector
        lbl_drive = tk.Label(main_frame, text="Detected Drive:", bg="#ececec", fg="#000000", font=("Helvetica", 11, "bold"))
        lbl_drive.grid(row=1, column=0, sticky=tk.W, pady=6)
        self.cmb_drive = ttk.Combobox(main_frame, width=38, state="readonly")
        self.cmb_drive.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=6, padx=8)
        btn_refresh = tk.Button(main_frame, text="Refresh", command=self._refresh_drives, bg="#e1e1e1", fg="#000000", font=("Helvetica", 10), relief=tk.RAISED)
        btn_refresh.grid(row=1, column=2, pady=6)

        # Custom Target Path / Manual Drive Browse
        lbl_tgt = tk.Label(main_frame, text="Target Folder on Drive:", bg="#ececec", fg="#000000", font=("Helvetica", 11))
        lbl_tgt.grid(row=2, column=0, sticky=tk.W, pady=6)
        self.ent_tgt = tk.Entry(main_frame, width=40, bg="#ffffff", fg="#000000", font=("Helvetica", 11), relief=tk.SOLID, bd=1)
        self.ent_tgt.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=6, padx=8)
        btn_browse_tgt = tk.Button(main_frame, text="Browse...", command=self._browse_target, bg="#e1e1e1", fg="#000000", font=("Helvetica", 10), relief=tk.RAISED)
        btn_browse_tgt.grid(row=2, column=2, pady=6)

        # Action Buttons
        btn_frame = tk.Frame(main_frame, bg="#ececec")
        btn_frame.grid(row=3, column=0, columnspan=3, pady=12)

        self.btn_copy = tk.Button(btn_frame, text="Copy Audio Files in Sequential Order", command=self._start_copy, bg="#007aff", fg="#ffffff", font=("Helvetica", 11, "bold"), padx=12, pady=6, relief=tk.RAISED)
        self.btn_copy.pack(side=tk.LEFT, padx=5)

        # Progress bar
        self.progress_bar = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, mode="determinate")
        self.progress_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=6)

        self.lbl_status = tk.Label(main_frame, text="Select source folder and target drive to begin.", bg="#ececec", fg="#555555", font=("Helvetica", 10, "italic"))
        self.lbl_status.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=4)

        # Log text box
        log_frame = tk.Frame(main_frame, bg="#ececec")
        log_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.txt_log = tk.Text(log_frame, height=8, bg="#ffffff", fg="#000000", font=("Courier", 10), state=tk.DISABLED, relief=tk.SOLID, bd=1)
        self.txt_log.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        scrollbar = tk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.txt_log.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.txt_log["yscrollcommand"] = scrollbar.set

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)

        self.cmb_drive.bind("<<ComboboxSelected>>", self._on_drive_selected)

    def _browse_source(self):
        path = filedialog.askdirectory(title="Select Source Folder with MP3 Files")
        if path:
            self.ent_src.delete(0, tk.END)
            self.ent_src.insert(0, path)

    def _browse_target(self):
        path = filedialog.askdirectory(title="Select Target Directory on MP3 Player")
        if path:
            self.ent_tgt.delete(0, tk.END)
            self.ent_tgt.insert(0, path)

    def _refresh_drives(self):
        self.drives = find_external_drives()
        options = [f"{name} ({path})" for name, path in self.drives]
        self.cmb_drive["values"] = options
        if options:
            self.cmb_drive.current(0)
            self._on_drive_selected(None)
        else:
            self.cmb_drive.set("")
            self._log("No external drives automatically detected. You can browse target directory manually.")

    def _on_drive_selected(self, event):
        idx = self.cmb_drive.current()
        if idx >= 0 and idx < len(self.drives):
            _name, path = self.drives[idx]
            self.ent_tgt.delete(0, tk.END)
            self.ent_tgt.insert(0, path)

    def _log(self, message: str):
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)

    def _update_progress(self, current: int, total: int, msg: str):
        def _update():
            self.progress_bar["maximum"] = total
            self.progress_bar["value"] = current
            self.lbl_status.config(text=f"[{current}/{total}] {msg}")
            self._log(msg)
        self.after(0, _update)

    def _start_copy(self):
        src_dir = self.ent_src.get().strip()
        tgt_dir = self.ent_tgt.get().strip()

        if not src_dir or not Path(src_dir).exists():
            messagebox.showerror("Error", "Please select a valid source directory.")
            return

        if not tgt_dir:
            messagebox.showerror("Error", "Please select a valid target directory.")
            return

        self.btn_copy.config(state=tk.DISABLED)
        self._log(f"Starting sequential copy from {src_dir} to {tgt_dir}...")

        def _worker():
            try:
                copied = copy_audio_files_to_device(
                    source_dir=src_dir,
                    target_dir=tgt_dir,
                    progress_callback=self._update_progress,
                )
                self.after(0, lambda: messagebox.showinfo("Success", f"Copied {len(copied)} files sequentially to target drive."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Copying failed: {e}"))
            finally:
                self.after(0, lambda: self.btn_copy.config(state=tk.NORMAL))

        threading.Thread(target=_worker, daemon=True).start()


def main():
    app = CopierGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
