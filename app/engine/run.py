from io import BytesIO
import pandas as pd

from app.engine.core.loaders import load_excel
from app.engine.core.reconciler import run_reconciliation
from app.engine.outputs.writer import write_excel


def get_sheet_names(excel_bytes: bytes) -> list[str]:
    with BytesIO(excel_bytes) as buffer:
        xl = pd.ExcelFile(buffer)
        return xl.sheet_names


def run_web_reconciliation(
    excel_bytes: bytes,
    pastel_sheet: str,
    ixtrac_sheet: str,
) -> bytes:
    """
    Web-safe wrapper around the existing reconciliation engine
    """

    buffer = BytesIO(excel_bytes)

    pastel_df = load_excel(buffer, pastel_sheet)
    ixtrac_df = load_excel(buffer, ixtrac_sheet)

    (
        matched,
        ref_mismatch,
        reviewed,
        pastel_outstanding,
        ixtrac_outstanding,
        netted,
        remaining_credits,
        summary,
    ) = run_reconciliation(pastel_df, ixtrac_df)

    output_buffer = BytesIO()

    write_excel(
        output_buffer,
        matched,
        ref_mismatch,
        reviewed,
        pastel_outstanding,
        ixtrac_outstanding,
        netted,
        remaining_credits,
        summary,
    )

    output_buffer.seek(0)
    return output_buffer.read()
