from datetime import datetime
import pandas as pd

from app.engine.core.internal_netting import net_credit_debit, _find_column
from app.engine.core.matchers import match_pastel_ixtrac
from app.engine.core.reasons import pastel_reason, ixtrac_reason
from app.engine.core.reviewer import (
    review_pastel_against_ixtrac,
    review_ixtrac_against_pastel,
)
from app.engine.utils.dataframe import remove_total_rows


def run_reconciliation(pastel, ixtrac):
    pastel = remove_total_rows(pastel.copy())
    ixtrac = remove_total_rows(ixtrac.copy())

    credit_col = _find_column(pastel, {"credit"})
    debit_col = _find_column(pastel, {"debit"})

    pastel_after_netting, netted = net_credit_debit(pastel)

    remaining_credits = pastel_after_netting[
        pastel_after_netting[credit_col] > 0
    ].copy()

    pastel_debits_only = pastel_after_netting[
        pastel_after_netting[debit_col] > 0
    ].copy()

    merged, ixtrac_unmatched = match_pastel_ixtrac(
        pastel_debits_only, ixtrac
    )

    matched = merged[
        (merged["REFERENCE_MATCH"] == True) &
        (merged["NAME_SCORE"] >= 2)
    ].copy()

    ref_mismatch_name_amount_match = merged[
        (merged["REFERENCE_MATCH"] == False) &
        (merged["NAME_SCORE"] >= 1)
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

    # 🔁 REVIEW PHASE (PAIR-AWARE)
    reviewed_pastel_pairs, pastel_outstanding = review_pastel_against_ixtrac(
        pastel_unmatched,
        ixtrac,
        pastel_amt_col="Debit",
        ixtrac_amt_col="NET AMT",
        pastel_ref_col="Reference",
        ixtrac_ref_col="WARRANT NO",
        pastel_name_col="Description",
        ixtrac_name_col="NAME",
    )

    reviewed_ixtrac_pairs, ixtrac_outstanding = review_ixtrac_against_pastel(
        ixtrac_unmatched,
        pastel,
        ixtrac_amt_col="NET AMT",
        pastel_amt_col="Debit",
        ixtrac_ref_col="WARRANT NO",
        pastel_ref_col="Reference",
        ixtrac_name_col="NAME",
        pastel_name_col="Description",
    )

    all_reviewed_pairs = reviewed_pastel_pairs + reviewed_ixtrac_pairs

    reviewed_matches = pd.DataFrame([
        {
            **{f"PASTEL_{k}": v for k, v in p.to_dict().items()},
            **{f"IXTRAC_{k}": v for k, v in x.to_dict().items()},
            "REVIEW_RULE": rule
        }
        for p, x, rule in all_reviewed_pairs
    ])

    summary = {
        "Run Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Pastel Total": len(pastel),
        "IX TRAC Total": len(ixtrac),
        "Internally Netted": len(netted),
        "Remaining Credits": len(remaining_credits),
        "Confirmed": len(matched),
        "Ref Mismatch Candidates": len(ref_mismatch_name_amount_match),
        "Reviewed Matches": len(reviewed_matches),
        "Pastel Outstanding": len(pastel_outstanding),
        "IXTRAC Outstanding": len(ixtrac_outstanding),
    }

    return (
        matched,
        ref_mismatch_name_amount_match,
        reviewed_matches,
        pastel_outstanding,
        ixtrac_outstanding,
        netted,
        remaining_credits,
        summary,
    )
