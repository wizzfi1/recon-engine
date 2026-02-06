from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from datetime import datetime

from app.engine.run import run_web_reconciliation

router = APIRouter(prefix="/api", tags=["reconcile"])

DEFAULT_BASENAME = "RECONCILIATION_OUTPUT"


@router.post("/reconcile")
async def reconcile(
    file: UploadFile = File(...),
    pastel_sheet: str = Form(...),
    ixtrac_sheet: str = Form(...),
    append_timestamp: bool = Form(True),
):
    if pastel_sheet == ixtrac_sheet:
        raise HTTPException(
            status_code=400,
            detail="Pastel and IXTRAC sheets must be different.",
        )

    excel_bytes = await file.read()

    try:
        output_bytes = run_web_reconciliation(
            excel_bytes,
            pastel_sheet,
            ixtrac_sheet,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S") if append_timestamp else ""
    filename = f"{DEFAULT_BASENAME}_{ts}.xlsx" if ts else f"{DEFAULT_BASENAME}.xlsx"

    return StreamingResponse(
        BytesIO(output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )
