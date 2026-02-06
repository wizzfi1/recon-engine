import pandas as pd


class DataValidationError(Exception):
    pass


def validate_numeric_column(df, column, sheet_name):
    errors = []

    for idx, value in df[column].items():
        try:
            float(str(value).replace(",", "").strip())
        except:
            errors.append({
                "sheet": sheet_name,
                "row": idx + 2,
                "column": column,
                "value": value,
                "message": f"Invalid numeric value: {value}"
            })

    return errors


def annotate_errors(df, errors):
    df = df.copy()

    if "VALIDATION_ERRORS" not in df.columns:
        df["VALIDATION_ERRORS"] = ""

    for err in errors:
        row = err["row"] - 2
        existing = str(df.loc[row, "VALIDATION_ERRORS"]).strip()

        msg = f'{err["column"]}: {err["message"]}'

        if existing:
            df.loc[row, "VALIDATION_ERRORS"] = existing + " | " + msg
        else:
            df.loc[row, "VALIDATION_ERRORS"] = msg

    return df


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
