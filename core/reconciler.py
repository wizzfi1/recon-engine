from datetime import datetime
from core.internal_netting import net_credit_debit
from core.matchers import match_pastel_ixtrac
from core.reasons import pastel_reason, ixtrac_reason


def run_reconciliation(pastel, ixtrac):
    # 1️⃣ Internal netting
    pastel_remaining, netted = net_credit_debit(pastel)

    # 2️⃣ External matching
    merged, ixtrac_unmatched = match_pastel_ixtrac(
        pastel_remaining, ixtrac
    )

    # 3️⃣ Fully confirmed (reference + name)
    matched = merged[
        (merged["REFERENCE_MATCH"] == True) &
        (merged["NAME_SCORE"] >= 2)
    ].copy()

    # 4️⃣ Amount + Name match but Reference mismatch (NEW)
    ref_mismatch_name_amount = merged[
        (merged["REFERENCE_MATCH"] == False) &
        (merged["NAME_SCORE"] >= 2)
    ].copy()

    # 5️⃣ True Pastel unmatched
    pastel_unmatched = merged[
        ~(
            ((merged["REFERENCE_MATCH"] == True) & (merged["NAME_SCORE"] >= 2)) |
            ((merged["REFERENCE_MATCH"] == False) & (merged["NAME_SCORE"] >= 2))
        )
    ].copy()

    # 6️⃣ Reason codes
    pastel_unmatched["REASON_CODE"] = pastel_unmatched.apply(
        pastel_reason, axis=1
    )

    ixtrac_unmatched["REASON_CODE"] = ixtrac_unmatched.apply(
        ixtrac_reason, axis=1
    )

    # 7️⃣ Summary
    summary = {
        "Run Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Pastel Total": len(pastel),
        "IX TRAC Total": len(ixtrac),
        "Internally Netted": len(netted),
        "Confirmed": len(matched),
        "Ref Mismatch (Name+Amount Match)": len(ref_mismatch_name_amount),
        "Pastel Unmatched": len(pastel_unmatched),
        "IX TRAC Unmatched": len(ixtrac_unmatched),
    }

    return (
        matched,
        ref_mismatch_name_amount,
        pastel_unmatched,
        ixtrac_unmatched,
        netted,
        summary,
    )
