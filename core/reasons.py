def pastel_reason(row):
    """
    Classify why a Pastel entry failed reconciliation.
    """

    if row.get("MATCH_STATUS") in ("NO_IXTRAC", "NO_VALID_CANDIDATE"):
        return "NO_MATCH_IN_IXTRAC"

    pastel_ref = str(row.get("Reference")).strip()
    ixtrac_ref = str(row.get("WARRANT NO")).strip()

    if pastel_ref != ixtrac_ref:
        return "REFERENCE_MISMATCH"

    if row.get("NAME_SCORE", 0) < 2:
        return "NAME_MISMATCH"

    return "P00_UNKNOWN"


def ixtrac_reason(row):
    return "NO_MATCH_IN_PASTEL"
