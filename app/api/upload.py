from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
from io import BytesIO

router = APIRouter(prefix="/api", tags=["upload"])

LARGE_FILE_ROWS = 10_000


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    contents = await file.read()

    try:
        xl = pd.ExcelFile(BytesIO(contents))
        first_sheet = xl.sheet_names[0]
        row_count = xl.parse(first_sheet).shape[0]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Excel file")

    return {
        "filename": file.filename,
        "sheets": xl.sheet_names,
        "row_count": row_count,
        "large_file": row_count >= LARGE_FILE_ROWS,
    }
