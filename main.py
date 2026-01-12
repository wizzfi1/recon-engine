from core.loaders import load_excel
from core.reconciler import run_reconciliation
from outputs.writer import write_excel
from config import PASTEL_SHEET, IXTRAC_SHEET, OUTPUT_FILE


INPUT_FILE = "DEMO FINANCE.xlsx"

pastel = load_excel(INPUT_FILE, PASTEL_SHEET)
ixtrac = load_excel(INPUT_FILE, IXTRAC_SHEET)

<<<<<<< HEAD
matched, pastel_unmatched, ixtrac_unmatched, netted, summary = (
    run_reconciliation(pastel, ixtrac)
)
=======
(
    matched,
    ref_mismatch_name_amount,
    pastel_unmatched,
    ixtrac_unmatched,
    netted,
    summary,
) = run_reconciliation(pastel, ixtrac)
>>>>>>> master

write_excel(
    OUTPUT_FILE,
    matched,
<<<<<<< HEAD
    pastel_unmatched,
    ixtrac_unmatched,
    netted,
    summary
=======
    ref_mismatch_name_amount,
    pastel_unmatched,
    ixtrac_unmatched,
    netted,
    summary,
>>>>>>> master
)

print("✅ Reconciliation completed successfully.")
