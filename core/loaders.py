import pandas as pd


def load_excel(file_path, sheet_name):
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    df = df.rename(columns=lambda x: x.strip())
    return df
