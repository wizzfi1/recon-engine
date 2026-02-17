import pandas as pd
import re


BUSINESS_STOPWORDS = {
    "ltd", "limited", "nigeria", "plc", "corp", "corporation",
    "trading", "trad", "services", "service", "company", "co",
    "the", "estate", "est", "of"
}

_non_alnum = re.compile(r"[^a-z0-9 ]+")


def safe_to_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return 0.0


def _find_column(df, candidates):
    for col in df.columns:
        if col.strip().lower() in candidates:
            return col
    raise KeyError(f"None of {candidates} found in columns: {df.columns.tolist()}")


def _name_key(text: str) -> str:
    """
    Normalized name key:
    - lower
    - remove non-alphanumeric
    - remove stopwords
    - sort tokens (so word order doesn't matter)
    """
    text = _non_alnum.sub(" ", str(text).lower())
    tokens = [t for t in text.split() if t and t not in BUSINESS_STOPWORDS]
    if not tokens:
        return ""
    tokens.sort()
    return " ".join(tokens)


def _strong_name_match(a_key: str, b_key: str) -> bool:
    """
    Controlled name match gate:

    Allow if:
      - >=2 shared tokens, OR
      - exactly 1 shared token, but it is a "strong" token
        (len>=6 and not numeric)

    This supports cases like: "EST OF OGUNDELE" -> {"ogundele"} (single strong token)
    """
    a = set(a_key.split()) if a_key else set()
    b = set(b_key.split()) if b_key else set()
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
    Internally net Pastel credits vs debits.

    Stage A (strict):
      NET_KEY = REF|AMT

    Stage B (fallback):
      NET_KEY = NAMEKEY|AMT   (only if strong name overlap, amount same)

    This solves cases like:
      Ref=233 (credit) vs Ref=TRF (debit) but same beneficiary + amount.
    """

    pastel = pastel.copy()

    credit_col = _find_column(pastel, {"credit"})
    debit_col = _find_column(pastel, {"debit"})
    ref_col = _find_column(pastel, {"reference"})

    # Try common name columns (Pastel usually has Description)
    # If your Pastel uses another column, add it here.
    try:
        name_col = _find_column(pastel, {"description", "name", "beneficiary"})
    except KeyError:
        name_col = None  # fallback netting by name will be skipped if not found

    pastel["_ORIG_IDX"] = pastel.index

    # Normalize amounts as absolute (we only care that credit and debit have same magnitude)
    pastel["_CREDIT_AMT"] = pastel[credit_col].apply(safe_to_float).abs().round(2)
    pastel["_DEBIT_AMT"] = pastel[debit_col].apply(safe_to_float).abs().round(2)
    pastel["_REF"] = pastel[ref_col].astype(str).str.strip()

    if name_col:
        pastel["_NAMEKEY"] = pastel[name_col].apply(_name_key)
    else:
        pastel["_NAMEKEY"] = ""

    credits = pastel[pastel["_CREDIT_AMT"] > 0].copy()
    debits = pastel[pastel["_DEBIT_AMT"] > 0].copy()

    # =========================
    # STAGE A: REF + AMT netting
    # =========================
    credits["NET_KEY_A"] = credits["_REF"] + "|" + credits["_CREDIT_AMT"].astype(str)
    debits["NET_KEY_A"] = debits["_REF"] + "|" + debits["_DEBIT_AMT"].astype(str)

    credits["_SEQ_A"] = credits.groupby("NET_KEY_A").cumcount()
    debits["_SEQ_A"] = debits.groupby("NET_KEY_A").cumcount()

    paired_a = credits.merge(
        debits,
        on=["NET_KEY_A", "_SEQ_A"],
        how="inner",
        suffixes=("_credit", "_debit")
    )

    audit_a = pd.DataFrame({
        "Reference_Credit": paired_a["_REF_credit"],
        "Reference_Debit": paired_a["_REF_debit"],
        "Name": paired_a["_NAMEKEY_credit"],
        "Credit_Amount": paired_a["_CREDIT_AMT_credit"],
        "Debit_Amount": paired_a["_DEBIT_AMT_debit"],
        "STATUS": "INTERNALLY_NETTED_REF_AMOUNT"
    })

    remove_ids_a = (
        paired_a["_ORIG_IDX_credit"].tolist()
        + paired_a["_ORIG_IDX_debit"].tolist()
    )

    remaining = pastel.loc[~pastel["_ORIG_IDX"].isin(remove_ids_a)].copy()

    # =========================
    # STAGE B: NAME + AMT netting (fallback)
    # =========================
    audit_b = pd.DataFrame()

    if name_col:
        credits_b = remaining[remaining["_CREDIT_AMT"] > 0].copy()
        debits_b = remaining[remaining["_DEBIT_AMT"] > 0].copy()

        # Only consider rows with usable name keys
        credits_b = credits_b[credits_b["_NAMEKEY"].astype(str).str.len() >= 3]
        debits_b = debits_b[debits_b["_NAMEKEY"].astype(str).str.len() >= 3]

        # Candidate key
        credits_b["NET_KEY_B"] = credits_b["_NAMEKEY"] + "|" + credits_b["_CREDIT_AMT"].astype(str)
        debits_b["NET_KEY_B"] = debits_b["_NAMEKEY"] + "|" + debits_b["_DEBIT_AMT"].astype(str)

        # Sequence pairing per key
        credits_b["_SEQ_B"] = credits_b.groupby("NET_KEY_B").cumcount()
        debits_b["_SEQ_B"] = debits_b.groupby("NET_KEY_B").cumcount()

        paired_b = credits_b.merge(
            debits_b,
            on=["NET_KEY_B", "_SEQ_B"],
            how="inner",
            suffixes=("_credit", "_debit")
        )

        # ✅ Safety gate (updated): allow >=2 tokens OR 1 strong token
        keep = []
        for _, row in paired_b.iterrows():
            keep.append(_strong_name_match(row["_NAMEKEY_credit"], row["_NAMEKEY_debit"]))

        paired_b = paired_b[pd.Series(keep, index=paired_b.index)]

        paired_b = paired_b[pd.Series(keep, index=paired_b.index)]

        audit_b = pd.DataFrame({
            "Reference_Credit": paired_b["_REF_credit"],
            "Reference_Debit": paired_b["_REF_debit"],
            "Name": paired_b["_NAMEKEY_credit"],
            "Credit_Amount": paired_b["_CREDIT_AMT_credit"],
            "Debit_Amount": paired_b["_DEBIT_AMT_debit"],
            "STATUS": "INTERNALLY_NETTED_NAME_AMOUNT"
        })

        remove_ids_b = (
            paired_b["_ORIG_IDX_credit"].tolist()
            + paired_b["_ORIG_IDX_debit"].tolist()
        )

        remaining = remaining.loc[~remaining["_ORIG_IDX"].isin(remove_ids_b)].copy()

    # =========================
    # cleanup
    # =========================
    remaining.drop(
        columns=["_CREDIT_AMT", "_DEBIT_AMT", "_REF", "_ORIG_IDX", "_NAMEKEY"],
        inplace=True,
        errors="ignore"
    )

    audit = pd.concat([audit_a, audit_b], ignore_index=True)
    return remaining, audit
