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
from core.progress import ProgressReporter
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
STAGES = ["LOAD", "VALIDATE", "NETTING", "MATCHING", "REVIEW", "WRITE", "DONE"]

STAGE_LABEL = {
    "LOAD": "Load",
    "VALIDATE": "Validate",
    "NETTING": "Netting",
    "MATCHING": "Matching",
    "REVIEW": "Review",
    "WRITE": "Output",
    "DONE": "Done",
}

STAGE_PERCENT = {
    "LOAD": 10,
    "VALIDATE": 20,
    "NETTING": 40,
    "MATCHING": 65,
    "REVIEW": 85,
    "WRITE": 95,
    "DONE": 100,
}
# =================================================


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
        self.geometry("920x860")
        self.resizable(True, True)

        # App icon
        try:
            self.iconbitmap(resource_path("assets/app.ico"))
        except Exception as e:
            print("Icon load failed:", e)

        self.input_file = None
        self.output_dir = None
        self.cancel_requested = False

        self.stage_labels = {}
        self.stage_spinners = {}
        self.metric_labels = {}

        self._build_ui()

    # ==================================================
    # UI
    # ==================================================
    def _build_ui(self):
        container = ttk.Frame(self, padding=24)
        container.pack(fill=BOTH, expand=True)

        # ---------- HEADER ----------
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

        ttk.Label(title, text=COMPANY_NAME,
                  font=("Segoe UI", 16, "bold"),
                  foreground=PRIMARY_GREEN).pack(anchor=W)

        ttk.Label(title, text=f"{APP_NAME} · {DEPARTMENT_NAME}",
                  font=("Segoe UI", 10),
                  foreground=TEXT_MUTED).pack(anchor=W)

        ttk.Separator(container).pack(fill=X, pady=14)

        # ---------- FILE ----------
        file_frame = ttk.Frame(container)
        file_frame.pack(fill=X)

        self.file_label = ttk.Label(file_frame, text="No file selected")
        self.file_label.pack(side=LEFT, expand=True, fill=X)

        ttk.Button(file_frame, text="Choose Excel File",
                   command=self.browse_file,
                   bootstyle="secondary").pack(side=RIGHT)

        # ---------- SHEET MAPPING ----------
        ttk.Label(container, text="Sheet Mapping",
                  font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(10, 6))

        sheet_frame = ttk.Frame(container)
        sheet_frame.pack(fill=X)

        self.pastel_sheet_var = tk.StringVar()
        self.ixtrac_sheet_var = tk.StringVar()

        ttk.Label(sheet_frame, text="Pastel Sheet:").grid(row=0, column=0, sticky=W)
        self.pastel_combo = ttk.Combobox(sheet_frame, textvariable=self.pastel_sheet_var,
                                         state="readonly", width=28)
        self.pastel_combo.grid(row=0, column=1, padx=8)

        ttk.Label(sheet_frame, text="IXTRAC Sheet:").grid(row=0, column=2, sticky=W)
        self.ixtrac_combo = ttk.Combobox(sheet_frame, textvariable=self.ixtrac_sheet_var,
                                         state="readonly", width=28)
        self.ixtrac_combo.grid(row=0, column=3, padx=8)

        # ---------- OUTPUT ----------
        out_frame = ttk.Frame(container)
        out_frame.pack(fill=X, pady=10)

        self.output_label = ttk.Label(out_frame,
                                      text="Output: same folder as input",
                                      foreground=TEXT_MUTED)
        self.output_label.pack(side=LEFT, expand=True, fill=X)

        ttk.Button(out_frame, text="Change Output Folder",
                   command=self.choose_output_folder,
                   bootstyle="secondary").pack(side=RIGHT)

        # ---------- OUTPUT NAME ----------
        ttk.Label(container, text="Output File Name",
                  font=("Segoe UI", 10, "bold")).pack(anchor=W)

        self.filename_entry = ttk.Entry(container)
        self.filename_entry.pack(fill=X)
        self.filename_entry.insert(0, DEFAULT_OUTPUT_BASENAME)

        self.timestamp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(container, text="Append timestamp",
                        variable=self.timestamp_var,
                        bootstyle="success").pack(anchor=W, pady=6)

        # ---------- STAGE STEPPER ----------
        ttk.Label(container, text="Reconciliation Pipeline",
                  font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(15, 6))

        stepper = ttk.Frame(container)
        stepper.pack(fill=X)

        for stage in STAGES:
            block = ttk.Frame(stepper)
            block.pack(side=LEFT, padx=6)

            lbl = ttk.Label(block, text=STAGE_LABEL[stage],
                            padding=6, bootstyle="secondary")
            lbl.pack()

            spinner = ttk.Progressbar(block,
                                      mode="indeterminate",
                                      length=40)
            spinner.pack(pady=2)
            spinner.stop()

            self.stage_labels[stage] = lbl
            self.stage_spinners[stage] = spinner

        # ---------- METRICS ----------
        ttk.Label(container, text="Live Metrics",
                  font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(15, 6))

        metrics = ttk.Frame(container)
        metrics.pack(fill=X)

        for key in ["credits", "debits", "netted",
                    "candidates", "confirmed", "ref_mismatch"]:
            lbl = ttk.Label(metrics, text=f"{key}: —",
                            font=("Segoe UI", 10))
            lbl.pack(anchor=W)
            self.metric_labels[key] = lbl

        # ---------- OVERALL PROGRESS ----------
        self.progress = ttk.Progressbar(container,
                                        mode="determinate",
                                        maximum=100,
                                        length=620)
        self.progress.pack(pady=12)

        self.status = ttk.Label(container, text="Status: Idle")
        self.status.pack()

        # ---------- BUTTONS ----------
        btns = ttk.Frame(container)
        btns.pack(pady=20)

        self.run_btn = ttk.Button(btns, text="Run Reconciliation",
                                  command=self.start_reconciliation,
                                  bootstyle="success",
                                  state=DISABLED)
        self.run_btn.pack(side=LEFT, padx=10)

        self.cancel_btn = ttk.Button(btns, text="Cancel",
                                     command=self.request_cancel,
                                     bootstyle="danger",
                                     state=DISABLED)
        self.cancel_btn.pack(side=LEFT, padx=10)

        ttk.Separator(container).pack(fill=X, pady=20)
        ttk.Label(container, text=FOOTER_TEXT,
                  font=("Segoe UI", 9)).pack()

    # ==================================================
    # Progress rendering
    # ==================================================
    def render_stage(self, stage):
        # 🔒 Hard stop after terminal state
        if self.terminal_stage_reached:
            return

        # Stop all spinners
        for spinner in self.stage_spinners.values():
            spinner.stop()

        if stage == "ERROR":
            self.terminal_stage_reached = True

            for lbl in self.stage_labels.values():
                lbl.configure(bootstyle="danger")

            self.progress.configure(value=100)
            self.status.config(text="Status: Error occurred")
            return

        if stage == "DONE":
            self.terminal_stage_reached = True

            for lbl in self.stage_labels.values():
                lbl.configure(bootstyle="success")

            self.progress.configure(value=100)
            self.status.config(text="Status: Completed successfully")
            return

        # Normal active stages
        for s, lbl in self.stage_labels.items():
            if s == stage:
                lbl.configure(bootstyle="info")
                self.stage_spinners[s].start(10)
            elif STAGES.index(s) < STAGES.index(stage):
                lbl.configure(bootstyle="success")
            else:
                lbl.configure(bootstyle="secondary")

        self.progress.configure(value=STAGE_PERCENT[stage])
        self.status.config(text=f"Status: {STAGE_LABEL[stage]}")

    def render_metrics(self, metrics):
        """
        Update live counters emitted by the reconciliation engine.
        """
        for key, value in metrics.items():
            if key in self.metric_labels:
                self.metric_labels[key].config(text=f"{key}: {value}")

        # ==================================================
    # Guards
    # ==================================================
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

    # ==================================================
    # Actions
    # ==================================================
    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if not path:
            return

        self.reset_ui_state()  # 👈 ADD THIS

        self.input_file = path
        self.output_dir = os.path.dirname(path)
        self.file_label.config(text=os.path.basename(path))
        self.output_label.config(text=f"Output: {self.output_dir}")

        xls = pd.ExcelFile(path)
        sheets = xls.sheet_names

        self.pastel_combo["values"] = sheets
        self.ixtrac_combo["values"] = sheets

        self.pastel_sheet_var.set(PASTEL_SHEET if PASTEL_SHEET in sheets else sheets[0])
        self.ixtrac_sheet_var.set(IXTRAC_SHEET if IXTRAC_SHEET in sheets else sheets[-1])

        self.run_btn.config(state=NORMAL)

    def choose_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir = folder
            self.output_label.config(text=f"Output: {folder}")

    def start_reconciliation(self):
        if self.pastel_sheet_var.get() == self.ixtrac_sheet_var.get():
            messagebox.showerror("Invalid Sheet Selection",
                                 "Pastel and IXTRAC sheets must be different.")
            return

        if not self.confirm_large_file():
            return

        self.cancel_requested = False
        self.run_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)

        threading.Thread(target=self.run_reconciliation, daemon=True).start()

    def request_cancel(self):
        self.cancel_requested = True
        self.status.config(text="Status: Cancelling…")

    def run_reconciliation(self):
        try:
            pastel = load_excel(self.input_file, self.pastel_sheet_var.get())
            ixtrac = load_excel(self.input_file, self.ixtrac_sheet_var.get())

            reporter = ProgressReporter(
                on_stage=lambda s: self.after(0, self.render_stage, s),
                on_metrics=lambda m: self.after(0, self.render_metrics, m),
                is_cancelled=lambda: self.cancel_requested
            )

            results = run_reconciliation(pastel, ixtrac, progress=reporter)

            if self.cancel_requested or results is None:
                self.after(0, lambda: self.status.config(text="Status: Cancelled"))
                return

            base = self.filename_entry.get().strip() or DEFAULT_OUTPUT_BASENAME
            ts = datetime.now().strftime("%Y%m%d_%H%M%S") if self.timestamp_var.get() else ""
            name = f"{base}_{ts}.xlsx" if ts else f"{base}.xlsx"

            out = os.path.join(self.output_dir, name)
            write_excel(out, *results)

            self.after(0, lambda: messagebox.showinfo(
                "Completed", f"Output saved to:\n{out}"
            ))

        except DataValidationError as e:
            # Mark pipeline as failed
            self.after(0, self.render_stage, "ERROR")

            try:
                # Reload original sheets
                pastel = load_excel(self.input_file, self.pastel_sheet_var.get())
                ixtrac = load_excel(self.input_file, self.ixtrac_sheet_var.get())

                # Annotate errors
                pastel_annotated = annotate_errors(pastel, e.errors, "PASTEL")
                ixtrac_annotated = annotate_errors(ixtrac, e.errors, "IXTRAC")

                # Build output path
                base, ext = os.path.splitext(self.input_file)
                error_file = f"{base}_VALIDATION_ERRORS{ext}"

                # Write annotated workbook
                with pd.ExcelWriter(error_file, engine="xlsxwriter") as writer:
                    pastel_annotated.to_excel(
                        writer,
                        sheet_name=self.pastel_sheet_var.get(),
                        index=False
                    )
                    ixtrac_annotated.to_excel(
                        writer,
                        sheet_name=self.ixtrac_sheet_var.get(),
                        index=False
                    )

                # Notify user clearly
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Validation Failed",
                        "Reconciliation could not proceed due to data validation errors.\n\n"
                        "An annotated copy of the original workbook has been generated, "
                        "highlighting the exact rows and columns that require correction.\n\n"
                        f"File saved as:\n{error_file}"
                    )
                )

            except Exception as write_err:
                # Absolute fallback (should never happen)
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Validation Failed",
                        f"{str(e)}\n\n"
                        "Additionally, the system could not generate the annotated file.\n"
                        f"Reason: {write_err}"
                    )
                )


    def reset_ui_state(self):
        # Unlock terminal state
        self.terminal_stage_reached = False
        self.cancel_requested = False

        # Reset stage labels & spinners
        for stage in STAGES:
            self.stage_labels[stage].configure(bootstyle="secondary")
            self.stage_spinners[stage].stop()

        # Reset metrics
        for key, lbl in self.metric_labels.items():
            lbl.config(text=f"{key}: —")

        # Reset progress + status
        self.progress.configure(value=0)
        self.status.config(text="Status: Ready")

        # Buttons
        self.cancel_btn.config(state=DISABLED)

if __name__ == "__main__":
    ReconApp().mainloop()
