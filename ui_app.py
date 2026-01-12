import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import os
import threading
import sys
from datetime import datetime

from core.loaders import load_excel
from core.reconciler import run_reconciliation
from outputs.writer import write_excel
from config import PASTEL_SHEET, IXTRAC_SHEET

# ================= BRAND CONFIG =================
COMPANY_NAME = "Greenwich Registrars and Data Solutions"
DEPARTMENT_NAME = "Finance & Accounts"
APP_NAME = "Reconciliation Engine"
VERSION = "v1.0.0"

DEFAULT_OUTPUT_BASENAME = "RECONCILIATION_OUTPUT"

PRIMARY_GREEN = "#1E6F3D"
SECONDARY_GREEN = "#6FBF8F"
BACKGROUND = "#F5F7F6"
TEXT_MUTED = "#4B5563"

FOOTER_TEXT = f"© 2026 {COMPANY_NAME} · Internal Finance System · {VERSION}"
# =================================================


def resource_path(relative_path):
    """Resolve paths correctly for PyInstaller and normal runs"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ReconApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")

        self.title(f"{COMPANY_NAME} — {APP_NAME}")
        self.geometry("760x640")
        self.resizable(False, False)

        # ---------- Window icon ----------
        icon_path = resource_path("assets/app.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # ---------- ttkbootstrap styles ----------
        style = ttk.Style()
        style.configure("Brand.TFrame", background=BACKGROUND)
        style.configure(
            "BrandTitle.TLabel",
            font=("Segoe UI", 16, "bold"),
            foreground=PRIMARY_GREEN,
            background=BACKGROUND,
        )
        style.configure(
            "BrandSub.TLabel",
            font=("Segoe UI", 10),
            foreground=TEXT_MUTED,
            background=BACKGROUND,
        )
        style.configure(
            "Footer.TLabel",
            font=("Segoe UI", 9),
            foreground="#6B7280",
            background=BACKGROUND,
        )

        # ---------- State ----------
        self.input_file = None
        self.output_dir = None
        self.output_path = None

        self._build_ui()

    # ==========================================================
    # UI
    # ==========================================================
    def _build_ui(self):
        container = ttk.Frame(self, style="Brand.TFrame", padding=24)
        container.pack(fill=BOTH, expand=True)

        # ---------- Header ----------
        header = ttk.Frame(container, style="Brand.TFrame")
        header.pack(fill=X)

        logo_path = resource_path("assets/logo.png")
        if os.path.exists(logo_path):
            self.logo_img = tk.PhotoImage(file=logo_path)
            ttk.Label(header, image=self.logo_img, style="Brand.TFrame").pack(
                side=LEFT, padx=(0, 16)
            )

        title_block = ttk.Frame(header, style="Brand.TFrame")
        title_block.pack(side=LEFT)

        ttk.Label(
            title_block, text=COMPANY_NAME, style="BrandTitle.TLabel"
        ).pack(anchor=W)

        ttk.Label(
            title_block,
            text=f"{APP_NAME} · {DEPARTMENT_NAME}",
            style="BrandSub.TLabel",
        ).pack(anchor=W)

        ttk.Separator(container).pack(fill=X, pady=14)

        ttk.Label(
            container,
            text="Pastel ↔ IX TRAC Reconciliation Tool",
            font=("Segoe UI", 11),
        ).pack(pady=(0, 18))

        # ---------- Drop zone ----------
        drop = tk.Frame(
            container,
            bg=SECONDARY_GREEN,
            highlightbackground=PRIMARY_GREEN,
            highlightthickness=2,
            height=90,
        )
        drop.pack(fill=X, pady=10)

        self.file_label = tk.Label(
            drop,
            text="Click to browse",
            bg=SECONDARY_GREEN,
            fg="white",
            font=("Segoe UI", 11),
            justify="center",
        )
        self.file_label.pack(expand=True)

        drop.bind("<Button-1>", self.browse_file)
        self.file_label.bind("<Button-1>", self.browse_file)

        # ---------- Output folder ----------
        ttk.Label(
            container, text="Output Folder", font=("Segoe UI", 10, "bold")
        ).pack(pady=(24, 6))

        folder_frame = ttk.Frame(container)
        folder_frame.pack(fill=X)

        self.output_folder_label = ttk.Label(
            folder_frame, text="Same folder as input file"
        )
        self.output_folder_label.pack(side=LEFT, fill=X, expand=True)

        ttk.Button(
            folder_frame,
            text="Change",
            command=self.choose_output_folder,
            bootstyle="secondary",
        ).pack(side=RIGHT)

        # ---------- Output filename ----------
        ttk.Label(
            container, text="Output File Name", font=("Segoe UI", 10, "bold")
        ).pack(pady=(20, 6))

        self.filename_entry = ttk.Entry(container)
        self.filename_entry.pack(fill=X)
        self.filename_entry.insert(0, DEFAULT_OUTPUT_BASENAME)

        self.timestamp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            container,
            text="Append timestamp to filename",
            variable=self.timestamp_var,
            bootstyle="success",
        ).pack(pady=6)

        # ---------- Run ----------
        self.run_btn = ttk.Button(
            container,
            text="Run Reconciliation →",
            command=self.start_reconciliation,
            bootstyle="success",
            state=DISABLED,
        )
        self.run_btn.pack(pady=(30, 10))

        self.progress = ttk.Progressbar(container, mode="indeterminate", length=460)
        self.progress.pack(pady=6)

        self.status = ttk.Label(container, text="Status: Waiting for file")
        self.status.pack(pady=6)

        self.open_folder_btn = ttk.Button(
            container,
            text="Open Output Folder",
            command=self.open_output_folder,
            bootstyle="secondary",
            state=DISABLED,
        )
        self.open_folder_btn.pack(pady=(10, 0))

        ttk.Separator(container).pack(fill=X, pady=14)

        ttk.Label(container, text=FOOTER_TEXT, style="Footer.TLabel").pack()

    # ==========================================================
    # Actions
    # ==========================================================
    def browse_file(self, event=None):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if not path:
            return

        self.input_file = path
        self.file_label.config(text=os.path.basename(path))
        self.run_btn.config(state=NORMAL)
        self.status.config(text="Status: File loaded — ready to run")

        if not self.output_dir:
            self.output_dir = os.path.dirname(path)
            self.output_folder_label.config(text=self.output_dir)

    def choose_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir = folder
            self.output_folder_label.config(text=folder)

    def start_reconciliation(self):
        self.run_btn.config(state=DISABLED)
        self.open_folder_btn.config(state=DISABLED)
        self.progress.start(10)
        self.status.config(text="Status: Processing reconciliation…")

        threading.Thread(target=self.run_reconciliation).start()

    def run_reconciliation(self):
        try:
            pastel = load_excel(self.input_file, PASTEL_SHEET)
            ixtrac = load_excel(self.input_file, IXTRAC_SHEET)

            results = run_reconciliation(pastel, ixtrac)

            base = self.filename_entry.get().strip() or DEFAULT_OUTPUT_BASENAME
            ts = (
                datetime.now().strftime("%Y%m%d_%H%M%S")
                if self.timestamp_var.get()
                else ""
            )
            filename = f"{base}_{ts}.xlsx" if ts else f"{base}.xlsx"

            self.output_path = os.path.join(self.output_dir, filename)

            write_excel(self.output_path, *results)

            self.after(0, self.on_success)

        except Exception as e:
            self.after(0, lambda: self.on_error(e))

    def on_success(self):
        self.progress.stop()
        self.status.config(text="Status: Completed successfully")
        self.open_folder_btn.config(state=NORMAL)

        messagebox.showinfo(
            "Completed", f"Reconciliation completed.\n\nSaved to:\n{self.output_path}"
        )

    def on_error(self, error):
        self.progress.stop()
        self.run_btn.config(state=NORMAL)
        self.status.config(text="Status: Error occurred")
        messagebox.showerror("Error", str(error))

    def open_output_folder(self):
        if not self.output_path:
            return

        folder = os.path.dirname(self.output_path)
        if sys.platform.startswith("win"):
            os.startfile(folder)
        elif sys.platform.startswith("darwin"):
            os.system(f'open "{folder}"')
        else:
            os.system(f'xdg-open "{folder}"')


if __name__ == "__main__":
    app = ReconApp()
    app.mainloop()
