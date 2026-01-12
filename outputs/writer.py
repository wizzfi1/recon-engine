import pandas as pd


def write_excel(
    output_file,
    matched,
    ref_mismatch_name_amount,
    pastel_unmatched,
    ixtrac_unmatched,
    netted,
    summary
):
    summary_df = pd.DataFrame(
        list(summary.items()),
        columns=["Metric", "Value"]
    )

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        matched.to_excel(writer, "MATCHED", index=False)
        ref_mismatch_name_amount.to_excel(
            writer, "REF_MISMATCH_NAME_AMOUNT_MATCH", index=False
        )
        pastel_unmatched.to_excel(writer, "PASTEL_UNMATCHED", index=False)
        ixtrac_unmatched.to_excel(writer, "IXTRAC_UNMATCHED", index=False)
        netted.to_excel(writer, "CREDIT_DEBIT_NETTED", index=False)
        summary_df.to_excel(writer, "RECON_SUMMARY", index=False)
