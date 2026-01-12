def pastel_reason(row):
    if row.get("WARRANT NO") is None:
        return "P03_NO_MATCH_IN_IXTRAC"
    return "P04_NAME_MISMATCH"


def ixtrac_reason(row):
    return "I03_NO_MATCH_IN_PASTEL"
