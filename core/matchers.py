import pandas as pd
from utils.text_match import name_match_score
from core.internal_netting import _find_column


def safe_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return None


def match_pastel_ixtrac(pastel: pd.DataFrame, ixtrac: pd.DataFrame):
    """
    Two-stage reconciliation:
    - Amount-based candidate search (exact amount key)
    - Explicit evaluation of reference and name
    - One-to-one enforced
    """

    pastel = pastel.copy()
    ixtrac = ixtrac.copy()

    # ---- Resolve columns robustly ----
    pastel_debit_col = _find_column(pastel, {"debit"})
    pastel_ref_col = _find_column(pastel, {"reference"})
    pastel_desc_col = _find_column(pastel, {"description"})

    ixtrac_amt_col = _find_column(ixtrac, {"net amt"})
    ixtrac_name_col = _find_column(ixtrac, {"name"})
    warrant_col = _find_column(ixtrac, {"warrant no", "warr no"})

    # ---- SAFE AMOUNT NORMALIZATION (keep key numeric) ----
    pastel["AMT_KEY"] = pastel[pastel_debit_col].apply(safe_float)
    ixtrac["AMT_KEY"] = ixtrac[ixtrac_amt_col].apply(safe_float)

    # Drop rows where amount is invalid
    pastel = pastel[pastel["AMT_KEY"].notna()].copy()
    ixtrac = ixtrac[ixtrac["AMT_KEY"].notna()].copy()

    # ---- Build fast lookup: AMT_KEY -> list of ixtrac indices ----
    # This avoids filtering ixtrac dataframe inside the loop.
    amt_to_ixtrac_indices = {}
    for idx, amt in ixtrac["AMT_KEY"].items():
        amt_to_ixtrac_indices.setdefault(amt, []).append(idx)

    results = []
    matched_ixtrac_idx = set()

    # ---- MATCHING LOOP ----
    for _, p in pastel.iterrows():
        p_amt = p["AMT_KEY"]
        candidate_idxs = amt_to_ixtrac_indices.get(p_amt, [])

        # Filter out already matched ixtrac rows
        candidate_idxs = [i for i in candidate_idxs if i not in matched_ixtrac_idx]

        if not candidate_idxs:
            results.append({
                **p.to_dict(),
                "MATCH_STATUS": "NO_IXTRAC",
                "NAME_SCORE": 0,
                "REFERENCE_MATCH": False
            })
            continue

        best_row = None
        best_score = 0
        best_idx = None
        ref_match = False

        p_ref = str(p[pastel_ref_col]).strip()
        p_desc = p[pastel_desc_col]

        for idx in candidate_idxs:
            i = ixtrac.loc[idx]

            score = name_match_score(p_desc, i[ixtrac_name_col])
            reference_equal = (p_ref == str(i[warrant_col]).strip())

            # 🚫 HARD GATE:
            # Reject unless:
            # - name matches strongly (>=2 tokens)
            # OR
            # - reference matches
            if score < 2 and not reference_equal:
                continue

            priority = (reference_equal, score)

            if best_row is None or priority > (ref_match, best_score):
                best_row = i
                best_score = score
                best_idx = idx
                ref_match = reference_equal

        if best_row is None:
            # No acceptable candidate after filtering
            results.append({
                **p.to_dict(),
                "MATCH_STATUS": "NO_VALID_CANDIDATE",
                "NAME_SCORE": 0,
                "REFERENCE_MATCH": False
            })
            continue

        results.append({
            **p.to_dict(),
            **best_row.to_dict(),
            "MATCH_STATUS": "CANDIDATE_FOUND",
            "NAME_SCORE": best_score,
            "REFERENCE_MATCH": ref_match
        })

        matched_ixtrac_idx.add(best_idx)

    merged = pd.DataFrame(results)

    # Drop helper key if you don’t want it in outputs:
    # merged.drop(columns=["AMT_KEY"], inplace=True, errors="ignore")

    ixtrac_unmatched = ixtrac.loc[~ixtrac.index.isin(matched_ixtrac_idx)].copy()
    # ixtrac_unmatched.drop(columns=["AMT_KEY"], inplace=True, errors="ignore")

    return merged, ixtrac_unmatched
