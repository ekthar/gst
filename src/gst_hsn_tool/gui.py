from __future__ import annotations

import ctypes
import os
import random
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from gst_hsn_tool.catalog import download_and_build_master
from gst_hsn_tool.config import LEARNING_DB_PATH
from gst_hsn_tool.learning import import_learning_file
from gst_hsn_tool.pipeline import run_pipeline
from gst_hsn_tool.training import backup_training_state, restore_training_state, run_training_mode


class GstHsnApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("GST HSN Resolver Studio")
        self.root.geometry("1140x780")
        self.root.minsize(1020, 700)

        self.colors = {
            "bg": "#fff8f6",
            "surface": "#ffffff",
            "surface_alt": "#fff0ea",
            "ink": "#2b1f2a",
            "muted": "#7b6677",
            "accent": "#ff7f50",
            "accent_soft": "#ffd2c0",
            "mint": "#6db7ad",
            "line": "#f3d6cb",
        }
        self.font_family = self._resolve_font_family()

        self.client_path_var = tk.StringVar()
        self.master_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar(value=str(Path("data") / "output_result.xlsx"))

        self.training_file_var = tk.StringVar()
        self.training_product_header_var = tk.StringVar(value="Product")
        self.training_category_header_var = tk.StringVar(value="Category")
        self.training_hsn_header_var = tk.StringVar(value="HSN Code")

        self.mapping_log_text: tk.Text | None = None
        self.training_log_text: tk.Text | None = None

        self.status_var = tk.StringVar(value="Ready")
        self._status_base_text = "Ready"
        self._status_spinner_job: str | None = None
        self._status_spinner_step = 0

        self.progress_bar: ttk.Progressbar | None = None

        self.hero_canvas: tk.Canvas | None = None
        self._hero_blobs: list[dict] = []
        self._hero_anim_job: str | None = None

        self._configure_theme()
        self._build_ui()
        self._start_hero_animation()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_theme(self) -> None:
        self.root.configure(bg=self.colors["bg"])
        self.root.option_add("*Font", (self.font_family, 10))
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=self.colors["bg"])
        style.configure("Card.TFrame", background=self.colors["surface"], relief="flat")
        style.configure("Header.TLabel", background=self.colors["bg"], foreground=self.colors["ink"], font=(self.font_family, 21, "bold"))
        style.configure("SubHeader.TLabel", background=self.colors["bg"], foreground=self.colors["muted"], font=(self.font_family, 10))
        style.configure("Status.TLabel", background=self.colors["bg"], foreground=self.colors["mint"], font=(self.font_family, 10, "bold"))
        style.configure("SectionTitle.TLabel", background=self.colors["surface"], foreground=self.colors["ink"], font=(self.font_family, 11, "bold"))
        style.configure("TLabel", background=self.colors["surface"], foreground=self.colors["ink"], font=(self.font_family, 10))
        style.configure(
            "TEntry",
            fieldbackground="#fffdfc",
            foreground=self.colors["ink"],
            bordercolor="#f0d2c5",
            lightcolor="#f0d2c5",
            darkcolor="#f0d2c5",
            padding=(10, 8),
            relief="flat",
        )
        style.configure(
            "Accent.TButton",
            background=self.colors["accent"],
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            focuscolor=self.colors["accent"],
            padding=(14, 9),
            font=(self.font_family, 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#ff9269"), ("disabled", "#e2c7bb")])
        style.configure(
            "Soft.TButton",
            background=self.colors["accent_soft"],
            foreground=self.colors["ink"],
            borderwidth=0,
            focusthickness=0,
            focuscolor=self.colors["accent_soft"],
            padding=(12, 9),
            font=(self.font_family, 9, "bold"),
        )
        style.map("Soft.TButton", background=[("active", "#ffdcca"), ("disabled", "#efe6e1")])
        style.configure(
            "TNotebook",
            background=self.colors["bg"],
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#f7ddd2",
            foreground=self.colors["ink"],
            font=(self.font_family, 10, "bold"),
            padding=(20, 10),
        )
        style.map("TNotebook.Tab", background=[("selected", self.colors["surface"]), ("active", "#fce5db")])
        style.configure("Card.TLabelframe", background=self.colors["surface"], bordercolor=self.colors["line"], borderwidth=1, relief="flat")
        style.configure("Card.TLabelframe.Label", background=self.colors["surface"], foreground=self.colors["ink"], font=(self.font_family, 10, "bold"))
        style.configure(
            "Cute.Horizontal.TProgressbar",
            background=self.colors["accent"],
            troughcolor="#ffe9df",
            bordercolor="#ffe9df",
            lightcolor=self.colors["accent"],
            darkcolor=self.colors["accent"],
            thickness=10,
        )

    def _resolve_font_family(self) -> str:
        self._load_local_hanken_font_if_available()
        families = {name.lower(): name for name in tkfont.families(self.root)}
        preferred = [
            "Hanken Grotesk",
            "HankenGrotesk",
            "Hanken Grotesk SemiBold",
            "Segoe UI",
            "Calibri",
        ]
        for name in preferred:
            if name.lower() in families:
                return families[name.lower()]
        return "TkDefaultFont"

    def _load_local_hanken_font_if_available(self) -> None:
        if os.name != "nt":
            return

        font_candidates = [
            Path("assets") / "fonts" / "HankenGrotesk-VariableFont_wght.ttf",
            Path("assets") / "fonts" / "HankenGrotesk-Regular.ttf",
            Path("assets") / "fonts" / "HankenGrotesk-Medium.ttf",
        ]

        gdi_add_font = ctypes.windll.gdi32.AddFontResourceExW
        fr_private = 0x10

        for path in font_candidates:
            try:
                abs_path = path.resolve()
            except OSError:
                continue
            if not abs_path.exists():
                continue
            gdi_add_font(str(abs_path), fr_private, 0)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, style="App.TFrame", padding=14)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        top = ttk.Frame(container, style="App.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        self.hero_canvas = tk.Canvas(top, height=120, highlightthickness=0, bg=self.colors["bg"])
        self.hero_canvas.grid(row=0, column=0, sticky="ew", padx=(0, 0), pady=(0, 8))

        title_holder = ttk.Frame(top, style="App.TFrame")
        title_holder.place(relx=0.02, rely=0.16)
        ttk.Label(title_holder, text="GST HSN Resolver", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            title_holder,
            text="Offline GST mapping with separate AI training and backupable learning memory",
            style="SubHeader.TLabel",
        ).pack(anchor="w")

        status_row = ttk.Frame(container, style="App.TFrame")
        status_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        status_row.columnconfigure(1, weight=1)
        ttk.Label(status_row, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(status_row, mode="indeterminate", style="Cute.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=(12, 0))

        notebook = ttk.Notebook(container)
        notebook.grid(row=2, column=0, sticky="nsew")

        mapping_tab = ttk.Frame(notebook, style="Card.TFrame", padding=14)
        training_tab = ttk.Frame(notebook, style="Card.TFrame", padding=14)
        notebook.add(mapping_tab, text="Mapping")
        notebook.add(training_tab, text="AI Training")

        self._build_mapping_tab(mapping_tab)
        self._build_training_tab(training_tab)

    def _start_hero_animation(self) -> None:
        if self.hero_canvas is None:
            return
        width = max(self.hero_canvas.winfo_width(), 800)
        self.hero_canvas.delete("all")
        self._hero_blobs = [
            {"x": 120.0, "y": 60.0, "r": 54.0, "dx": 0.6, "dy": 0.3, "color": "#ffe4d8"},
            {"x": 340.0, "y": 42.0, "r": 42.0, "dx": -0.4, "dy": 0.25, "color": "#ffd7c8"},
            {"x": 600.0, "y": 66.0, "r": 50.0, "dx": 0.35, "dy": -0.2, "color": "#ffe9dc"},
            {"x": float(width - 140), "y": 48.0, "r": 44.0, "dx": -0.5, "dy": 0.22, "color": "#ffe0d1"},
        ]
        self._animate_hero()

    def _animate_hero(self) -> None:
        if self.hero_canvas is None:
            return

        canvas = self.hero_canvas
        width = max(canvas.winfo_width(), 800)
        height = max(canvas.winfo_height(), 120)
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, height, fill=self.colors["bg"], outline=self.colors["bg"])

        for blob in self._hero_blobs:
            blob["x"] += blob["dx"]
            blob["y"] += blob["dy"]
            if blob["x"] - blob["r"] < 0 or blob["x"] + blob["r"] > width:
                blob["dx"] *= -1
            if blob["y"] - blob["r"] < 0 or blob["y"] + blob["r"] > height:
                blob["dy"] *= -1
            jitter = random.uniform(-0.3, 0.3)
            blob["dy"] += jitter * 0.03
            blob["dy"] = max(min(blob["dy"], 0.8), -0.8)

            canvas.create_oval(
                blob["x"] - blob["r"],
                blob["y"] - blob["r"],
                blob["x"] + blob["r"],
                blob["y"] + blob["r"],
                fill=blob["color"],
                outline="",
            )

        self._hero_anim_job = self.root.after(40, self._animate_hero)

    def _build_mapping_tab(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="Map your client file to GST HSN with confidence-safe output", style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        self._add_file_row(
            frame,
            row=1,
            label_text="Client Input (CSV/XLSX)",
            variable=self.client_path_var,
            select_command=self._browse_client,
        )
        self._add_file_row(
            frame,
            row=2,
            label_text="HSN Master (CSV/XLSX)",
            variable=self.master_path_var,
            select_command=self._browse_master,
        )
        self._add_file_row(
            frame,
            row=3,
            label_text="Output File (.xlsx/.csv)",
            variable=self.output_path_var,
            select_command=self._browse_output,
        )

        action_frame = ttk.Frame(frame)
        action_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 8))
        action_frame.columnconfigure(5, weight=1)

        self.run_btn = ttk.Button(action_frame, text="Run Mapping", style="Accent.TButton", command=self._on_run)
        self.run_btn.grid(row=0, column=0, padx=(0, 8))

        self.download_btn = ttk.Button(
            action_frame,
            text="Download Official HSN",
            style="Soft.TButton",
            command=self._on_download_master,
        )
        self.download_btn.grid(row=0, column=1, padx=(0, 8))

        self.open_btn = ttk.Button(
            action_frame,
            text="Open Output",
            style="Soft.TButton",
            command=self._open_output,
            state="disabled",
        )
        self.open_btn.grid(row=0, column=2, padx=(0, 8))

        ttk.Button(action_frame, text="Clear Mapping Log", style="Soft.TButton", command=self._clear_mapping_log).grid(row=0, column=3)

        log_box = ttk.LabelFrame(frame, text="Mapping Log", style="Card.TLabelframe", padding=8)
        log_box.grid(row=5, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(5, weight=1)
        frame.columnconfigure(1, weight=1)

        self.mapping_log_text = tk.Text(
            log_box,
            height=20,
            wrap="word",
            font=("Consolas", 10),
            bg="#fffdfa",
            fg="#3e2f3e",
            insertbackground="#3e2f3e",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=8,
        )
        self.mapping_log_text.pack(fill="both", expand=True)

    def _build_training_tab(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="Train AI memory with your files plus Google-discovered web practice", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        action_row = ttk.Frame(frame)
        action_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        action_row.columnconfigure(4, weight=1)

        self.train_btn = ttk.Button(action_row, text="Run AI Training Mode", style="Accent.TButton", command=self._on_training_mode)
        self.train_btn.grid(row=0, column=0, padx=(0, 8))

        self.backup_btn = ttk.Button(action_row, text="Backup Training", style="Soft.TButton", command=self._on_backup)
        self.backup_btn.grid(row=0, column=1, padx=(0, 8))

        self.restore_btn = ttk.Button(action_row, text="Restore Training", style="Soft.TButton", command=self._on_restore)
        self.restore_btn.grid(row=0, column=2, padx=(0, 8))

        ttk.Button(action_row, text="Clear Training Log", style="Soft.TButton", command=self._clear_training_log).grid(row=0, column=3)

        import_box = ttk.LabelFrame(frame, text="Learn From Your Excel/CSV", style="Card.TLabelframe", padding=8)
        import_box.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        import_box.columnconfigure(1, weight=1)

        ttk.Label(import_box, text="Training file").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(import_box, textvariable=self.training_file_var).grid(row=0, column=1, sticky="ew", padx=(8, 8), pady=4)
        ttk.Button(import_box, text="Browse", command=self._browse_training_file).grid(row=0, column=2, pady=4)

        ttk.Label(import_box, text="Product header").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(import_box, textvariable=self.training_product_header_var).grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=4)

        ttk.Label(import_box, text="Category header").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(import_box, textvariable=self.training_category_header_var).grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=4)

        ttk.Label(import_box, text="HSN header").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(import_box, textvariable=self.training_hsn_header_var).grid(row=3, column=1, sticky="ew", padx=(8, 8), pady=4)

        ttk.Button(import_box, text="Import To AI Memory", style="Accent.TButton", command=self._on_import_training_file).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 2)
        )

        info = (
            "Example headers from your sheet: Product, Category, HSN Code. "
            "Set header names exactly as in file before import."
        )
        ttk.Label(import_box, text=info, foreground=self.colors["muted"]).grid(row=5, column=0, columnspan=3, sticky="w")

        log_box = ttk.LabelFrame(frame, text="AI Training Log", style="Card.TLabelframe", padding=8)
        log_box.grid(row=3, column=0, sticky="nsew")
        frame.rowconfigure(3, weight=1)
        frame.columnconfigure(0, weight=1)

        self.training_log_text = tk.Text(
            log_box,
            height=20,
            wrap="word",
            font=("Consolas", 10),
            bg="#fffdfa",
            fg="#3e2f3e",
            insertbackground="#3e2f3e",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=8,
        )
        self.training_log_text.pack(fill="both", expand=True)

    def _add_file_row(
        self,
        parent: ttk.Frame,
        row: int,
        label_text: str,
        variable: tk.StringVar,
        select_command,
    ) -> None:
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", pady=6)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 8), pady=6)
        parent.columnconfigure(1, weight=1)
        ttk.Button(parent, text="Browse", style="Soft.TButton", command=select_command).grid(row=row, column=2, pady=6)

    def _append_mapping_log(self, message: str) -> None:
        if self.mapping_log_text is None:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self.mapping_log_text.insert("end", f"[{stamp}] {message}\n")
        self.mapping_log_text.see("end")

    def _append_training_log(self, message: str) -> None:
        if self.training_log_text is None:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self.training_log_text.insert("end", f"[{stamp}] {message}\n")
        self.training_log_text.see("end")

    def _clear_mapping_log(self) -> None:
        if self.mapping_log_text is not None:
            self.mapping_log_text.delete("1.0", "end")

    def _clear_training_log(self) -> None:
        if self.training_log_text is not None:
            self.training_log_text.delete("1.0", "end")

    def _browse_client(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Client Input File",
            filetypes=[("Data Files", "*.csv *.xlsx *.xls"), ("All Files", "*.*")],
        )
        if path:
            self.client_path_var.set(path)

    def _browse_master(self) -> None:
        path = filedialog.askopenfilename(
            title="Select HSN Master File",
            filetypes=[("Data Files", "*.csv *.xlsx *.xls"), ("All Files", "*.*")],
        )
        if path:
            self.master_path_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose Output File",
            defaultextension=".xlsx",
            initialfile="output_result.xlsx",
            filetypes=[("Excel File", "*.xlsx"), ("CSV File", "*.csv")],
        )
        if path:
            self.output_path_var.set(path)

    def _browse_training_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Training Excel/CSV",
            filetypes=[("Data Files", "*.csv *.xlsx *.xls"), ("All Files", "*.*")],
        )
        if path:
            self.training_file_var.set(path)

    def _validate_inputs(self) -> tuple[Path, Path, Path] | None:
        client = Path(self.client_path_var.get().strip())
        master = Path(self.master_path_var.get().strip())
        output = Path(self.output_path_var.get().strip())

        if not client:
            messagebox.showerror("Missing File", "Please select client input file.")
            return None
        if not master:
            messagebox.showerror("Missing File", "Please select HSN master file.")
            return None
        if not output:
            messagebox.showerror("Missing File", "Please select output file.")
            return None
        if not client.exists():
            messagebox.showerror("File Not Found", f"Client file not found:\n{client}")
            return None
        if not master.exists():
            messagebox.showerror("File Not Found", f"HSN master file not found:\n{master}")
            return None

        if output.suffix.lower() not in {".xlsx", ".csv"}:
            output = output.with_suffix(".xlsx")
            self.output_path_var.set(str(output))

        return client, master, output

    def _set_running(self, running: bool) -> None:
        self.run_btn.configure(state="disabled" if running else "normal")
        self.download_btn.configure(state="disabled" if running else "normal")
        self.open_btn.configure(state="disabled" if running else self.open_btn.cget("state"))
        self.train_btn.configure(state="disabled" if running else "normal")
        self.backup_btn.configure(state="disabled" if running else "normal")
        self.restore_btn.configure(state="disabled" if running else "normal")
        if self.progress_bar is not None:
            if running:
                self.progress_bar.start(12)
                self._start_status_spinner()
            else:
                self.progress_bar.stop()
                self._stop_status_spinner()

    def _set_status(self, text: str) -> None:
        self._status_base_text = text
        self.status_var.set(text)

    def _start_status_spinner(self) -> None:
        if self._status_spinner_job is not None:
            return
        self._status_spinner_step = 0
        self._tick_status_spinner()

    def _tick_status_spinner(self) -> None:
        dots = "." * ((self._status_spinner_step % 3) + 1)
        self.status_var.set(f"{self._status_base_text}{dots}")
        self._status_spinner_step += 1
        self._status_spinner_job = self.root.after(360, self._tick_status_spinner)

    def _stop_status_spinner(self) -> None:
        if self._status_spinner_job is not None:
            self.root.after_cancel(self._status_spinner_job)
            self._status_spinner_job = None
        self.status_var.set(self._status_base_text)

    def _on_run(self) -> None:
        validated = self._validate_inputs()
        if validated is None:
            return

        client, master, output = validated
        self._set_running(True)
        self._set_status("Running mapping")
        self._append_mapping_log("Started processing.")
        self._append_mapping_log(f"Client input: {client}")
        self._append_mapping_log(f"HSN master: {master}")
        self._append_mapping_log(f"Output: {output}")

        thread = threading.Thread(target=self._run_worker, args=(client, master, output), daemon=True)
        thread.start()

    def _run_worker(self, client: Path, master: Path, output: Path) -> None:
        try:
            summary = run_pipeline(client, master, output)
            self.root.after(0, lambda: self._on_success(summary))
        except Exception as exc:
            trace = traceback.format_exc()
            self.root.after(0, lambda e=exc, t=trace: self._on_failure(e, t, channel="mapping"))

    def _on_success(self, summary: dict) -> None:
        self._set_running(False)
        self.open_btn.configure(state="normal")
        self._set_status("Completed successfully")
        actual_output = str(summary.get("output_path", "")).strip()
        if actual_output:
            self.output_path_var.set(actual_output)
        self._append_mapping_log("Processing completed.")
        self._append_mapping_log(f"Total rows: {summary.get('total_rows', 0)}")
        self._append_mapping_log(f"Unique normalized products: {summary.get('unique_products', 0)}")
        self._append_mapping_log(f"Learned exact hits: {summary.get('learned_exact_hits', 0)}")
        self._append_mapping_log(f"Learned fuzzy hits: {summary.get('learned_fuzzy_hits', 0)}")
        self._append_mapping_log(f"New learning records saved: {summary.get('learned_saved', 0)}")
        self._append_mapping_log(f"Auto approved: {summary.get('auto_approved_rows', 0)}")
        self._append_mapping_log(f"Review queue: {summary.get('review_rows', 0)}")
        if actual_output:
            self._append_mapping_log(f"Saved output: {actual_output}")
        messagebox.showinfo(
            "Done",
            "HSN mapping completed successfully.\n"
            f"Rows: {summary.get('total_rows', 0)}\n"
            f"Review queue: {summary.get('review_rows', 0)}\n"
            f"Output: {actual_output}",
        )

    def _on_download_master(self) -> None:
        suggested = Path("data") / "hsn_master_from_gst.csv"
        path = filedialog.asksaveasfilename(
            title="Save Local HSN Master",
            defaultextension=".csv",
            initialfile=suggested.name,
            initialdir=str(suggested.parent),
            filetypes=[("CSV file", "*.csv")],
        )
        if not path:
            return

        output_csv = Path(path)
        self._set_running(True)
        self._set_status("Downloading official HSN directory")
        self._append_mapping_log("Downloading official GST HSN directory file.")

        thread = threading.Thread(target=self._download_worker, args=(output_csv,), daemon=True)
        thread.start()

    def _download_worker(self, output_csv: Path) -> None:
        try:
            count = download_and_build_master(output_csv)
            self.root.after(0, lambda: self._on_download_success(output_csv, count))
        except Exception as exc:
            trace = traceback.format_exc()
            self.root.after(0, lambda e=exc, t=trace: self._on_failure(e, t, channel="mapping"))

    def _on_download_success(self, output_csv: Path, count: int) -> None:
        self._set_running(False)
        self._set_status("Official HSN master ready")
        self.master_path_var.set(str(output_csv))
        self._append_mapping_log(f"Master created: {output_csv}")
        self._append_mapping_log(f"8-digit HSN rows: {count}")
        messagebox.showinfo(
            "HSN Master Ready",
            f"Downloaded and built local HSN master.\nRows: {count}\nFile: {output_csv}",
        )

    def _on_training_mode(self) -> None:
        self._set_running(True)
        self._set_status("AI Training Mode running")
        self._append_training_log("Training mode started.")

        master = Path(self.master_path_var.get().strip()) if self.master_path_var.get().strip() else None
        thread = threading.Thread(target=self._training_worker, args=(master,), daemon=True)
        thread.start()

    def _training_worker(self, master: Path | None) -> None:
        try:
            summary = run_training_mode(master, logger=lambda m: self.root.after(0, lambda: self._append_training_log(m)))
            self.root.after(0, lambda: self._on_training_success(summary))
        except Exception as exc:
            trace = traceback.format_exc()
            self.root.after(0, lambda e=exc, t=trace: self._on_failure(e, t, channel="training"))

    def _on_training_success(self, summary: dict) -> None:
        self._set_running(False)
        self._set_status("Training mode completed")
        self._append_training_log("Training mode completed.")
        self._append_training_log(f"Snapshot source: {summary.get('source_mode', '')}")
        self._append_training_log(f"Snapshot master: {summary.get('snapshot_master', '')}")
        self._append_training_log(f"Google queries used: {summary.get('google_queries_used', 0)}")
        self._append_training_log(f"Product names used for Google queries: {summary.get('google_product_names_used', 0)}")
        self._append_training_log(f"Google URLs discovered: {summary.get('google_urls_discovered', 0)}")
        self._append_training_log(f"Google discovered list: {summary.get('google_discovered_file', '')}")
        self._append_training_log(f"Web pages visited: {summary.get('web_pages_visited', 0)}")
        self._append_training_log(f"Web pairs collected: {summary.get('web_pairs_collected', 0)}")
        self._append_training_log(f"Filtered irrelevant links: {summary.get('web_filtered_links', 0)}")
        self._append_training_log(f"Timed out by budget: {summary.get('web_timed_out', False)}")
        self._append_training_log(f"Practice file: {summary.get('practice_file', '')}")
        self._append_training_log(f"Practice rows: {summary.get('practice_rows', 0)}")
        self._append_training_log(f"Corpus file: {summary.get('corpus_file', '')}")
        self._append_training_log(f"Corpus rows: {summary.get('corpus_rows', 0)}")
        self._append_training_log(f"Corpus size (MB): {summary.get('corpus_size_mb', 0)}")
        messagebox.showinfo(
            "Training Mode Done",
            "AI training mode completed.\n"
            f"Google queries: {summary.get('google_queries_used', 0)}\n"
            f"Products used in Google queries: {summary.get('google_product_names_used', 0)}\n"
            f"Google URLs discovered: {summary.get('google_urls_discovered', 0)}\n"
            f"Web pairs: {summary.get('web_pairs_collected', 0)}\n"
            f"Filtered links: {summary.get('web_filtered_links', 0)}\n"
            f"Timed out by budget: {summary.get('web_timed_out', False)}\n"
            f"Practice rows: {summary.get('practice_rows', 0)}\n"
            f"Corpus rows: {summary.get('corpus_rows', 0)}\n"
            f"Corpus size MB: {summary.get('corpus_size_mb', 0)}",
        )

    def _on_import_training_file(self) -> None:
        file_path = self.training_file_var.get().strip()
        if not file_path:
            messagebox.showerror("Missing File", "Select a training Excel/CSV file first.")
            return

        path = Path(file_path)
        if not path.exists():
            messagebox.showerror("File Not Found", f"Training file not found:\n{path}")
            return

        product_header = self.training_product_header_var.get().strip()
        category_header = self.training_category_header_var.get().strip()
        hsn_header = self.training_hsn_header_var.get().strip()
        if not product_header or not hsn_header:
            messagebox.showerror("Missing Header", "Product header and HSN header are required.")
            return

        self._set_running(True)
        self._set_status("Importing training file")
        self._append_training_log(f"Training import started: {path}")
        self._append_training_log(
            f"Headers -> Product: {product_header}, Category: {category_header}, HSN: {hsn_header}"
        )

        thread = threading.Thread(
            target=self._import_training_worker,
            args=(path, product_header, category_header, hsn_header),
            daemon=True,
        )
        thread.start()

    def _import_training_worker(
        self,
        path: Path,
        product_header: str,
        category_header: str,
        hsn_header: str,
    ) -> None:
        try:
            result = import_learning_file(
                file_path=path,
                memory_csv_path=Path(LEARNING_DB_PATH),
                product_header=product_header,
                category_header=category_header,
                hsn_header=hsn_header,
            )
            self.root.after(0, lambda: self._on_import_training_success(result))
        except Exception as exc:
            trace = traceback.format_exc()
            self.root.after(0, lambda e=exc, t=trace: self._on_failure(e, t, channel="training"))

    def _on_import_training_success(self, result: dict) -> None:
        self._set_running(False)
        self._set_status("Training import completed")
        self._append_training_log("Training import completed.")
        self._append_training_log(f"File: {result.get('file', '')}")
        self._append_training_log(f"Total rows: {result.get('total_rows', 0)}")
        self._append_training_log(f"Usable rows: {result.get('usable_rows', 0)}")
        self._append_training_log(f"Saved rows: {result.get('saved_rows', 0)}")
        self._append_training_log(f"Skipped rows: {result.get('skipped_rows', 0)}")
        self._append_training_log(f"Learning DB: {LEARNING_DB_PATH}")
        messagebox.showinfo(
            "Training Import Done",
            "AI memory import completed.\n"
            f"Usable rows: {result.get('usable_rows', 0)}\n"
            f"Saved rows: {result.get('saved_rows', 0)}\n"
            f"Skipped rows: {result.get('skipped_rows', 0)}",
        )

    def _on_backup(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save Training Backup",
            defaultextension=".zip",
            initialfile="gst_training_backup.zip",
            filetypes=[("Zip file", "*.zip")],
        )
        if not path:
            return

        backup_path = backup_training_state(Path(path))
        self._append_training_log(f"Backup created: {backup_path}")
        messagebox.showinfo("Backup Created", f"Training backup saved:\n{backup_path}")

    def _on_restore(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Training Backup Zip",
            filetypes=[("Zip file", "*.zip")],
        )
        if not path:
            return

        result = restore_training_state(Path(path))
        self._append_training_log(f"Backup restored: {result.get('backup', '')}")
        self._append_training_log(f"Files restored: {result.get('files_restored', 0)}")
        messagebox.showinfo(
            "Restore Completed",
            f"Training state restored.\nFiles restored: {result.get('files_restored', 0)}",
        )

    def _on_failure(self, exc: Exception, trace: str, channel: str) -> None:
        self._set_running(False)
        self._set_status("Failed")
        if channel == "training":
            self._append_training_log(f"Error: {exc}")
            self._append_training_log(trace)
        else:
            self._append_mapping_log(f"Error: {exc}")
            self._append_mapping_log(trace)
        messagebox.showerror("Operation Failed", f"Processing failed:\n{exc}")

    def _open_output(self) -> None:
        output = Path(self.output_path_var.get().strip())
        if not output.exists():
            messagebox.showwarning("File Missing", "Output file not found yet.")
            return
        os.startfile(str(output))

    def _on_close(self) -> None:
        if self._hero_anim_job is not None:
            self.root.after_cancel(self._hero_anim_job)
            self._hero_anim_job = None
        if self._status_spinner_job is not None:
            self.root.after_cancel(self._status_spinner_job)
            self._status_spinner_job = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    GstHsnApp(root)
    root.mainloop()
