import pandas as pd


def _find_column(df, candidates):
    """
    Find a column in df whose lowercase stripped name
    matches one of the candidate names.
    """
    for col in df.columns:
        if col.strip().lower() in candidates:
            return col
    raise KeyError(
        f"None of {candidates} found in columns: {df.columns.tolist()}"
    )


def net_credit_debit(pastel: pd.DataFrame):
    """
    Internally net Credit vs Debit entries in Pastel.

    Rules:
    - Credit > 0 can net against Debit > 0
    - One-to-one matching by amount
    - Netted entries are removed from further reconciliation
    - Netted pairs are returned as an audit trail
    """

    pastel = pastel.copy()

    # --- robust column detection ---
    credit_col = _find_column(pastel, {"credit"})
    debit_col = _find_column(pastel, {"debit"})
    reference_col = _find_column(pastel, {"reference"})

    # --- split legs ---
    credits = pastel[pastel[credit_col] > 0].copy().reset_index()
    debits = pastel[pastel[debit_col] > 0].copy().reset_index()

    # --- build netting keys (amount-based) ---
    credits["NET_KEY"] = credits[credit_col].astype(str)
    debits["NET_KEY"] = debits[debit_col].astype(str)

    # --- one-to-one internal netting ---
    netted = credits.merge(
        debits,
        on="NET_KEY",
        how="inner",
        suffixes=("_credit", "_debit")
    )

    # enforce strict one-to-one
    netted = netted.groupby("NET_KEY", as_index=False).head(1)

    # --- audit trail ---
    audit = pd.DataFrame({
        "Credit_Reference": netted[f"{reference_col}_credit"],
        "Credit_Amount": netted[f"{credit_col}_credit"],
        "Debit_Reference": netted[f"{reference_col}_debit"],
        "Debit_Amount": netted[f"{debit_col}_debit"],
        "STATUS": "INTERNALLY_NETTED"
    })

    # --- remove netted legs from pastel ---
    remove_idx = (
        netted["index_credit"].tolist()
        + netted["index_debit"].tolist()
    )

    remaining = pastel.drop(pastel.index[remove_idx])

    return remaining, audit
