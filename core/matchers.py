import pandas as pd
from utils.text import name_match_score


def match_pastel_ixtrac(pastel: pd.DataFrame, ixtrac: pd.DataFrame):
    """
    Two-stage reconciliation:
    - Amount-based candidate search
    - Explicit evaluation of reference and name
    """

    pastel = pastel.copy()
    ixtrac = ixtrac.copy()

    pastel["AMT_KEY"] = pastel["Debit"].astype(float)
    ixtrac["AMT_KEY"] = ixtrac["NET AMT"].astype(float)

    results = []
    matched_ixtrac_idx = set()

    for _, p in pastel.iterrows():
        candidates = ixtrac[ixtrac["AMT_KEY"] == p["AMT_KEY"]]

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
            reference_equal = str(p["Reference"]).strip() == str(i["WARRANT NO"]).strip()

            # Prefer reference matches first, then higher name score
            priority = (reference_equal, score)

            if best is None or priority > (ref_match, best_score):
                best = i
                best_score = score
                best_idx = idx
                ref_match = reference_equal

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
