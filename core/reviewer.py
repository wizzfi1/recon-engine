import re

BUSINESS_STOPWORDS = {
    "ltd", "limited", "nigeria", "plc", "corp", "corporation",
    "trading", "trad", "services", "service", "company", "co"
}

def normalize_name(text):
    text = re.sub(r"[^a-z0-9 ]", "", str(text).lower())
    tokens = set(text.split())
    return {t for t in tokens if t not in BUSINESS_STOPWORDS}

def normalize_amount(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return None

def normalize_ref(val):
    try:
        return str(int(float(str(val).strip()))).strip()
    except:
        return str(val).strip()


# ----------------------------
# REVIEW PASTEL → IXTRAC
# ----------------------------
def review_pastel_against_ixtrac(
    pastel_unmatched,
    original_ixtrac,
    pastel_amt_col,
    ixtrac_amt_col,
    pastel_ref_col,
    ixtrac_ref_col,
    pastel_name_col,
    ixtrac_name_col,
):
    reviewed_pairs = []
    outstanding = []
    used_ixtrac = set()

    for _, p in pastel_unmatched.iterrows():
        matched = False

        p_amt = normalize_amount(p[pastel_amt_col])
        p_ref = normalize_ref(p[pastel_ref_col])
        p_names = normalize_name(p[pastel_name_col])

        if p_amt is None or len(p_names) < 2:
            outstanding.append(p)
            continue

        for _, x in original_ixtrac.iterrows():
            if x.name in used_ixtrac:
                continue

            x_ref = normalize_ref(x[ixtrac_ref_col])
            if x_ref != p_ref:
                continue

            x_amt = normalize_amount(x[ixtrac_amt_col])
            x_names = normalize_name(x[ixtrac_name_col])
            if x_amt is None:
                continue

            name_overlap = len(p_names & x_names)
            if name_overlap < 2:
                continue

            # Rule A1: Exact amount
            if abs(p_amt - x_amt) < 0.01:
                reviewed_pairs.append((p.copy(), x.copy(), "EXACT_AMT+2NAME+REF"))
                used_ixtrac.add(x.name)
                matched = True
                break

            # Rule A2: Whole amount
            if int(p_amt) == int(x_amt):
                reviewed_pairs.append((p.copy(), x.copy(), "WHOLE_AMT+2NAME+REF"))
                used_ixtrac.add(x.name)
                matched = True
                break

        if not matched:
            outstanding.append(p)

    return reviewed_pairs, pastel_unmatched.loc[[r.name for r in outstanding]].copy()


# ----------------------------
# REVIEW IXTRAC → PASTEL
# ----------------------------
def review_ixtrac_against_pastel(
    ixtrac_unmatched,
    original_pastel,
    ixtrac_amt_col,
    pastel_amt_col,
    ixtrac_ref_col,
    pastel_ref_col,
    ixtrac_name_col,
    pastel_name_col,
):
    reviewed_pairs = []
    outstanding = []
    used_pastel = set()

    for _, x in ixtrac_unmatched.iterrows():
        matched = False

        x_amt = normalize_amount(x[ixtrac_amt_col])
        x_ref = normalize_ref(x[ixtrac_ref_col])
        x_names = normalize_name(x[ixtrac_name_col])

        if x_amt is None or len(x_names) < 2:
            outstanding.append(x)
            continue

        for _, p in original_pastel.iterrows():
            if p.name in used_pastel:
                continue

            p_ref = normalize_ref(p[pastel_ref_col])
            if p_ref != x_ref:
                continue

            p_amt = normalize_amount(p[pastel_amt_col])
            p_names = normalize_name(p[pastel_name_col])
            if p_amt is None:
                continue

            name_overlap = len(x_names & p_names)
            if name_overlap < 2:
                continue

            # Rule B1: Exact amount
            if abs(x_amt - p_amt) < 0.01:
                reviewed_pairs.append((p.copy(), x.copy(), "EXACT_AMT+2NAME+REF"))
                used_pastel.add(p.name)
                matched = True
                break

            # Rule B2: Whole amount
            if int(x_amt) == int(p_amt):
                reviewed_pairs.append((p.copy(), x.copy(), "WHOLE_AMT+2NAME+REF"))
                used_pastel.add(p.name)
                matched = True
                break

        if not matched:
            outstanding.append(x)

    return reviewed_pairs, ixtrac_unmatched.loc[[r.name for r in outstanding]].copy()
