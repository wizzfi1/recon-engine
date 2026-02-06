import pandas as pd


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


def net_credit_debit(pastel: pd.DataFrame):
    pastel = pastel.copy()

    credit_col = _find_column(pastel, {"credit"})
    debit_col = _find_column(pastel, {"debit"})
    ref_col = _find_column(pastel, {"reference"})

    # Preserve original index explicitly
    pastel["_ORIG_IDX"] = pastel.index

    pastel["_CREDIT_AMT"] = pastel[credit_col].apply(safe_to_float).round(2)
    pastel["_DEBIT_AMT"] = pastel[debit_col].apply(safe_to_float).round(2)
    pastel["_REF"] = pastel[ref_col].astype(str).str.strip()

    credits = pastel[pastel["_CREDIT_AMT"] > 0].copy()
    debits = pastel[pastel["_DEBIT_AMT"] > 0].copy()

    credits["NET_KEY"] = credits["_REF"] + "|" + credits["_CREDIT_AMT"].astype(str)
    debits["NET_KEY"] = debits["_REF"] + "|" + debits["_DEBIT_AMT"].astype(str)

    netted = credits.merge(
        debits,
        on="NET_KEY",
        how="inner",
        suffixes=("_credit", "_debit")
    ).groupby("NET_KEY", as_index=False).head(1)

    audit = pd.DataFrame({
        "Reference": netted["_REF_credit"],
        "Credit_Amount": netted["_CREDIT_AMT_credit"],
        "Debit_Amount": netted["_DEBIT_AMT_debit"],
        "STATUS": "INTERNALLY_NETTED_REF_AMOUNT"
    })

    # 🔒 SAFE removal using original index values
    remove_ids = (
        netted["_ORIG_IDX_credit"].tolist()
        + netted["_ORIG_IDX_debit"].tolist()
    )

    remaining = pastel.loc[~pastel["_ORIG_IDX"].isin(remove_ids)].copy()

    remaining.drop(
        columns=["_CREDIT_AMT", "_DEBIT_AMT", "_REF", "_ORIG_IDX"],
        inplace=True,
        errors="ignore"
    )

    return remaining, audit
