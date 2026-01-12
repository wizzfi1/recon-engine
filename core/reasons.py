import pandas as pd


def pastel_reason(row):
    """
    Classify why a Pastel entry failed reconciliation.
    """

    # 1️⃣ No IX TRAC candidate at all
    if row.get("MATCH_STATUS") == "NO_IXTRAC":
        return "NO_MATCH_IN_IXTRAC"

    # 2️⃣ Reference mismatch
    pastel_ref = str(row.get("Reference")).strip()
    ixtrac_ref = str(row.get("WARRANT NO")).strip()

    if pastel_ref != ixtrac_ref:
        return "REFERENCE_MISMATCH"

    # 3️⃣ Name mismatch
    if row.get("NAME_SCORE", 0) < 2:
        return "NAME_MISMATCH"

    return "P00_UNKNOWN"


def ixtrac_reason(row):
    return "NO_MATCH_IN_PASTEL"
