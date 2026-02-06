import pandas as pd
from app.engine.utils.text_match import name_match_score


def safe_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return None


def match_pastel_ixtrac(pastel: pd.DataFrame, ixtrac: pd.DataFrame):
    """
    Two-stage reconciliation:
    - Amount-based candidate search
    - Explicit evaluation of reference and name
    - One-to-one enforced
    """

    pastel = pastel.copy()
    ixtrac = ixtrac.copy()

    # ================================
    # SAFE AMOUNT NORMALIZATION
    # ================================
    pastel["AMT_KEY"] = pastel["Debit"].apply(safe_float)
    ixtrac["AMT_KEY"] = ixtrac["NET AMT"].apply(safe_float)

    # Drop rows where amount is invalid
    pastel = pastel[pastel["AMT_KEY"].notna()]
    ixtrac = ixtrac[ixtrac["AMT_KEY"].notna()]

    results = []
    matched_ixtrac_idx = set()

    # ================================
    # MATCHING LOOP
    # ================================
    for _, p in pastel.iterrows():
        # Exclude already matched ixtrac rows
        candidates = ixtrac[
            (ixtrac["AMT_KEY"] == p["AMT_KEY"]) &
            (~ixtrac.index.isin(matched_ixtrac_idx))
        ]

        if candidates.empty:
            results.append({
                **p,
                "MATCH_STATUS": "NO_IXTRAC",
                "NAME_SCORE": 0,
                "REFERENCE_MATCH": False
            })
            continue

        best = None
        best_score = 0
        best_idx = None
        ref_match = False

        for idx, i in candidates.iterrows():
            score = name_match_score(p["Description"], i["NAME"])
            reference_equal = (
                str(p["Reference"]).strip() ==
                str(i["WARRANT NO"]).strip()
            )

            # Reject totally weak matches (no name & no ref)
            if score == 0 and not reference_equal:
                continue

            priority = (reference_equal, score)

            if best is None or priority > (ref_match, best_score):
                best = i
                best_score = score
                best_idx = idx
                ref_match = reference_equal

        if best is None:
            # No acceptable candidate after filtering
            results.append({
                **p,
                "MATCH_STATUS": "NO_VALID_CANDIDATE",
                "NAME_SCORE": 0,
                "REFERENCE_MATCH": False
            })
            continue

        results.append({
            **p,
            **best,
            "MATCH_STATUS": "CANDIDATE_FOUND",
            "NAME_SCORE": best_score,
            "REFERENCE_MATCH": ref_match
        })

        matched_ixtrac_idx.add(best_idx)

    merged = pd.DataFrame(results)
    ixtrac_unmatched = ixtrac.drop(index=matched_ixtrac_idx)

    return merged, ixtrac_unmatched
