from io import BytesIO
import pandas as pd


def enforce_excel_safe(df):
    df = df.copy(deep=True)
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: ", ".join(map(str, x))
            if isinstance(x, (list, set, tuple, dict))
            else x
        )
    return df


def write_excel(
    output_file,
    matched,
    ref_mismatch_name_amount_match,
    reviewed_matches,
    pastel_outstanding,
    ixtrac_outstanding,
    netted,
    remaining_credits,
    summary,
):
    summary_df = pd.DataFrame(summary.items(), columns=["Metric", "Value"])

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        workbook = writer.book

        # ===============================
        # RAW DATA SHEETS
        # ===============================
        enforce_excel_safe(matched).to_excel(
            excel_writer=writer, sheet_name="CONFIRMED", index=False
        )
        enforce_excel_safe(ref_mismatch_name_amount_match).to_excel(
            excel_writer=writer, sheet_name="REF_MISMATCH", index=False
        )
        enforce_excel_safe(reviewed_matches).to_excel(
            excel_writer=writer, sheet_name="REVIEWED_MATCHES", index=False
        )
        enforce_excel_safe(pastel_outstanding).to_excel(
            excel_writer=writer, sheet_name="PASTEL_OUTSTANDING", index=False
        )
        enforce_excel_safe(ixtrac_outstanding).to_excel(
            excel_writer=writer, sheet_name="IXTRAC_OUTSTANDING", index=False
        )
        enforce_excel_safe(netted).to_excel(
            excel_writer=writer, sheet_name="NETTED", index=False
        )
        enforce_excel_safe(remaining_credits).to_excel(
            excel_writer=writer, sheet_name="REMAINING_CREDITS", index=False
        )
        summary_df.to_excel(
            excel_writer=writer, sheet_name="SUMMARY", index=False
        )

        # ===============================
        # DASHBOARD
        # ===============================
        dashboard = workbook.add_worksheet("DASHBOARD")

        title_fmt = workbook.add_format({"bold": True, "font_size": 16})
        kpi_label_fmt = workbook.add_format({
            "bold": True, "border": 1, "align": "center"
        })
        kpi_value_fmt = workbook.add_format({
            "bold": True, "border": 1, "align": "center", "font_size": 14
        })

        dashboard.merge_range("B2:H2", "RECONCILIATION DASHBOARD", title_fmt)

        summary_map = dict(summary)

        # --- source-of-truth values ---
        pastel_total = summary_map.get("Pastel Total", 0)
        ixtrac_total = summary_map.get("IX TRAC Total", 0)
        confirmed = summary_map.get("Confirmed", 0)
        reviewed = summary_map.get("Reviewed Matches", 0)
        outstanding = (
            summary_map.get("Pastel Outstanding", 0)
            + summary_map.get("IXTRAC Outstanding", 0)
        )
        netted_count = summary_map.get("Internally Netted", 0)
        ref_mismatch = summary_map.get("Ref Mismatch Candidates", 0)

        # ===============================
        # KPI TILES
        # ===============================
        kpis = [
            ("Pastel Rows", pastel_total),
            ("IXTRAC Rows", ixtrac_total),
            ("Confirmed", confirmed),
            ("Reviewed", reviewed),
            ("Outstanding", outstanding),
            ("Netted", netted_count),
            ("Ref Mismatch", ref_mismatch),
        ]

        row, col = 4, 1
        for label, value in kpis:
            dashboard.write(row, col, label, kpi_label_fmt)
            dashboard.write(row + 1, col, value, kpi_value_fmt)
            col += 2
            if col > 7:
                col = 1
                row += 3

        # ===============================
        # CHART DATA TABLE
        # ===============================
        chart_row = 15

        dashboard.write_row(chart_row, 1, [
            "Confirmed",
            "Reviewed",
            "Outstanding",
            "Ref Mismatch",
        ])

        dashboard.write_row(chart_row + 1, 1, [
            confirmed,
            reviewed,
            outstanding,
            ref_mismatch,
        ])

        # ===============================
        # BAR CHART
        # ===============================
        bar = workbook.add_chart({"type": "column"})
        bar.add_series({
            "categories": ["DASHBOARD", chart_row, 1, chart_row, 4],
            "values": ["DASHBOARD", chart_row + 1, 1, chart_row + 1, 4],
            "data_labels": {"value": True},
        })
        bar.set_title({"name": "Match Quality Overview"})
        dashboard.insert_chart("B10", bar, {"x_scale": 1.4, "y_scale": 1.3})

        # ===============================
        # PIE CHART
        # ===============================
        pie = workbook.add_chart({"type": "pie"})
        pie.add_series({
            "categories": ["DASHBOARD", chart_row, 1, chart_row, 4],
            "values": ["DASHBOARD", chart_row + 1, 1, chart_row + 1, 4],
            "data_labels": {"percentage": True},
        })
        pie.set_title({"name": "Reconciliation Distribution"})
        dashboard.insert_chart("F10", pie, {"x_scale": 1.3, "y_scale": 1.3})

        dashboard.set_column("B:H", 18)
