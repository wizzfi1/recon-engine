import pandas as pd


def write_excel(
    output_file,
    merged,
    matched,
    ref_mismatch_name_amount_match,
    pastel_unmatched,
    ixtrac_unmatched,
    netted,
    remaining_credits,
    summary,
):

    df = merged.copy()

    # =====================================================
    # NAME NORMALISATION (CARDINALITY SAFE)
    # =====================================================
    EXCLUDE_WORDS = {
        "ESTATE", "OF", "THE",
        "ADMIN", "ADMINISTRATOR", "ADMINISTRATORS",
        "ADMOR", "ADMORS",
        "TO", "AND"
    }

    def normalise_tokens(text):
        if pd.isna(text):
            return []
        text = (
            str(text)
            .upper()
            .replace("&", " ")
            .replace("-", " ")
        )
        return [
            t for t in text.split()
            if t not in EXCLUDE_WORDS
        ]

    df["PASTEL_TOKENS"] = df["Description"].apply(normalise_tokens)
    df["IXTRAC_TOKENS"] = df["NAME"].apply(normalise_tokens)

    # =====================================================
    # TOKEN MATCHING WITH PREFIX SUPPORT
    # =====================================================
    def token_match(a, b):
        if a == b:
            return True
        if len(a) >= 2 and len(b) >= 2:
            return a.startswith(b) or b.startswith(a)
        return False

    def overlap_score(row):
        ix = row["IXTRAC_TOKENS"].copy()
        score = 0
        for p in row["PASTEL_TOKENS"]:
            for i in ix:
                if token_match(p, i):
                    score += 1
                    ix.remove(i)
                    break
        return score

    df["CLEAN_NAME_SCORE"] = df.apply(overlap_score, axis=1)
    df["PASTEL_TOKEN_COUNT"] = df["PASTEL_TOKENS"].apply(len).clip(lower=1)

    # =====================================================
    # NAME CLASSIFICATION
    # =====================================================
    def classify(row):
        if row["CLEAN_NAME_SCORE"] >= row["PASTEL_TOKEN_COUNT"]:
            return "ALL_NAMES_MATCH"
        if row["CLEAN_NAME_SCORE"] >= 2:
            return "ANY_TWO_NAMES_MATCH"
        if (
            row["CLEAN_NAME_SCORE"] == 1 and
            (len(row["PASTEL_TOKENS"]) == 1 or len(row["IXTRAC_TOKENS"]) == 1)
        ):
            return "SINGLE_ABBREVIATED_NAME_MATCH"
        return "NO_STRONG_MATCH"

    df["NAME_MATCH_TYPE"] = df.apply(classify, axis=1)

    df["CONFIRMED_NAME_RULE"] = df["NAME_MATCH_TYPE"].isin({
        "ALL_NAMES_MATCH",
        "ANY_TWO_NAMES_MATCH",
        "SINGLE_ABBREVIATED_NAME_MATCH",
    })

    # =====================================================
    # POSTING RULE (THIS IS THE KEY FIX)
    # =====================================================
    df["POSTABLE_RULE"] = (
        (df["REFERENCE_MATCH"] == True) &
        (df["CONFIRMED_NAME_RULE"])
    )

    postable_for_pastel = df[df["POSTABLE_RULE"]].copy()
    postable_for_ixtrac = df[df["POSTABLE_RULE"]].copy()

    # =====================================================
    # ACTION LISTS
    # =====================================================
    remaining = df[~df["POSTABLE_RULE"]].copy()

    remaining["REVIEW_FOCUS"] = "BOTH"
    remaining["NEXT_ACTION"] = "Joint review required"
    remaining["RECOMMENDED_FIX"] = "Verify beneficiary identity across systems"

    # =====================================================
    # WRITE EXCEL
    # =====================================================
    summary_df = pd.DataFrame(summary.items(), columns=["Metric", "Value"])

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        matched.to_excel(writer, "CONFIRMED_REF_NAME", index=False)
        df[df["CONFIRMED_NAME_RULE"]].to_excel(writer, "CONFIRMED_NAME_AMOUNT", index=False)

        postable_for_pastel.to_excel(writer, "POSTABLE_FOR_PASTEL", index=False)
        postable_for_ixtrac.to_excel(writer, "POSTABLE_FOR_IXTRAC", index=False)

        remaining.to_excel(writer, "REF_MISMATCH_REMAINING", index=False)

        pastel_unmatched.to_excel(writer, "PASTEL_UNMATCHED", index=False)
        ixtrac_unmatched.to_excel(writer, "IXTRAC_UNMATCHED", index=False)
        netted.to_excel(writer, "CREDIT_DEBIT_NETTED", index=False)
        remaining_credits.to_excel(writer, "PASTEL_REMAINING_CREDITS", index=False)
        summary_df.to_excel(writer, "RECON_SUMMARY", index=False)
