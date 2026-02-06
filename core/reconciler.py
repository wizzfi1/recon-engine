from datetime import datetime
import pandas as pd

from core.internal_netting import net_credit_debit, _find_column
from core.matchers import match_pastel_ixtrac
from core.reviewer import (
    review_pastel_against_ixtrac,
    review_ixtrac_against_pastel,
)
from core.reasons import pastel_reason, ixtrac_reason
from utils.dataframe import remove_total_rows
from core.validators import validate_all


def run_reconciliation(pastel, ixtrac):
    pastel = remove_total_rows(pastel.copy())
    ixtrac = remove_total_rows(ixtrac.copy())

    credit_col = _find_column(pastel, {"credit"})
    debit_col = _find_column(pastel, {"debit"})

    pastel_cols = {"debit": debit_col, "credit": credit_col}
    ixtrac_cols = {"net_amt": "NET AMT"}

    # 🚫 HARD STOP if validation fails
    validate_all(pastel, ixtrac, pastel_cols, ixtrac_cols)

    # ============================
    # INTERNAL NETTING
    # ============================
    pastel_after_netting, netted = net_credit_debit(pastel)

    remaining_credits = pastel_after_netting[
        pastel_after_netting[credit_col] > 0
    ].copy()

    pastel_debits_only = pastel_after_netting[
        pastel_after_netting[debit_col] > 0
    ].copy()

    # ============================
    # EXTERNAL MATCHING
    # ============================
    merged, ixtrac_unmatched = match_pastel_ixtrac(
        pastel_debits_only, ixtrac
    )

    matched = merged[
        (merged["REFERENCE_MATCH"] == True) &
        (merged["NAME_SCORE"] >= 2)
    ].copy()

    ref_mismatch = merged[
        (merged["REFERENCE_MATCH"] == False) &
        (merged["NAME_SCORE"] >= 2)
    ].copy()

    pastel_unmatched = merged[
        merged["MATCH_STATUS"].isin(["NO_IXTRAC", "NO_VALID_CANDIDATE"])
    ].copy()
    pastel_unmatched["REASON_CODE"] = pastel_unmatched.apply(
        pastel_reason, axis=1
    )

    ixtrac_unmatched["REASON_CODE"] = ixtrac_unmatched.apply(
        ixtrac_reason, axis=1
    )

    reviewed_pastel_pairs, pastel_outstanding = review_pastel_against_ixtrac(
        pastel_unmatched, ixtrac,
        "Debit", "NET AMT",
        "Reference", "WARRANT NO",
        "Description", "NAME",
    )

    reviewed_ixtrac_pairs, ixtrac_outstanding = review_ixtrac_against_pastel(
        ixtrac_unmatched, pastel,
        "NET AMT", "Debit",
        "WARRANT NO", "Reference",
        "NAME", "Description",
    )

    reviewed_matches = pd.DataFrame([
        {
            **{f"PASTEL_{k}": v for k, v in p.to_dict().items()},
            **{f"IXTRAC_{k}": v for k, v in x.to_dict().items()},
            "REVIEW_RULE": rule
        }
        for p, x, rule in (reviewed_pastel_pairs + reviewed_ixtrac_pairs)
    ])

    summary = {
        "Run Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Pastel Rows": len(pastel),
        "IXTRAC Rows": len(ixtrac),
        "Internally Netted": len(netted),
        "Remaining Credits": len(remaining_credits),
        "Confirmed": len(matched),
        "Ref Mismatch": len(ref_mismatch),
        "Reviewed": len(reviewed_matches),
        "Pastel Outstanding": len(pastel_outstanding),
        "IXTRAC Outstanding": len(ixtrac_outstanding),
    }

    return (
        matched,
        ref_mismatch,
        reviewed_matches,
        pastel_outstanding,
        ixtrac_outstanding,
        netted,
        remaining_credits,
        summary,
    )
