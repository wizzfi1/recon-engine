import pandas as pd


def _find_column(df, candidates):
    for col in df.columns:
        if col.strip().lower() in candidates:
            return col
    raise KeyError(
        f"None of {candidates} found in columns: {df.columns.tolist()}"
    )


def net_credit_debit(pastel: pd.DataFrame):
    """
    Internal netting using:
    - Reference
    - Amount

    One-to-one, deterministic, scalable.
    """

    pastel = pastel.copy()

    credit_col = _find_column(pastel, {"credit"})
    debit_col = _find_column(pastel, {"debit"})
    ref_col = _find_column(pastel, {"reference"})

    pastel["_CREDIT_AMT"] = pastel[credit_col].fillna(0).round(2)
    pastel["_DEBIT_AMT"] = pastel[debit_col].fillna(0).round(2)
    pastel["_REF"] = pastel[ref_col].astype(str).str.strip()

    credits = pastel[pastel["_CREDIT_AMT"] > 0].copy().reset_index()
    debits = pastel[pastel["_DEBIT_AMT"] > 0].copy().reset_index()

    # Build strict matching key
    credits["NET_KEY"] = (
        credits["_REF"] + "|" +
        credits["_CREDIT_AMT"].astype(str)
    )

    debits["NET_KEY"] = (
        debits["_REF"] + "|" +
        debits["_DEBIT_AMT"].astype(str)
    )

    # One-to-one matching
    netted = credits.merge(
        debits,
        on="NET_KEY",
        how="inner",
        suffixes=("_credit", "_debit")
    )

    # Enforce strict 1–1
    netted = netted.groupby("NET_KEY", as_index=False).head(1)

    # Audit trail
    audit = pd.DataFrame({
        "Reference": netted["_REF_credit"],
        "Credit_Amount": netted["_CREDIT_AMT_credit"],
        "Debit_Amount": netted["_DEBIT_AMT_debit"],
        "STATUS": "INTERNALLY_NETTED_REF_AMOUNT"
    })

    remove_idx = (
        netted["index_credit"].tolist()
        + netted["index_debit"].tolist()
    )

    remaining = pastel.drop(pastel.index[remove_idx])

    remaining = remaining.drop(
        columns=["_CREDIT_AMT", "_DEBIT_AMT", "_REF"],
        errors="ignore"
    )

    return remaining, audit
