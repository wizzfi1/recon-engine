from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.upload import router as upload_router
from app.api.reconcile import router as reconcile_router

app = FastAPI(
    title="Reconciliation Engine",
    version="1.0.0",
)

# Routers
app.include_router(upload_router)
app.include_router(reconcile_router)

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/health")
def health():
    return {"status": "ok"}
