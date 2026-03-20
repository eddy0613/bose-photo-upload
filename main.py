import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai
from PIL import Image

app = FastAPI(title="Bose Photo Upload Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

TEMPLATES_DIR = Path(__file__).parent / "templates"

GEMINI_SYSTEM_PROMPT = """You are a Bose product support expert. Analyze the photos of the Bose product provided.

1. Identify the exact Bose product model if visible
2. Look for any visible issues: physical damage, dirty ports, LED indicator states, connection issues
3. Based on what you see, provide step-by-step troubleshooting instructions specific to this product
4. Keep the response conversational and suitable for being read aloud over a phone call
5. Be specific: "Press the power button on the right ear cup for 3 seconds" not "press the power button"
6. If you cannot identify the product or see any obvious issues, ask for clarification about the specific problem

Supported products include: QuietComfort 45, QC35 II, QC Ultra, Headphones 700, Sport Earbuds, QuietComfort Earbuds, SoundLink Flex, SoundLink Color, SoundLink Mini, Home Speaker 300/500, Smart Speaker 300/500, Soundbar 300/500/700/900, Frames, Sleepbuds, and all other Bose products."""


def get_session_dir(session_id: str) -> Path:
    # Validate session_id is a valid UUID to prevent path traversal
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    return UPLOAD_DIR / session_id


@app.get("/upload/{session_id}", response_class=HTMLResponse)
async def upload_page(session_id: str):
    """Serve the mobile-friendly upload page."""
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    template_path = TEMPLATES_DIR / "upload.html"
    html = template_path.read_text()
    html = html.replace("{{SESSION_ID}}", session_id)
    return HTMLResponse(content=html)


@app.post("/upload/{session_id}")
async def upload_photos(session_id: str, files: list[UploadFile] = File(...)):
    """Accept multipart photo uploads."""
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            continue

        # Generate safe filename
        ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
        safe_name = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = session_dir / safe_name

        content = await file.read()
        file_path.write_bytes(content)
        saved.append(safe_name)

    if not saved:
        raise HTTPException(status_code=400, detail="No valid image files uploaded")

    return {"success": True, "count": len(saved), "files": saved}


@app.get("/status/{session_id}")
async def check_status(session_id: str):
    """Return upload status for a session."""
    session_dir = get_session_dir(session_id)

    if not session_dir.exists():
        return {"uploaded": False, "count": 0, "photos": []}

    photos = [f.name for f in session_dir.iterdir() if f.is_file()]
    return {"uploaded": len(photos) > 0, "count": len(photos), "photos": photos}


@app.post("/analyse/{session_id}")
async def analyse_photos(session_id: str):
    """Analyze uploaded photos using Gemini Vision API."""
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured")

    session_dir = get_session_dir(session_id)
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="No photos found for this session")

    photo_paths = [f for f in session_dir.iterdir() if f.is_file()]
    if not photo_paths:
        raise HTTPException(status_code=404, detail="No photos found for this session")

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    images = []
    for path in photo_paths:
        try:
            img = Image.open(path)
            images.append(img)
        except Exception:
            continue

    if not images:
        raise HTTPException(status_code=400, detail="Could not process uploaded images")

    content = [GEMINI_SYSTEM_PROMPT, "\nPlease analyze these photos of the Bose product:"]
    content.extend(images)

    response = model.generate_content(content)

    return {"success": True, "analysis": response.text, "photos_analysed": len(images)}


@app.delete("/session/{session_id}")
async def cleanup_session(session_id: str):
    """Clean up uploaded photos for a session."""
    session_dir = get_session_dir(session_id)
    if session_dir.exists():
        shutil.rmtree(session_dir)
    return {"success": True}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
