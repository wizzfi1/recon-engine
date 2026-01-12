import pandas as pd
from utils.text import name_match_score


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
