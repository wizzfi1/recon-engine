import pandas as pd


class DataValidationError(Exception):
    """Raised when validation errors are found."""
    def __init__(self, errors):
        self.errors = errors
        super().__init__(self._format())

    def _format(self):
        lines = ["DATA VALIDATION FAILED:\n"]
        for e in self.errors:
            lines.append(
                f"- Sheet: {e['sheet']}, "
                f"Row: {e['row']}, "
                f"Column: {e['column']} → {e['message']}"
            )
        return "\n".join(lines)


def _is_numeric(val):
    try:
        float(str(val).replace(",", "").strip())
        return True
    except:
        return False


def validate_numeric_column(df, column, sheet_name):
    errors = []

    for idx, value in df[column].items():
        if pd.isna(value) or value == "":
            continue

        if not _is_numeric(value):
            errors.append({
                "sheet": sheet_name,
                "row": idx + 2,   # Excel row number
                "column": column,
                "value": value,
                "message": f"Invalid numeric value: {value}"
            })

    return errors


def validate_all(pastel, ixtrac, pastel_cols, ixtrac_cols):
    errors = []

    errors += validate_numeric_column(
        pastel, pastel_cols["debit"], "PASTEL"
    )
    errors += validate_numeric_column(
        pastel, pastel_cols["credit"], "PASTEL"
    )
    errors += validate_numeric_column(
        ixtrac, ixtrac_cols["net_amt"], "IXTRAC"
    )

    if errors:
        raise DataValidationError(errors)


def annotate_errors(df, errors, sheet_name):
    """
    Writes validation errors into the next available column
    of the dataframe, without mutating existing columns.
    """
    df = df.copy()

    sheet_errors = [e for e in errors if e["sheet"] == sheet_name]
    if not sheet_errors:
        return df

    # Find next empty column name
    base = "DATA_ERRORS"
    col = base
    i = 1
    while col in df.columns:
        col = f"{base}_{i}"
        i += 1

    df[col] = ""

    for err in sheet_errors:
        row_idx = err["row"] - 2  # Convert Excel row → pandas index
        msg = f"{err['column']}: {err['message']}"
        df.at[row_idx, col] = msg

    return df
