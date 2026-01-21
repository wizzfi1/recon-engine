from datetime import datetime
from core.internal_netting import net_credit_debit, _find_column
from core.matchers import match_pastel_ixtrac
from core.reasons import pastel_reason, ixtrac_reason


def run_reconciliation(pastel, ixtrac):
    pastel = pastel.copy()

    credit_col = _find_column(pastel, {"credit"})
    debit_col = _find_column(pastel, {"debit"})

    # 1️⃣ Internal netting
    pastel_after_netting, netted = net_credit_debit(pastel)

    # 2️⃣ Remaining credits (potential reversals)
    remaining_credits = pastel_after_netting[
        pastel_after_netting[credit_col] > 0
    ].copy()

    pastel_debits_only = pastel_after_netting[
        pastel_after_netting[debit_col] > 0
    ].copy()

    # 3️⃣ External matching (FULL candidate universe)
    merged, ixtrac_unmatched = match_pastel_ixtrac(
        pastel_debits_only, ixtrac
    )

    # 4️⃣ Basic confirmed (legacy)
    matched = merged[
        (merged["REFERENCE_MATCH"] == True) &
        (merged["NAME_SCORE"] >= 2)
    ].copy()

    # 5️⃣ Ref mismatch but name+amount
    ref_mismatch_name_amount_match = merged[
        (merged["REFERENCE_MATCH"] == False) &
        (merged["NAME_SCORE"] >= 1)
    ].copy()

    # 6️⃣ Pastel unmatched (no viable name signal at all)
    pastel_unmatched = merged[
        merged["NAME_SCORE"] == 0
    ].copy()

    pastel_unmatched["REASON_CODE"] = pastel_unmatched.apply(
        pastel_reason, axis=1
    )

    ixtrac_unmatched["REASON_CODE"] = ixtrac_unmatched.apply(
        ixtrac_reason, axis=1
    )

    summary = {
        "Run Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Pastel Total": len(pastel),
        "IX TRAC Total": len(ixtrac),
        "Internally Netted": len(netted),
        "Remaining Credits (Pastel)": len(remaining_credits),
        "Confirmed (Legacy)": len(matched),
        "Candidates (Ref Mismatch)": len(ref_mismatch_name_amount_match),
        "Pastel Unmatched": len(pastel_unmatched),
        "IX TRAC Unmatched": len(ixtrac_unmatched),
    }

    return (
        merged,                         # 🔑 FULL universe
        matched,
        ref_mismatch_name_amount_match, # informational only
        pastel_unmatched,
        ixtrac_unmatched,
        netted,
        remaining_credits,
        summary,
    )
