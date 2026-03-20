import os
import uuid
import shutil
import json
import logging
from difflib import SequenceMatcher
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import google.generativeai as genai
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# ---------------------------------------------------------------------------
# Bose product catalog
# ---------------------------------------------------------------------------
BOSE_PRODUCTS = [
    # Headphones
    {"id": "qc45", "name": "QuietComfort 45", "category": "headphones",
     "keywords": ["qc45", "quietcomfort 45", "qc 45", "quiet comfort 45"],
     "common_issues": ["Bluetooth pairing", "battery drain", "ear cushion wear", "audio cutting out"],
     "support_url": "/support/qc45"},
    {"id": "qc35-ii", "name": "QuietComfort 35 II", "category": "headphones",
     "keywords": ["qc35", "qc 35", "quietcomfort 35", "qc35ii", "quiet comfort 35"],
     "common_issues": ["firmware update issues", "microphone quality", "Alexa button", "charging issues"],
     "support_url": "/support/qc35-ii"},
    {"id": "qc-ultra-headphones", "name": "QuietComfort Ultra Headphones", "category": "headphones",
     "keywords": ["qc ultra", "quietcomfort ultra", "qc ultra headphones", "ultra headphones"],
     "common_issues": ["immersive audio mode", "head tracking", "battery life", "pairing"],
     "support_url": "/support/qc-ultra-headphones"},
    {"id": "headphones-700", "name": "Headphones 700", "category": "headphones",
     "keywords": ["headphones 700", "bose 700", "noise cancelling 700", "nc700"],
     "common_issues": ["touch controls", "noise cancellation levels", "call quality", "charging port"],
     "support_url": "/support/headphones-700"},
    {"id": "qc-se", "name": "QuietComfort SE", "category": "headphones",
     "keywords": ["qc se", "quietcomfort se", "quiet comfort se"],
     "common_issues": ["Bluetooth connectivity", "battery", "ear cushions"],
     "support_url": "/support/qc-se"},
    # Earbuds
    {"id": "qc-earbuds-ii", "name": "QuietComfort Earbuds II", "category": "earbuds",
     "keywords": ["qc earbuds ii", "qc earbuds 2", "quietcomfort earbuds ii", "qceb2"],
     "common_issues": ["CustomTune calibration", "ear tip fit", "charging case LED", "one earbud not working"],
     "support_url": "/support/qc-earbuds-ii"},
    {"id": "qc-earbuds", "name": "QuietComfort Earbuds", "category": "earbuds",
     "keywords": ["qc earbuds", "quietcomfort earbuds", "bose earbuds"],
     "common_issues": ["ear tip fit", "charging case", "pairing", "wind noise"],
     "support_url": "/support/qc-earbuds"},
    {"id": "sport-earbuds", "name": "Sport Earbuds", "category": "earbuds",
     "keywords": ["sport earbuds", "bose sport", "sport buds"],
     "common_issues": ["fit and stability", "sweat resistance", "charging", "touch controls"],
     "support_url": "/support/sport-earbuds"},
    {"id": "ultra-open-earbuds", "name": "Ultra Open Earbuds", "category": "earbuds",
     "keywords": ["ultra open", "open earbuds", "ultra open earbuds"],
     "common_issues": ["open fit stability", "Immersive Audio", "pairing", "charging"],
     "support_url": "/support/ultra-open-earbuds"},
    # Portable Speakers
    {"id": "soundlink-flex", "name": "SoundLink Flex", "category": "speakers",
     "keywords": ["soundlink flex", "sound link flex", "flex speaker"],
     "common_issues": ["waterproofing", "speakerphone quality", "Bluetooth range", "battery"],
     "support_url": "/support/soundlink-flex"},
    {"id": "soundlink-flex-2", "name": "SoundLink Flex 2", "category": "speakers",
     "keywords": ["soundlink flex 2", "flex 2", "soundlink flex gen 2"],
     "common_issues": ["pairing multiple devices", "PositionIQ", "charging"],
     "support_url": "/support/soundlink-flex-2"},
    {"id": "soundlink-color-ii", "name": "SoundLink Color II", "category": "speakers",
     "keywords": ["soundlink color", "sound link color", "color ii", "color 2"],
     "common_issues": ["battery life", "charging port", "voice prompts", "pairing"],
     "support_url": "/support/soundlink-color-ii"},
    {"id": "soundlink-mini-ii", "name": "SoundLink Mini II", "category": "speakers",
     "keywords": ["soundlink mini", "sound link mini", "mini ii", "mini 2", "mini speaker"],
     "common_issues": ["charging cradle", "battery replacement", "speakerphone"],
     "support_url": "/support/soundlink-mini-ii"},
    {"id": "soundlink-revolve-plus", "name": "SoundLink Revolve+", "category": "speakers",
     "keywords": ["revolve plus", "soundlink revolve", "revolve+", "revolve speaker"],
     "common_issues": ["360 sound", "handle strap", "charging port", "Bluetooth"],
     "support_url": "/support/soundlink-revolve-plus"},
    # Home / Smart Speakers
    {"id": "home-speaker-300", "name": "Home Speaker 300", "category": "home_speakers",
     "keywords": ["home speaker 300", "bose 300", "home 300"],
     "common_issues": ["Wi-Fi setup", "Alexa integration", "multiroom audio", "app connection"],
     "support_url": "/support/home-speaker-300"},
    {"id": "home-speaker-500", "name": "Home Speaker 500", "category": "home_speakers",
     "keywords": ["home speaker 500", "bose 500", "home 500"],
     "common_issues": ["Wi-Fi connectivity", "display", "Alexa/Google Assistant", "multiroom"],
     "support_url": "/support/home-speaker-500"},
    # Soundbars
    {"id": "smart-soundbar-300", "name": "Smart Soundbar 300", "category": "soundbars",
     "keywords": ["soundbar 300", "smart soundbar 300", "bose 300 bar"],
     "common_issues": ["HDMI ARC", "bass module pairing", "Wi-Fi setup", "dialogue clarity"],
     "support_url": "/support/smart-soundbar-300"},
    {"id": "smart-soundbar-600", "name": "Smart Soundbar 600", "category": "soundbars",
     "keywords": ["soundbar 600", "smart soundbar 600", "bose 600 bar"],
     "common_issues": ["Dolby Atmos", "HDMI eARC", "surround speakers pairing", "app"],
     "support_url": "/support/smart-soundbar-600"},
    {"id": "smart-soundbar-900", "name": "Smart Soundbar 900", "category": "soundbars",
     "keywords": ["soundbar 900", "smart soundbar 900", "bose 900", "soundbar 900"],
     "common_issues": ["Dolby Atmos height", "HDMI eARC", "bass module", "dialogue mode"],
     "support_url": "/support/smart-soundbar-900"},
    {"id": "soundbar-700", "name": "Soundbar 700", "category": "soundbars",
     "keywords": ["soundbar 700", "bose bar 700", "bose 700 soundbar"],
     "common_issues": ["ADAPTiQ calibration", "HDMI ARC", "Amazon Alexa", "app control"],
     "support_url": "/support/soundbar-700"},
    {"id": "soundbar-500", "name": "Soundbar 500", "category": "soundbars",
     "keywords": ["soundbar 500", "bose bar 500"],
     "common_issues": ["HDMI ARC", "Wi-Fi", "voice assistants", "bass module"],
     "support_url": "/support/soundbar-500"},
    # Frames
    {"id": "frames-alto", "name": "Bose Frames Alto", "category": "frames",
     "keywords": ["frames alto", "bose frames", "alto glasses", "audio glasses alto"],
     "common_issues": ["charging", "battery life", "sound leakage", "lens replacement"],
     "support_url": "/support/frames-alto"},
    {"id": "frames-tenor", "name": "Bose Frames Tenor", "category": "frames",
     "keywords": ["frames tenor", "tenor glasses", "audio glasses tenor"],
     "common_issues": ["charging", "Bluetooth", "sound leakage"],
     "support_url": "/support/frames-tenor"},
    {"id": "frames-soprano", "name": "Bose Frames Soprano", "category": "frames",
     "keywords": ["frames soprano", "soprano glasses"],
     "common_issues": ["charging", "Bluetooth", "fit"],
     "support_url": "/support/frames-soprano"},
    # Sleepbuds
    {"id": "sleepbuds-ii", "name": "Sleepbuds II", "category": "sleepbuds",
     "keywords": ["sleepbuds", "sleepbuds ii", "sleepbuds 2", "sleep buds", "bose sleep"],
     "common_issues": ["noise masking sounds", "charging case", "app setup", "fit during sleep"],
     "support_url": "/support/sleepbuds-ii"},
]

# Build keyword index for fast lookup
_KEYWORD_INDEX: dict[str, str] = {}
for _p in BOSE_PRODUCTS:
    for _kw in _p["keywords"]:
        _KEYWORD_INDEX[_kw.lower()] = _p["id"]


def _match_product(identified_text: str) -> dict | None:
    """Map free-text product description to closest BOSE_PRODUCTS entry."""
    if not identified_text:
        return None

    text_lower = identified_text.lower()

    # 1. Exact keyword match
    for kw, product_id in _KEYWORD_INDEX.items():
        if kw in text_lower:
            return next(p for p in BOSE_PRODUCTS if p["id"] == product_id)

    # 2. Fuzzy match against product names and keywords
    best_score = 0.0
    best_product = None
    for product in BOSE_PRODUCTS:
        candidates = [product["name"]] + product["keywords"]
        for candidate in candidates:
            score = SequenceMatcher(None, text_lower, candidate.lower()).ratio()
            if score > best_score:
                best_score = score
                best_product = product

    return best_product if best_score >= 0.5 else None


def get_session_dir(session_id: str) -> Path:
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    return UPLOAD_DIR / session_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/products")
async def list_products():
    """Return the full Bose product catalog."""
    return {"products": BOSE_PRODUCTS, "count": len(BOSE_PRODUCTS)}


@app.get("/upload/{session_id}", response_class=HTMLResponse)
async def upload_page(session_id: str):
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
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            logger.warning("Skipping non-image file: %s (%s)", file.filename, file.content_type)
            continue
        ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
        safe_name = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = session_dir / safe_name
        content = await file.read()
        file_path.write_bytes(content)
        saved.append(safe_name)
        logger.info("Saved photo %s for session %s", safe_name, session_id)

    if not saved:
        raise HTTPException(status_code=400, detail="No valid image files uploaded")

    return {"success": True, "count": len(saved), "files": saved}


@app.get("/status/{session_id}")
async def check_status(session_id: str):
    session_dir = get_session_dir(session_id)
    if not session_dir.exists():
        return {"uploaded": False, "count": 0, "photos": []}
    photos = [f.name for f in session_dir.iterdir() if f.is_file()]
    return {"uploaded": len(photos) > 0, "count": len(photos), "photos": photos}


@app.post("/analyse/{session_id}")
async def analyse_photos(session_id: str):
    """Two-stage Gemini analysis: identify product → map to catalog → troubleshoot."""
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
        except Exception as e:
            logger.warning("Could not open image %s: %s", path, e)

    if not images:
        raise HTTPException(status_code=400, detail="Could not process uploaded images")

    logger.info("Analysing %d photo(s) for session %s", len(images), session_id)

    # ------------------------------------------------------------------
    # Stage 1: Product identification
    # ------------------------------------------------------------------
    stage1_prompt = (
        "You are a Bose product expert. Look at these photos and identify the Bose product.\n\n"
        "Respond ONLY with valid JSON in this exact format:\n"
        '{"identified_product": "<what you see, e.g. QuietComfort 45 headphones>", '
        '"confidence": "<high|medium|low>", '
        '"visual_cues": ["<cue 1>", "<cue 2>"]}\n\n'
        "If you cannot identify a Bose product, set identified_product to null and confidence to low."
    )

    stage1_result = {}
    matched_product = None
    try:
        response1 = model.generate_content([stage1_prompt] + images)
        raw = response1.text.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        stage1_result = json.loads(raw.strip())
        logger.info("Stage 1 result: %s", stage1_result)
        matched_product = _match_product(stage1_result.get("identified_product") or "")
        if matched_product:
            logger.info("Matched product: %s (id=%s)", matched_product["name"], matched_product["id"])
    except Exception as e:
        logger.warning("Stage 1 failed, falling back to unstructured: %s", e)

    # ------------------------------------------------------------------
    # Stage 2: Troubleshooting with product context
    # ------------------------------------------------------------------
    product_context = ""
    if matched_product:
        product_context = (
            f"\n\nThe product has been identified as: {matched_product['name']} "
            f"(category: {matched_product['category']}).\n"
            f"Common known issues for this product: {', '.join(matched_product['common_issues'])}.\n"
            "Focus your analysis on these known issues where visible."
        )

    stage2_prompt = (
        "You are a Bose product support expert analysing photos of a customer's device for a phone support call.\n"
        + product_context
        + "\n\nAnalyse the photos and respond ONLY with valid JSON in this exact format:\n"
        '{\n'
        '  "product_id": "<matched product id or null>",\n'
        '  "product_name": "<full product name or null>",\n'
        '  "mapping_confidence": "<exact|fuzzy|none>",\n'
        '  "visible_issues": ["<issue 1>", "<issue 2>"],\n'
        '  "troubleshooting_steps": ["<step 1>", "<step 2>", "<step 3>"],\n'
        '  "utterance": "<conversational response suitable for reading aloud on a phone call. '
        'Be specific about button locations, port names, LED colors. Max 3-4 sentences.>"\n'
        '}\n\n'
        "If no visible issues are found, provide general maintenance/setup tips for the product."
    )

    try:
        response2 = model.generate_content([stage2_prompt] + images)
        raw2 = response2.text.strip()
        if raw2.startswith("```"):
            raw2 = raw2.split("```")[1]
            if raw2.startswith("json"):
                raw2 = raw2[4:]
        result = json.loads(raw2.strip())

        # Override product fields from our catalog match if available
        if matched_product:
            result["product_id"] = matched_product["id"]
            result["product_name"] = matched_product["name"]
            if not result.get("mapping_confidence"):
                result["mapping_confidence"] = "fuzzy"

        result["photos_analysed"] = len(images)
        result["success"] = True
        # Backwards compat
        result["analysis"] = result.get("utterance", "")

        logger.info("Analysis complete for session %s: product=%s", session_id, result.get("product_id"))
        return result

    except Exception as e:
        logger.error("Stage 2 failed: %s", e)
        # Last resort: unstructured fallback
        try:
            fallback_prompt = (
                "You are a Bose product support expert. Analyse these photos and provide "
                "troubleshooting advice in 2-3 sentences suitable for reading aloud on a phone call."
                + product_context
            )
            fallback_response = model.generate_content([fallback_prompt] + images)
            utterance = fallback_response.text.strip()
        except Exception as e2:
            logger.error("Fallback also failed: %s", e2)
            utterance = (
                "I wasn't able to fully analyse the photos right now. "
                "Could you describe the specific issue you're experiencing with your Bose product?"
            )

        return {
            "success": True,
            "product_id": matched_product["id"] if matched_product else None,
            "product_name": matched_product["name"] if matched_product else None,
            "mapping_confidence": "fuzzy" if matched_product else "none",
            "visible_issues": [],
            "troubleshooting_steps": [],
            "utterance": utterance,
            "analysis": utterance,
            "photos_analysed": len(images),
        }


@app.delete("/session/{session_id}")
async def cleanup_session(session_id: str):
    session_dir = get_session_dir(session_id)
    if session_dir.exists():
        shutil.rmtree(session_dir)
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
