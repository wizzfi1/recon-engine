# core/internal_netting.py
import re
from collections import defaultdict, Counter
import pandas as pd


# ---- tuneables (safety/performance) ----
MAX_BUCKET_SCAN = 5000
# If a single amount has > MAX_BUCKET_SCAN rows (credits+debits),
# we avoid deep scanning because it can still be heavy.
# We will still attempt matching using token index, but we won't do naive O(n*m).


# ---- name normalization ----
# NOTE: include estate-related words here so "EST OF OGUNDELE" -> {"ogundele"}
NETTING_STOPWORDS = {
    "ltd", "limited", "nigeria", "plc", "corp", "corporation",
    "trading", "trad", "services", "service", "company", "co",
    "estate", "est", "of", "the", "trust", "late",
    "mr", "mrs", "miss", "dr", "chief", "sir", "madam",
}
_non_alnum = re.compile(r"[^a-z0-9 ]+")


def _normalize_name_tokens(text) -> tuple[str, ...]:
    s = _non_alnum.sub(" ", str(text).lower()).strip()
    toks = [t for t in s.split() if t and t not in NETTING_STOPWORDS]
    # tuple is hashable & fast
    return tuple(toks)


def safe_to_float(val):
    try:
        return float(str(val).replace(",", "").replace("+", "").strip())
    except Exception:
        return 0.0


def _find_column(df, candidates):
    for col in df.columns:
        if col.strip().lower() in candidates:
            return col
    raise KeyError(f"None of {candidates} found in columns: {df.columns.tolist()}")


def _strong_name_match(a_tokens: tuple[str, ...], b_tokens: tuple[str, ...]) -> bool:
    """
    Controlled name match gate for fallback netting:
      - allow >=2 shared tokens
      - OR allow 1 shared token if it is "strong" (len>=6, not numeric)
    """
    if not a_tokens or not b_tokens:
        return False

    a = set(a_tokens)
    b = set(b_tokens)
    common = a & b

    if len(common) >= 2:
        return True

    if len(common) == 1:
        token = next(iter(common))
        if len(token) >= 6 and not token.isdigit():
            return True

    return False


def net_credit_debit(pastel: pd.DataFrame):
    """
    Internal netting:
      Stage A (strict): REF + AMOUNT nets credit vs debit
      Stage B (fallback): NAME + AMOUNT nets credit vs debit (safe, no merge explosion)

    Returns:
      remaining_df, audit_df
    """
    pastel = pastel.copy()

    credit_col = _find_column(pastel, {"credit"})
    debit_col = _find_column(pastel, {"debit"})
    ref_col = _find_column(pastel, {"reference"})

    # Name column can vary; try common ones
    name_col = None
    for cand in ("description", "name", "beneficiary", "narration"):
        try:
            name_col = _find_column(pastel, {cand})
            break
        except Exception:
            continue

    if name_col is None:
        # fallback: if not found, we can still do Stage A strictly
        name_col = None

    # Preserve original index explicitly
    pastel["_ORIG_IDX"] = pastel.index

    pastel["_CREDIT_AMT"] = pastel[credit_col].apply(safe_to_float).round(2)
    pastel["_DEBIT_AMT"] = pastel[debit_col].apply(safe_to_float).round(2)
    pastel["_REF"] = pastel[ref_col].astype(str).str.strip()

    if name_col:
        pastel["_NAME_TOKENS"] = pastel[name_col].apply(_normalize_name_tokens)
    else:
        pastel["_NAME_TOKENS"] = [tuple()] * len(pastel)

    credits = pastel[pastel["_CREDIT_AMT"] > 0].copy()
    debits = pastel[pastel["_DEBIT_AMT"] > 0].copy()

    # ----------------------------
    # STAGE A: REF + AMOUNT
    # ----------------------------
    credit_map = defaultdict(list)  # (ref, amt) -> [orig_idx]
    debit_map = defaultdict(list)

    for _, r in credits.iterrows():
        key = (r["_REF"], r["_CREDIT_AMT"])
        credit_map[key].append(r["_ORIG_IDX"])

    for _, r in debits.iterrows():
        key = (r["_REF"], r["_DEBIT_AMT"])
        debit_map[key].append(r["_ORIG_IDX"])

    audit_rows = []
    remove_ids = set()

    for key in set(credit_map.keys()) & set(debit_map.keys()):
        c_list = credit_map[key]
        d_list = debit_map[key]
        pair_count = min(len(c_list), len(d_list))

        for i in range(pair_count):
            c_id = c_list[i]
            d_id = d_list[i]
            remove_ids.add(c_id)
            remove_ids.add(d_id)
            audit_rows.append({
                "Reference": key[0],
                "Credit_Amount": key[1],
                "Debit_Amount": key[1],
                "STATUS": "INTERNALLY_NETTED_REF_AMOUNT",
            })

    # Remaining after Stage A
    rem_credits = credits.loc[~credits["_ORIG_IDX"].isin(remove_ids)].copy()
    rem_debits = debits.loc[~debits["_ORIG_IDX"].isin(remove_ids)].copy()

    # ----------------------------
    # STAGE B: NAME + AMOUNT (safe)
    # ----------------------------
    # Group by amount to ensure we only compare like-for-like
    # We DO NOT merge. We do indexed token matching.
    credits_by_amt = defaultdict(list)
    debits_by_amt = defaultdict(list)

    for _, r in rem_credits.iterrows():
        credits_by_amt[r["_CREDIT_AMT"]].append(r)

    for _, r in rem_debits.iterrows():
        debits_by_amt[r["_DEBIT_AMT"]].append(r)

    for amt in set(credits_by_amt.keys()) & set(debits_by_amt.keys()):
        c_rows = credits_by_amt[amt]
        d_rows = debits_by_amt[amt]

        # Build token -> debit ORIG_IDX index for this amount bucket
        token_to_debit_ids = defaultdict(list)
        debit_tokens = {}
        debit_ref = {}
        for r in d_rows:
            d_id = r["_ORIG_IDX"]
            toks = r["_NAME_TOKENS"] or tuple()
            debit_tokens[d_id] = toks
            debit_ref[d_id] = r["_REF"]
            for t in set(toks):
                token_to_debit_ids[t].append(d_id)

        used_debits = set()

        # Optional safety: if bucket is huge, we still use token index,
        # but we avoid any naive scans.
        bucket_size = len(c_rows) + len(d_rows)

        for r in c_rows:
            c_id = r["_ORIG_IDX"]
            c_toks = r["_NAME_TOKENS"] or tuple()

            if not c_toks:
                continue

            # Candidate scoring via token hits
            hit_counts = Counter()
            for t in set(c_toks):
                for d_id in token_to_debit_ids.get(t, []):
                    if d_id in used_debits:
                        continue
                    hit_counts[d_id] += 1

            if not hit_counts:
                continue

            # Filter to "acceptable" candidates using your controlled match gate
            # Prefer more token overlap first
            candidates = []
            for d_id, overlap in hit_counts.items():
                if overlap <= 0:
                    continue
                if _strong_name_match(c_toks, debit_tokens.get(d_id, tuple())):
                    candidates.append((overlap, d_id))

            if not candidates:
                continue

            # Choose best candidate: highest overlap first (stable)
            candidates.sort(reverse=True, key=lambda x: x[0])
            best_overlap, best_debit_id = candidates[0]

            # Net it (one-to-one)
            used_debits.add(best_debit_id)
            remove_ids.add(c_id)
            remove_ids.add(best_debit_id)

            audit_rows.append({
                "Reference": f"{r['_REF']} ↔ {debit_ref.get(best_debit_id, '')}".strip(),
                "Credit_Amount": amt,
                "Debit_Amount": amt,
                "STATUS": "INTERNALLY_NETTED_NAME_AMOUNT",
            })

            # If bucket is enormous, allow early exit once one side exhausted
            if bucket_size > MAX_BUCKET_SCAN:
                # If we already matched a lot, we can stop early if debits are exhausted
                if len(used_debits) >= len(d_rows):
                    break

    # ----------------------------
    # FINAL: build remaining + audit
    # ----------------------------
    remaining = pastel.loc[~pastel["_ORIG_IDX"].isin(remove_ids)].copy()

    remaining.drop(
        columns=["_CREDIT_AMT", "_DEBIT_AMT", "_REF", "_ORIG_IDX", "_NAME_TOKENS"],
        inplace=True,
        errors="ignore"
    )

    audit = pd.DataFrame(audit_rows)

    return remaining, audit
