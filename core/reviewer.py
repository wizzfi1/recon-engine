# core/reviewer.py
import re
from collections import defaultdict

BUSINESS_STOPWORDS = {
    "ltd", "limited", "nigeria", "plc", "corp", "corporation",
    "trading", "trad", "services", "service", "company", "co"
}

_non_alnum = re.compile(r"[^a-z0-9 ]+")


def normalize_name_tokens(text):
    """
    - lowercase
    - remove non-alnum
    - split tokens
    - remove business stopwords
    Returns frozenset for fast hashing.
    """
    text = _non_alnum.sub("", str(text).lower())
    tokens = text.split()
    return frozenset(t for t in tokens if t and t not in BUSINESS_STOPWORDS)


def _is_nan(x: float) -> bool:
    # NaN is the only value where x != x is True
    return x != x


def normalize_amount(val):
    """
    Convert numeric-looking values to float.
    IMPORTANT: treat NaN as invalid -> return None
    """
    try:
        x = float(str(val).replace(",", "").strip())
        if _is_nan(x):
            return None
        return x
    except Exception:
        return None


def normalize_ref(val):
    """
    Preserve original behavior:
    - If numeric-ish, coerce to int string (removes .0)
    - Else fallback to stripped string
    """
    try:
        return str(int(float(str(val).strip()))).strip()
    except Exception:
        return str(val).strip()


def _precompute_review_fields(df, amt_col, ref_col, name_col):
    """
    Precompute normalized fields ONCE to avoid repeated work in loops.
    Returns dicts keyed by dataframe index.
    """
    amt = {}
    ref = {}
    tokens = {}

    for idx, v in df[amt_col].items():
        amt[idx] = normalize_amount(v)

    for idx, v in df[ref_col].items():
        ref[idx] = normalize_ref(v)

    for idx, v in df[name_col].items():
        tokens[idx] = normalize_name_tokens(v)

    return amt, ref, tokens


def _build_ref_index_from_precomputed(ref_dict):
    """
    Build mapping: normalized_ref -> list[row_index]
    Uses already-normalized refs (avoid normalizing twice).
    """
    ref_map = defaultdict(list)
    for idx, r in ref_dict.items():
        ref_map[r].append(idx)
    return ref_map


# ----------------------------
# REVIEW PASTEL → IXTRAC
# ----------------------------
def review_pastel_against_ixtrac(
    pastel_unmatched,
    original_ixtrac,
    pastel_amt_col,
    ixtrac_amt_col,
    pastel_ref_col,
    ixtrac_ref_col,
    pastel_name_col,
    ixtrac_name_col,
):
    reviewed_pairs = []
    outstanding_idx = []
    used_ixtrac = set()

    # Precompute once
    p_amt, p_ref, p_tokens = _precompute_review_fields(
        pastel_unmatched, pastel_amt_col, pastel_ref_col, pastel_name_col
    )
    x_amt, x_ref, x_tokens = _precompute_review_fields(
        original_ixtrac, ixtrac_amt_col, ixtrac_ref_col, ixtrac_name_col
    )

    # Block by REF (your rules require ref equality)
    ix_ref_map = _build_ref_index_from_precomputed(x_ref)

    for p_idx in pastel_unmatched.index:
        amt = p_amt.get(p_idx)
        ref = p_ref.get(p_idx)
        names = p_tokens.get(p_idx, frozenset())

        # Same guard as before
        if amt is None or len(names) < 2:
            outstanding_idx.append(p_idx)
            continue

        candidates = ix_ref_map.get(ref, [])
        if not candidates:
            outstanding_idx.append(p_idx)
            continue

        int_amt = int(amt)  # safe because amt is not None/NaN
        matched = False

        for x_idx in candidates:
            if x_idx in used_ixtrac:
                continue

            xamt = x_amt.get(x_idx)
            if xamt is None:
                continue

            overlap = len(names & x_tokens.get(x_idx, frozenset()))
            if overlap < 2:
                continue

            # Rule A1: Exact amount
            if abs(amt - xamt) < 0.01:
                reviewed_pairs.append(
                    (pastel_unmatched.loc[p_idx].copy(),
                     original_ixtrac.loc[x_idx].copy(),
                     "EXACT_AMT+2NAME+REF")
                )
                used_ixtrac.add(x_idx)
                matched = True
                break

            # Rule A2: Whole amount
            if int_amt == int(xamt):  # safe because xamt is not None/NaN
                reviewed_pairs.append(
                    (pastel_unmatched.loc[p_idx].copy(),
                     original_ixtrac.loc[x_idx].copy(),
                     "WHOLE_AMT+2NAME+REF")
                )
                used_ixtrac.add(x_idx)
                matched = True
                break

        if not matched:
            outstanding_idx.append(p_idx)

    return reviewed_pairs, pastel_unmatched.loc[outstanding_idx].copy()


# ----------------------------
# REVIEW IXTRAC → PASTEL
# ----------------------------
def review_ixtrac_against_pastel(
    ixtrac_unmatched,
    original_pastel,
    ixtrac_amt_col,
    pastel_amt_col,
    ixtrac_ref_col,
    pastel_ref_col,
    ixtrac_name_col,
    pastel_name_col,
):
    reviewed_pairs = []
    outstanding_idx = []
    used_pastel = set()

    # Precompute once
    x_amt, x_ref, x_tokens = _precompute_review_fields(
        ixtrac_unmatched, ixtrac_amt_col, ixtrac_ref_col, ixtrac_name_col
    )
    p_amt, p_ref, p_tokens = _precompute_review_fields(
        original_pastel, pastel_amt_col, pastel_ref_col, pastel_name_col
    )

    # Block by REF
    pastel_ref_map = _build_ref_index_from_precomputed(p_ref)

    for x_idx in ixtrac_unmatched.index:
        amt = x_amt.get(x_idx)
        ref = x_ref.get(x_idx)
        names = x_tokens.get(x_idx, frozenset())

        if amt is None or len(names) < 2:
            outstanding_idx.append(x_idx)
            continue

        candidates = pastel_ref_map.get(ref, [])
        if not candidates:
            outstanding_idx.append(x_idx)
            continue

        int_amt = int(amt)  # safe because amt is not None/NaN
        matched = False

        for p_idx in candidates:
            if p_idx in used_pastel:
                continue

            pamt = p_amt.get(p_idx)
            if pamt is None:
                continue

            overlap = len(names & p_tokens.get(p_idx, frozenset()))
            if overlap < 2:
                continue

            # Rule B1: Exact amount
            if abs(amt - pamt) < 0.01:
                reviewed_pairs.append(
                    (original_pastel.loc[p_idx].copy(),
                     ixtrac_unmatched.loc[x_idx].copy(),
                     "EXACT_AMT+2NAME+REF")
                )
                used_pastel.add(p_idx)
                matched = True
                break

            # Rule B2: Whole amount
            if int_amt == int(pamt):  # safe because pamt is not None/NaN
                reviewed_pairs.append(
                    (original_pastel.loc[p_idx].copy(),
                     ixtrac_unmatched.loc[x_idx].copy(),
                     "WHOLE_AMT+2NAME+REF")
                )
                used_pastel.add(p_idx)
                matched = True
                break

        if not matched:
            outstanding_idx.append(x_idx)

    return reviewed_pairs, ixtrac_unmatched.loc[outstanding_idx].copy()
