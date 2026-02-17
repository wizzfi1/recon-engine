import pandas as pd
import re


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


# precompiled cleanup regex (commas + whitespace)
_NUM_CLEAN = re.compile(r"[,\s]")


def _to_numeric_series(series: pd.Series) -> pd.Series:
    """
    Fast numeric parsing:
    - strips commas/spaces
    - coerces invalid values to NaN
    """
    s = series.astype(str).str.strip()
    # treat common empties as NA
    s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    s = s.str.replace(_NUM_CLEAN, "", regex=True)
    return pd.to_numeric(s, errors="coerce")


def validate_numeric_column(df, column, sheet_name):
    """
    Vectorized numeric validation (FAST).
    Returns the same error dicts you already use.
    """
    errors = []

    if column not in df.columns:
        errors.append({
            "sheet": sheet_name,
            "row": 1,
            "column": column,
            "value": None,
            "message": f"Missing required column: {column}"
        })
        return errors

    series = df[column]

    # blanks allowed
    blank_mask = series.isna() | (series.astype(str).str.strip() == "")

    numeric = _to_numeric_series(series)

    bad_mask = (~blank_mask) & (numeric.isna())
    if not bad_mask.any():
        return []

    bad_indices = bad_mask[bad_mask].index
    for idx in bad_indices:
        value = series.loc[idx]
        errors.append({
            "sheet": sheet_name,
            "row": int(idx) + 2,  # Excel row number
            "column": column,
            "value": value,
            "message": f"Invalid numeric value: {value}"
        })

    return errors


def validate_all(pastel, ixtrac, pastel_cols, ixtrac_cols):
    errors = []

    errors += validate_numeric_column(pastel, pastel_cols["debit"], "PASTEL")
    errors += validate_numeric_column(pastel, pastel_cols["credit"], "PASTEL")
    errors += validate_numeric_column(ixtrac, ixtrac_cols["net_amt"], "IXTRAC")

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

    # group by row index to avoid repeated writes
    grouped = {}
    for err in sheet_errors:
        row_idx = err["row"] - 2  # Excel row → pandas index
        msg = f"{err['column']}: {err['message']}"
        grouped.setdefault(row_idx, []).append(msg)

    for row_idx, msgs in grouped.items():
        if 0 <= row_idx < len(df):
            df.at[row_idx, col] = " | ".join(msgs)

    return df
