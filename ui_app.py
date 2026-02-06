import os
import sys
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import pandas as pd

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from core.loaders import load_excel
from core.reconciler import run_reconciliation
from outputs.writer import write_excel
from config import PASTEL_SHEET, IXTRAC_SHEET
from core.validators import annotate_errors, DataValidationError


# ================= BRAND CONFIG =================
COMPANY_NAME = "Greenwich Registrars and Data Solutions"
DEPARTMENT_NAME = "Finance & Accounts"
APP_NAME = "Reconciliation Engine"
VERSION = "v1.0.0"

DEFAULT_OUTPUT_BASENAME = "RECONCILIATION_OUTPUT"

PRIMARY_GREEN = "#1E6F3D"
TEXT_MUTED = "#4B5563"

FOOTER_TEXT = f"© 2026 {COMPANY_NAME} · Internal Finance System · {VERSION}"
# =================================================


# ================= PROGRESS MODEL =================
PROGRESS_STAGES = [
    ("LOAD", "Loading Excel data…"),
    ("VALIDATE", "Validating data…"),
    ("NETTING", "Internal netting…"),
    ("MATCHING", "External matching…"),
    ("REVIEW", "Reviewing & classifying results…"),
    ("WRITE", "Writing output workbook…"),
    ("DONE", "Completed successfully"),
]

STAGE_INDEX = {k: i for i, (k, _) in enumerate(PROGRESS_STAGES)}
TOTAL_STAGES = len(PROGRESS_STAGES) - 1
# ==================================================


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ReconApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")

        self.title(f"{COMPANY_NAME} — {APP_NAME}")
        self.geometry("780x780")
        self.resizable(False, False)

        try:
            self.iconbitmap(resource_path("assets/app.ico"))
        except Exception:
            pass

        self.input_file = None
        self.output_dir = None
        self.output_path = None
        self.cancel_requested = False
        self.workbook_sheets = []

        self._build_ui()

    # ==================================================
    # UI
    # ==================================================
    def _build_ui(self):
        container = ttk.Frame(self, padding=24)
        container.pack(fill=BOTH, expand=True)

        # Header
        header = ttk.Frame(container)
        header.pack(fill=X)

        try:
            logo = Image.open(resource_path("assets/logo.jpg")).resize((60, 60))
            self.logo_img = ImageTk.PhotoImage(logo)
            ttk.Label(header, image=self.logo_img).pack(side=LEFT, padx=(0, 12))
        except Exception:
            pass

        title = ttk.Frame(header)
        title.pack(side=LEFT)

        ttk.Label(
            title, text=COMPANY_NAME,
            font=("Segoe UI", 16, "bold"),
            foreground=PRIMARY_GREEN
        ).pack(anchor=W)

        ttk.Label(
            title, text=f"{APP_NAME} · {DEPARTMENT_NAME}",
            font=("Segoe UI", 10),
            foreground=TEXT_MUTED
        ).pack(anchor=W)

        ttk.Separator(container).pack(fill=X, pady=14)

        # File selection
        file_frame = ttk.Frame(container)
        file_frame.pack(fill=X, pady=10)

        self.file_label = ttk.Label(file_frame, text="No file selected")
        self.file_label.pack(side=LEFT, fill=X, expand=True)

        ttk.Button(
            file_frame, text="Choose Excel File",
            command=self.browse_file,
            bootstyle="secondary"
        ).pack(side=RIGHT)

        # Sheet mapping
        ttk.Label(
            container, text="Sheet Mapping",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor=W, pady=(10, 6))

        sheet_frame = ttk.Frame(container)
        sheet_frame.pack(fill=X)

        self.pastel_sheet_var = tk.StringVar()
        self.ixtrac_sheet_var = tk.StringVar()

        ttk.Label(sheet_frame, text="Pastel Sheet:").grid(row=0, column=0, sticky=W)
        self.pastel_combo = ttk.Combobox(
            sheet_frame, textvariable=self.pastel_sheet_var,
            state="readonly", width=30
        )
        self.pastel_combo.grid(row=0, column=1, padx=8)

        ttk.Label(sheet_frame, text="IXTRAC Sheet:").grid(row=0, column=2, sticky=W)
        self.ixtrac_combo = ttk.Combobox(
            sheet_frame, textvariable=self.ixtrac_sheet_var,
            state="readonly", width=30
        )
        self.ixtrac_combo.grid(row=0, column=3, padx=8)

        # Output folder
        ttk.Label(
            container, text="Output Folder",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor=W, pady=(20, 6))

        folder_frame = ttk.Frame(container)
        folder_frame.pack(fill=X)

        self.output_folder_label = ttk.Label(
            folder_frame, text="Same folder as input file",
            foreground=TEXT_MUTED
        )
        self.output_folder_label.pack(side=LEFT, fill=X, expand=True)

        ttk.Button(
            folder_frame, text="Change",
            command=self.choose_output_folder,
            bootstyle="secondary"
        ).pack(side=RIGHT)

        # Output filename
        ttk.Label(
            container, text="Output File Name",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor=W, pady=(20, 6))

        self.filename_entry = ttk.Entry(container)
        self.filename_entry.pack(fill=X)
        self.filename_entry.insert(0, DEFAULT_OUTPUT_BASENAME)

        self.timestamp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            container, text="Append timestamp to filename",
            variable=self.timestamp_var,
            bootstyle="success"
        ).pack(anchor=W, pady=6)

        # Buttons
        btns = ttk.Frame(container)
        btns.pack(pady=24)

        self.run_btn = ttk.Button(
            btns, text="Run Reconciliation",
            command=self.start_reconciliation,
            bootstyle="success", state=DISABLED
        )
        self.run_btn.pack(side=LEFT, padx=10)

        self.cancel_btn = ttk.Button(
            btns, text="Cancel",
            command=self.request_cancel,
            bootstyle="danger", state=DISABLED
        )
        self.cancel_btn.pack(side=LEFT, padx=10)

        # Progress
        self.progress = ttk.Progressbar(
            container, mode="determinate", length=500, maximum=100
        )
        self.progress.pack(pady=10)

        self.status = ttk.Label(container, text="Status: Waiting for file")
        self.status.pack(pady=6)

        self.open_folder_btn = ttk.Button(
            container, text="Open Output Folder",
            command=self.open_output_folder,
            bootstyle="secondary", state=DISABLED
        )
        self.open_folder_btn.pack(pady=(10, 0))

        ttk.Separator(container).pack(fill=X, pady=20)
        ttk.Label(container, text=FOOTER_TEXT, font=("Segoe UI", 9)).pack()

    # ==================================================
    # Progress helpers
    # ==================================================
    def set_stage(self, stage_key):
        idx = STAGE_INDEX.get(stage_key, 0)
        percent = int((idx / TOTAL_STAGES) * 100)

        msg = dict(PROGRESS_STAGES)[stage_key]

        self.after(0, lambda: (
            self.status.config(text=f"Status: {msg}"),
            self.progress.configure(value=percent)
        ))

    # ==================================================
    # Actions
    # ==================================================
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

        xls = pd.ExcelFile(path)
        self.workbook_sheets = xls.sheet_names

        self.pastel_combo["values"] = self.workbook_sheets
        self.ixtrac_combo["values"] = self.workbook_sheets

        self.pastel_sheet_var.set(
            PASTEL_SHEET if PASTEL_SHEET in self.workbook_sheets else self.workbook_sheets[0]
        )
        self.ixtrac_sheet_var.set(
            IXTRAC_SHEET if IXTRAC_SHEET in self.workbook_sheets else self.workbook_sheets[-1]
        )

    def choose_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir = folder
            self.output_folder_label.config(text=folder)

    def confirm_large_file(self):
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
        if self.pastel_sheet_var.get() == self.ixtrac_sheet_var.get():
            messagebox.showerror(
                "Invalid Sheet Selection",
                "Pastel and IXTRAC sheets must be different.",
            )
            return

        if not self.confirm_large_file():
            self.status.config(text="Status: Cancelled by user")
            return

        self.cancel_requested = False
        self.run_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_folder_btn.config(state=DISABLED)

        self.progress.configure(value=0)
        self.set_stage("LOAD")

        threading.Thread(target=self.run_reconciliation, daemon=True).start()

    def request_cancel(self):
        self.cancel_requested = True
        self.status.config(text="Status: Cancelling…")

    def run_reconciliation(self):
        try:
            self.set_stage("LOAD")
            pastel = load_excel(self.input_file, self.pastel_sheet_var.get())
            ixtrac = load_excel(self.input_file, self.ixtrac_sheet_var.get())

            self.set_stage("VALIDATE")

            self.set_stage("NETTING")
            self.set_stage("MATCHING")
            self.set_stage("REVIEW")

            (
                matched,
                ref_mismatch,
                reviewed_matches,
                pastel_outstanding,
                ixtrac_outstanding,
                netted,
                remaining_credits,
                summary,
            ) = run_reconciliation(pastel, ixtrac)

            self.set_stage("WRITE")

            base = self.filename_entry.get().strip() or DEFAULT_OUTPUT_BASENAME
            ts = datetime.now().strftime("%Y%m%d_%H%M%S") if self.timestamp_var.get() else ""
            name = f"{base}_{ts}.xlsx" if ts else f"{base}.xlsx"

            self.output_path = os.path.join(self.output_dir, name)

            write_excel(
                self.output_path,
                matched,
                ref_mismatch,
                reviewed_matches,
                pastel_outstanding,
                ixtrac_outstanding,
                netted,
                remaining_credits,
                summary,
            )

            self.set_stage("DONE")
            self.after(0, self.on_success)

        except DataValidationError as e:
            pastel = load_excel(self.input_file, self.pastel_sheet_var.get())
            ixtrac = load_excel(self.input_file, self.ixtrac_sheet_var.get())

            pastel = annotate_errors(pastel, e.errors, "PASTEL")
            ixtrac = annotate_errors(ixtrac, e.errors, "IXTRAC")

            error_file = self.input_file.replace(".xlsx", "_VALIDATION_ERRORS.xlsx")

            with pd.ExcelWriter(error_file, engine="xlsxwriter") as writer:
                pastel.to_excel(writer, self.pastel_sheet_var.get(), index=False)
                ixtrac.to_excel(writer, self.ixtrac_sheet_var.get(), index=False)

            self.after(0, lambda: messagebox.showerror(
                "Validation Failed",
                f"Reconciliation aborted.\n\n"
                f"Errors found and annotated.\n\n"
                f"File saved as:\n{error_file}"
            ))

            self.progress.configure(value=0)
            self.run_btn.config(state=NORMAL)
            self.cancel_btn.config(state=DISABLED)

    def on_success(self):
        self.progress.configure(value=100)
        self.cancel_btn.config(state=DISABLED)
        self.run_btn.config(state=NORMAL)
        self.open_folder_btn.config(state=NORMAL)
        self.status.config(text="Status: Completed successfully")
        messagebox.showinfo("Completed", f"Output saved to:\n{self.output_path}")

    def open_output_folder(self):
        if self.output_path:
            os.startfile(os.path.dirname(self.output_path))


if __name__ == "__main__":
    app = ReconApp()
    app.mainloop()
