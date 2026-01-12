import pandas as pd


def net_credit_debit(pastel):
    credits = pastel[pastel["Credit"] > 0].copy().reset_index()
    debits = pastel[pastel["Debit"] > 0].copy().reset_index()

    credits["NET_KEY"] = credits["Credit"].astype(str)
    debits["NET_KEY"] = debits["Debit"].astype(str)

    netted = credits.merge(
        debits,
        on="NET_KEY",
        how="inner",
        suffixes=("_credit", "_debit")
    )

    netted = netted.groupby("NET_KEY").head(1)

    audit = pd.DataFrame({
        "Credit_Reference": netted["Reference_credit"],
        "Credit_Amount": netted["Credit"],
        "Debit_Reference": netted["Reference_debit"],
        "Debit_Amount": netted["Debit"],
        "STATUS": "INTERNALLY_NETTED"
    })

    remove_idx = (
        netted["index_credit"].tolist()
        + netted["index_debit"].tolist()
    )

    remaining = pastel.drop(pastel.index[remove_idx])

    return remaining, audit
