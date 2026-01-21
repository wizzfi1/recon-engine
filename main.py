from core.loaders import load_excel
from core.reconciler import run_reconciliation
from outputs.writer import write_excel
from config import PASTEL_SHEET, IXTRAC_SHEET, OUTPUT_FILE


INPUT_FILE = "ULR47.xlsx"

pastel = load_excel(INPUT_FILE, PASTEL_SHEET)
ixtrac = load_excel(INPUT_FILE, IXTRAC_SHEET)

(
    matched,
    ref_mismatch_name_amount,
    pastel_unmatched,
    ixtrac_unmatched,
    netted,
    summary,
) = run_reconciliation(pastel, ixtrac)

write_excel(
    OUTPUT_FILE,
    matched,
    ref_mismatch_name_amount,
    pastel_unmatched,
    ixtrac_unmatched,
    netted,
    summary,
)

print("✅ Reconciliation completed successfully.")
