def remove_total_rows(df):
    return df[
        ~df.apply(
            lambda r: r.astype(str).str.contains("TOTAL", case=False, na=False).any(),
            axis=1
        )
    ].copy()
