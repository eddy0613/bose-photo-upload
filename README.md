# Bose Photo Upload Server

FastAPI server for the Bose troubleshooting voice agent. Accepts product photos from callers, stores them by session, and analyzes them via Google Gemini Vision API.

## Setup

```bash
cd photo-upload-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and set your Google API key:

```bash
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY
```

## Run

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Docker

```bash
docker build -t bose-upload-server .
docker run -p 8080:8080 -e GOOGLE_API_KEY=your-key bose-upload-server
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/upload/{session_id}` | Mobile-friendly upload page |
| POST | `/upload/{session_id}` | Accept photo uploads (multipart) |
| GET | `/status/{session_id}` | Check upload status |
| POST | `/analyse/{session_id}` | Analyze photos with Gemini Vision |
| DELETE | `/session/{session_id}` | Clean up session photos |
