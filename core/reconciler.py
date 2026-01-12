from datetime import datetime
from core.internal_netting import net_credit_debit
from core.matchers import match_pastel_ixtrac
from core.reasons import pastel_reason, ixtrac_reason


def run_reconciliation(pastel, ixtrac):
    pastel_remaining, netted = net_credit_debit(pastel)

    matched, pastel_unmatched, ixtrac_unmatched = match_pastel_ixtrac(
        pastel_remaining, ixtrac
    )

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
        "Matched": len(matched),
        "Confirmed": (matched["STATUS"] == "confirmed").sum(),
        "Confirmed (2 names)": (matched["STATUS"] == "confirmed_2_names").sum(),
        "Pastel Unmatched": len(pastel_unmatched),
        "IX TRAC Unmatched": len(ixtrac_unmatched),
    }

    return matched, pastel_unmatched, ixtrac_unmatched, netted, summary
