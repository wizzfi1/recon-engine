import os
import sys
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

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
BACKGROUND = "#F5F7F6"
TEXT_MUTED = "#4B5563"

FOOTER_TEXT = f"© 2026 {COMPANY_NAME} · Internal Finance System · {VERSION}"
# =================================================


class ReconApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")

        self.title(f"{COMPANY_NAME} — {APP_NAME}")
        self.geometry("780x740")
        self.resizable(False, False)

        self.input_file = None
        self.output_dir = None
        self.output_path = None
        self.cancel_requested = False

        self._build_ui()

    # ==========================================================
    # UI
    # ==========================================================
    def _build_ui(self):
        container = ttk.Frame(self, padding=24)
        container.pack(fill=BOTH, expand=True)

        # Header
        ttk.Label(
            container,
            text=COMPANY_NAME,
            font=("Segoe UI", 16, "bold"),
            foreground=PRIMARY_GREEN,
        ).pack(anchor=W)

        ttk.Label(
            container,
            text=f"{APP_NAME} · {DEPARTMENT_NAME}",
            font=("Segoe UI", 10),
            foreground=TEXT_MUTED,
        ).pack(anchor=W)

        ttk.Separator(container).pack(fill=X, pady=14)

        # ---------- File selection ----------
        file_frame = ttk.Frame(container)
        file_frame.pack(fill=X, pady=10)

        self.file_label = ttk.Label(file_frame, text="No file selected")
        self.file_label.pack(side=LEFT, fill=X, expand=True)

        ttk.Button(
            file_frame,
            text="Choose Excel File",
            command=self.browse_file,
            bootstyle="secondary",
        ).pack(side=RIGHT)

        # ---------- Output folder ----------
        ttk.Label(container, text="Output Folder", font=("Segoe UI", 10, "bold")).pack(
            anchor=W, pady=(20, 6)
        )

        folder_frame = ttk.Frame(container)
        folder_frame.pack(fill=X)

        self.output_folder_label = ttk.Label(
            folder_frame,
            text="Same folder as input file",
            foreground=TEXT_MUTED,
        )
        self.output_folder_label.pack(side=LEFT, fill=X, expand=True)

        ttk.Button(
            folder_frame,
            text="Change",
            command=self.choose_output_folder,
            bootstyle="secondary",
        ).pack(side=RIGHT)

        # ---------- Output filename ----------
        ttk.Label(container, text="Output File Name", font=("Segoe UI", 10, "bold")).pack(
            anchor=W, pady=(20, 6)
        )

        self.filename_entry = ttk.Entry(container)
        self.filename_entry.pack(fill=X)
        self.filename_entry.insert(0, DEFAULT_OUTPUT_BASENAME)

        self.timestamp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            container,
            text="Append timestamp to filename",
            variable=self.timestamp_var,
            bootstyle="success",
        ).pack(anchor=W, pady=6)

        # ---------- Run / Cancel ----------
        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=24)

        self.run_btn = ttk.Button(
            btn_frame,
            text="Run Reconciliation",
            command=self.start_reconciliation,
            bootstyle="success",
            state=DISABLED,
        )
        self.run_btn.pack(side=LEFT, padx=10)

        self.cancel_btn = ttk.Button(
            btn_frame,
            text="Cancel",
            command=self.request_cancel,
            bootstyle="danger",
            state=DISABLED,
        )
        self.cancel_btn.pack(side=LEFT, padx=10)

        self.progress = ttk.Progressbar(container, mode="indeterminate", length=500)
        self.progress.pack(pady=10)

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

        ttk.Separator(container).pack(fill=X, pady=20)
        ttk.Label(container, text=FOOTER_TEXT, font=("Segoe UI", 9)).pack()

    # ==========================================================
    # Actions
    # ==========================================================
    def browse_file(self):
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

    def confirm_large_file(self):
        import pandas as pd

        try:
            rows = pd.read_excel(self.input_file, sheet_name=0).shape[0]
        except Exception:
            return True

        if rows >= 10000:
            return messagebox.askyesno(
                "Large File Warning",
                f"This workbook contains approximately {rows:,} rows.\n\n"
                "Processing may take several minutes.\n\n"
                "Do you want to continue?",
            )
        return True

    def start_reconciliation(self):
        if not self.confirm_large_file():
            self.status.config(text="Status: Cancelled by user")
            return

        self.cancel_requested = False
        self.run_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_folder_btn.config(state=DISABLED)
        self.progress.start(10)

        threading.Thread(target=self.run_reconciliation).start()

    def request_cancel(self):
        self.cancel_requested = True
        self.status.config(text="Status: Cancelling…")

    def update_status(self, msg):
        self.status.config(text=f"Status: {msg}")
        self.status.update_idletasks()

    def run_reconciliation(self):
        try:
            self.after(0, lambda: self.update_status("Loading Excel data…"))
            pastel = load_excel(self.input_file, PASTEL_SHEET)
            ixtrac = load_excel(self.input_file, IXTRAC_SHEET)

            if self.cancel_requested:
                self.after(0, self.on_cancelled)
                return

            self.after(0, lambda: self.update_status("Reconciling (netting & matching)…"))
            results = run_reconciliation(pastel, ixtrac)

            if self.cancel_requested:
                self.after(0, self.on_cancelled)
                return

            self.after(0, lambda: self.update_status("Writing output workbook…"))

            base = self.filename_entry.get().strip() or DEFAULT_OUTPUT_BASENAME
            ts = datetime.now().strftime("%Y%m%d_%H%M%S") if self.timestamp_var.get() else ""
            name = f"{base}_{ts}.xlsx" if ts else f"{base}.xlsx"

            self.output_path = os.path.join(self.output_dir, name)
            write_excel(self.output_path, *results)

            self.after(0, self.on_success)

        except Exception as e:
            self.after(0, lambda: self.on_error(e))

    def on_success(self):
        self.progress.stop()
        self.cancel_btn.config(state=DISABLED)
        self.run_btn.config(state=NORMAL)
        self.open_folder_btn.config(state=NORMAL)
        self.status.config(text="Status: Completed successfully")
        messagebox.showinfo("Completed", f"Output saved to:\n{self.output_path}")

    def on_cancelled(self):
        self.progress.stop()
        self.cancel_btn.config(state=DISABLED)
        self.run_btn.config(state=NORMAL)
        self.status.config(text="Status: Cancelled")
        messagebox.showwarning("Cancelled", "Reconciliation was cancelled.")

    def on_error(self, error):
        self.progress.stop()
        self.cancel_btn.config(state=DISABLED)
        self.run_btn.config(state=NORMAL)
        self.status.config(text="Status: Error occurred")
        messagebox.showerror("Error", str(error))

    def open_output_folder(self):
        if self.output_path:
            folder = os.path.dirname(self.output_path)
            os.startfile(folder)


if __name__ == "__main__":
    app = ReconApp()
    app.mainloop()
