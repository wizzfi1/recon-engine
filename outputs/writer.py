# outputs/writer.py
import pandas as pd


def enforce_excel_safe(df):
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: ", ".join(map(str, x))
            if isinstance(x, (list, set, tuple, dict)) else x
        )
    return df


def write_excel(
    output_file,
    matched,
    ref_mismatch,
    reviewed_matches,
    pastel_outstanding,
    ixtrac_outstanding,
    netted,
    remaining_credits,
    summary,
   
):

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:

     
        enforce_excel_safe(matched).to_excel(writer, "CONFIRMED", index=False)
        enforce_excel_safe(ref_mismatch).to_excel(writer, "REF_MISMATCH", index=False)
        enforce_excel_safe(reviewed_matches).to_excel(writer, "REVIEWED_MATCHES", index=False)
        enforce_excel_safe(pastel_outstanding).to_excel(writer, "PASTEL_OUTSTANDING", index=False)
        enforce_excel_safe(ixtrac_outstanding).to_excel(writer, "IXTRAC_OUTSTANDING", index=False)
        enforce_excel_safe(netted).to_excel(writer, "NETTED", index=False)
        enforce_excel_safe(remaining_credits).to_excel(writer, "REMAINING_CREDITS", index=False)

        pd.DataFrame(summary.items(), columns=["Metric", "Value"]).to_excel(
            writer, "SUMMARY", index=False
        )
