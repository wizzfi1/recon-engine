import pandas as pd
from utils.text import name_match_score


<<<<<<< HEAD
def match_pastel_ixtrac(pastel, ixtrac):
    pastel["MATCH_KEY"] = (
        pastel["Reference"].astype(str).str.strip()
        + "|"
        + pastel["Debit"].astype(str)
    )

    ixtrac["MATCH_KEY"] = (
        ixtrac["WARRANT NO"].astype(str).str.strip()
        + "|"
        + ixtrac["NET AMT"].astype(str)
    )

    merged = pastel.merge(
        ixtrac,
        on="MATCH_KEY",
        how="left",
        suffixes=("_pastel", "_ixtrac")
    )

    def status(row):
        if pd.isna(row["NAME"]):
            return None
        score = name_match_score(row["Description"], row["NAME"])
        if score >= 3:
            return "confirmed"
        if score >= 2:
            return "confirmed_2_names"
        return None

    merged["STATUS"] = merged.apply(status, axis=1)

    matched = merged[merged["STATUS"].notna()].copy()
    pastel_unmatched = merged[merged["STATUS"].isna()].copy()

    matched_keys = matched["MATCH_KEY"].unique()
    ixtrac_unmatched = ixtrac[
        ~ixtrac["MATCH_KEY"].isin(matched_keys)
    ].copy()

    return matched, pastel_unmatched, ixtrac_unmatched
=======
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
>>>>>>> master
