# FSB_TPE_Comparator — Comprehensive Project Documentation

> **Version:** 1.0.0  
> **Author:** Kunal Jejure  
> **Last Updated:** February 12, 2026  
> **Repository:** [https://github.com/continuous-intelligence/FSB_TPE_Comparator-.git](https://github.com/continuous-intelligence/FSB_TPE_Comparator-.git)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Backend — Detailed Module Breakdown](#5-backend--detailed-module-breakdown)
   - 5.1 [Entry Point — `main.py`](#51-entry-point--mainpy)
   - 5.2 [Application Factory — `backend/app.py`](#52-application-factory--backendapppy)
   - 5.3 [Configuration — `backend/config.py`](#53-configuration--backendconfigpy)
   - 5.4 [Database Layer — `backend/database.py`](#54-database-layer--backenddatabasepy)
   - 5.5 [API Layer — Compare Endpoint](#55-api-layer--compare-endpoint)
   - 5.6 [API Layer — Chat Endpoint](#56-api-layer--chat-endpoint)
6. [Services Layer — Core Logic](#6-services-layer--core-logic)
   - 6.1 [PDF Parser — `pdf_parser.py`](#61-pdf-parser--pdf_parserpy)
   - 6.2 [Diff Engine — `diff_engine.py`](#62-diff-engine--diff_enginepy)
   - 6.3 [Visual Diff Engine — `visual_diff.py`](#63-visual-diff-engine--visual_diffpy)
   - 6.4 [AI Comparison — `ai_compare.py`](#64-ai-comparison--ai_comparepy)
   - 6.5 [PDF Report Generator — `pdf_report.py`](#65-pdf-report-generator--pdf_reportpy)
   - 6.6 [ReportLab Report Generator — `report_gen.py`](#66-reportlab-report-generator--report_genpy)
7. [LLM Integration — Deep Dive](#7-llm-integration--deep-dive)
   - 7.1 [Model & Provider](#71-model--provider)
   - 7.2 [AI Semantic Comparison — Prompt Engineering](#72-ai-semantic-comparison--prompt-engineering)
   - 7.3 [AI Chat Assistant — Prompt Engineering](#73-ai-chat-assistant--prompt-engineering)
   - 7.4 [JSON Parsing & Safety](#74-json-parsing--safety)
8. [Frontend — UI Deep Dive](#8-frontend--ui-deep-dive)
   - 8.1 [Single-Page Application Architecture](#81-single-page-application-architecture)
   - 8.2 [Views & Navigation](#82-views--navigation)
   - 8.3 [File Upload & Drag-and-Drop](#83-file-upload--drag-and-drop)
   - 8.4 [Comparison Workflow](#84-comparison-workflow)
   - 8.5 [Results Rendering](#85-results-rendering)
   - 8.6 [AI Chat Interface](#86-ai-chat-interface)
   - 8.7 [History View](#87-history-view)
   - 8.8 [Dashboard Charts](#88-dashboard-charts)
9. [Comparison Pipeline — End-to-End Flow](#9-comparison-pipeline--end-to-end-flow)
10. [Algorithm Details](#10-algorithm-details)
    - 10.1 [Line-Level Text Diff Algorithm](#101-line-level-text-diff-algorithm)
    - 10.2 [SSIM-Based Visual Diff Algorithm](#102-ssim-based-visual-diff-algorithm)
    - 10.3 [Morphological Operations for Region Grouping](#103-morphological-operations-for-region-grouping)
    - 10.4 [Bounding Box Overlay Rendering](#104-bounding-box-overlay-rendering)
11. [Database Schema](#11-database-schema)
12. [API Reference](#12-api-reference)
13. [Configuration & Environment Variables](#13-configuration--environment-variables)
14. [Testing](#14-testing)
15. [Deployment & Running](#15-deployment--running)
16. [Design Decisions & Rationale](#16-design-decisions--rationale)

---

## 1. Project Overview

**FSB_TPE_Comparator** (also branded as **AuditLens** / **PDF Comparator**) is an enterprise-grade, AI-powered PDF comparison system. It allows users to upload two PDF documents — an "original" and a "revised" version — and produces a comprehensive multi-dimensional comparison:

| Comparison Dimension | Technology Used | Output |
|---|---|---|
| **Text Diff** | Python `difflib.SequenceMatcher` | GitHub-style side-by-side line diff |
| **Visual Diff** | OpenCV + scikit-image SSIM | Overlay image with highlighted change regions |
| **AI Semantic Analysis** | Groq LLM (Llama 3.3 70B) | Structured JSON with change classification & significance |
| **Interactive AI Chat** | Groq LLM (Llama 3.3 70B) | Conversational Q&A about results |
| **PDF Report** | Pillow PDF export | Downloadable PDF of diff overlays |

### Key Capabilities

- **Page-level granularity**: Every page is compared independently for text, visuals, and semantics.
- **Mismatched page counts**: Gracefully handles PDFs with different page counts (pages only in original → REMOVED, pages only in revised → ADDED).
- **AI-powered semantic understanding**: Goes beyond pixel/text diffs to understand the *meaning* of changes (e.g., "Button colour changed from blue to green").
- **Interactive AI chat**: Users can ask follow-up questions about comparison results in a chat interface.
- **Comparison history**: All comparisons are persisted in a SQLite database for later review.
- **Downloadable reports**: Visual diff overlays are compiled into a downloadable PDF report.

---

## 2. Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                          CLIENT (Browser)                             │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Dashboard   │  │ Compare  │  │ Results  │  │    History View   │  │
│  │    View      │  │   View   │  │   View   │  │                   │  │
│  └──────┬───────┘  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│         │               │             │                  │            │
│         └───────────────┼─────────────┼──────────────────┘            │
│                         │ HTTP (fetch)│                                │
└─────────────────────────┼─────────────┼───────────────────────────────┘
                          │             │
┌─────────────────────────┼─────────────┼───────────────────────────────┐
│                    FastAPI Backend (Uvicorn)                           │
│  ┌──────────────────────┴─────────────┴──────────────────────────┐    │
│  │                     API Router Layer                           │    │
│  │  POST /api/compare    GET /api/history    POST /api/chat       │    │
│  └──────┬──────────────────────┬──────────────────┬──────────────┘    │
│         │                      │                  │                   │
│  ┌──────▼──────────────────────▼──────────────────▼──────────────┐    │
│  │                    Services Layer                              │    │
│  │  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌──────────────┐   │    │
│  │  │PDF Parser│ │Diff Engine│ │Visual Diff │ │ AI Compare   │   │    │
│  │  │(PyMuPDF) │ │(difflib)  │ │(OpenCV+    │ │ (Groq LLM)   │   │    │
│  │  │          │ │           │ │ SSIM)      │ │              │   │    │
│  │  └──────────┘ └───────────┘ └────────────┘ └──────────────┘   │    │
│  │  ┌──────────────┐ ┌─────────────────┐                         │    │
│  │  │PDF Report Gen│ │ReportLab Report │                         │    │
│  │  │(Pillow)      │ │(ReportLab)      │                         │    │
│  │  └──────────────┘ └─────────────────┘                         │    │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌─────────────────┐    ┌────────────────────────────────────────┐    │
│  │  SQLite (history│    │  Static Files (CSS, JS, images,       │    │
│  │   .db)          │    │  generated reports)                    │    │
│  └─────────────────┘    └────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
                          │
                          │ HTTPS (OpenAI-compatible SDK)
                          ▼
              ┌───────────────────────┐
              │  Groq Cloud API       │
              │  Model: llama-3.3-    │
              │  70b-versatile        │
              └───────────────────────┘
```

---

## 3. Technology Stack

### Backend
| Component | Technology | Version | Purpose |
|---|---|---|---|
| Web Framework | FastAPI | ≥0.110.0 | Async REST API & template serving |
| ASGI Server | Uvicorn | ≥0.29.0 | Production-ready ASGI server with hot-reload |
| Templating | Jinja2 | ≥3.1.3 | Server-side HTML template rendering |
| PDF Processing | PyMuPDF (fitz) | latest | Text extraction & page-to-image rendering |
| Image Processing | OpenCV | ≥4.9.0 | Image manipulation, morphological ops, contour detection |
| Image Processing | Pillow (PIL) | ≥10.2.0 | Image format conversion, PDF report generation |
| Similarity Metric | scikit-image | ≥0.22.0 | Structural Similarity Index (SSIM) computation |
| Numerical Computing | NumPy | ≥1.26.0 | Array operations for image processing |
| LLM SDK | OpenAI Python SDK | ≥1.3.0 | OpenAI-compatible client for Groq API |
| PDF Reports | ReportLab | ≥4.1.0 | Structured PDF report generation with tables |
| Database | SQLite3 | built-in | Comparison history persistence |
| Environment | python-dotenv | ≥1.0.1 | `.env` file loading |

### Frontend
| Component | Technology | Purpose |
|---|---|---|
| Icons | Lucide Icons (CDN) | Crisp, consistent SVG icon set |
| Charts | Chart.js v4 | Performance visualization charts |
| Fonts | Inter + JetBrains Mono (Google Fonts) | Typography — UI text + monospace diffs |
| Styling | Vanilla CSS | Custom design system with CSS variables |

### External Services
| Service | Provider | Model | Purpose |
|---|---|---|---|
| LLM API | **Groq** | **Llama 3.3 70B Versatile** | Semantic text comparison + interactive chat |

---

## 4. Project Structure

```
FSB_TPE_Comparator-/
├── main.py                          # Application entry point
├── pyproject.toml                   # Poetry project config & dependencies
├── requirements.txt                 # pip-compatible dependency list
├── .env                             # Environment variables (API keys)
├── .gitignore                       # Git ignore rules
├── history.db                       # SQLite database (auto-created)
├── README.md                        # Project README
│
├── backend/                         # Python backend package
│   ├── __init__.py                  # Package marker
│   ├── app.py                       # FastAPI app factory, routing, static files
│   ├── config.py                    # Centralized configuration loader
│   ├── database.py                  # SQLite database operations (history)
│   │
│   ├── api/                         # API route handlers
│   │   ├── __init__.py
│   │   ├── compare.py               # POST /api/compare — main comparison endpoint
│   │   └── chat.py                  # POST /api/chat — AI chat endpoint
│   │
│   └── services/                    # Core business logic
│       ├── __init__.py
│       ├── pdf_parser.py            # PDF text extraction & page rendering
│       ├── diff_engine.py           # Character-level text diff engine
│       ├── visual_diff.py           # SSIM-based visual diff with overlays
│       ├── ai_compare.py            # Groq LLM semantic comparison
│       ├── pdf_report.py            # Pillow-based PDF report generation
│       └── report_gen.py            # ReportLab-based detailed PDF reports
│
├── frontend/                        # Frontend assets
│   ├── templates/
│   │   └── index.html               # Single-page application (2710 lines)
│   └── static/
│       ├── images/                  # Logo images (Name_Image.png, Title_Image.png, xLM.svg)
│       └── reports/                 # Generated diff report PDFs
│
├── tests/                           # Test suite
│   ├── __init__.py
│   └── test_compare.py              # Unit tests for PDF parsing, diffing, visual diff
│
├── uploads/                         # Temporary upload directory (auto-cleaned)
└── venv/                            # Python virtual environment
```

---

## 5. Backend — Detailed Module Breakdown

### 5.1 Entry Point — `main.py`

```python
uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
```

- Starts the Uvicorn ASGI server on **port 8000**.
- `reload=True` enables hot-reloading during development — file changes auto-restart the server.
- The `"backend.app:app"` string tells Uvicorn to import the `app` object from `backend/app.py`.

### 5.2 Application Factory — `backend/app.py`

**Responsibilities:**
1. **Database initialization**: Calls `init_db()` at module load time to ensure the SQLite tables exist.
2. **Path resolution**: Dynamically resolves project root, frontend, and static directories using `pathlib.Path`.
3. **Static file mounting**: Mounts `frontend/static/` at the `/static` URL path using FastAPI's `StaticFiles`.
4. **Template configuration**: Configures Jinja2 templates from `frontend/templates/`.
5. **Router registration**: Includes both the `compare_router` and `chat_router` under the `/api` prefix.
6. **Health check**: Exposes `GET /health` returning `{"status": "UP"}`.
7. **Home route**: Serves `index.html` at `GET /`.

### 5.3 Configuration — `backend/config.py`

**Centralised configuration** loaded once at startup:

| Variable | Source | Purpose |
|---|---|---|
| `GROQ_API_KEY` | `.env` | Authentication for Groq LLM API |
| `AZURE_CLIENT_ID` | `.env` | Azure AD app registration (future auth) |
| `AZURE_CLIENT_SECRET` | `.env` | Azure AD secret (future auth) |
| `AZURE_TENANT_ID` | `.env` | Azure AD tenant (future auth) |
| `SECRET_KEY` | `.env` | Session encryption key |
| `UPLOAD_DIR` | Computed | `<project_root>/uploads/` — temporary PDF storage |
| `REPORTS_DIR` | Computed | `<project_root>/frontend/static/reports/` — generated reports |

The module uses `python-dotenv` to load variables from the project-root `.env` file. Missing `GROQ_API_KEY` triggers a warning but doesn't crash the application — AI features gracefully degrade.

### 5.4 Database Layer — `backend/database.py`

**SQLite database** (`history.db`) with thread-safe access via `threading.Lock`.

**Three functions:**

| Function | Purpose |
|---|---|
| `init_db()` | Creates the `comparisons` table if it doesn't exist |
| `add_comparison(original, revised, pages, status, report_url)` | Inserts a new comparison record |
| `get_recent_comparisons(limit=10)` | Fetches the most recent N comparison records (DESC order) |

**Schema** — see [Section 11](#11-database-schema).

### 5.5 API Layer — Compare Endpoint (`backend/api/compare.py`)

**`POST /api/compare`** — The core endpoint. Accepts two PDF files via multipart form upload.

**Step-by-step pipeline (358 lines):**

1. **Validation**: Checks both files have `.pdf` extension.
2. **Job isolation**: Creates a unique UUID-named directory under `uploads/` to prevent collisions.
3. **File persistence**: Copies uploaded streams to `original.pdf` and `revised.pdf` on disk.
4. **Text extraction**: Calls `extract_text()` for both PDFs → list of strings (one per page).
5. **Page iteration**: Iterates over `max(orig_pages, rev_pages)` pages:
   - Determines **disposition**: `compared` (both exist), `removed` (only original), `added` (only revised).
   - Computes **line-level text diff** via `_build_line_diff()`.
   - Renders both pages to **PIL images** via `page_to_image()`.
   - Generates **visual diff overlay** via `generate_diff_overlay()` (only when both pages exist).
   - Determines **page status**: `PASS` (no changes), `FAIL` (changes found), `ADDED`, or `REMOVED`.
6. **AI semantic analysis**: Calls `_run_ai_comparison()` which invokes the Groq LLM.
7. **Result enrichment**: Merges AI-detected text and image changes back into per-page results.
8. **PDF report generation**: Saves overlay images as a multi-page PDF in `static/reports/`.
9. **History persistence**: Stores the comparison metadata in SQLite.
10. **Cleanup**: Deletes the temporary job directory in a `finally` block.

**Helper function — `_build_line_diff(text1, text2)`:**

Uses `difflib.SequenceMatcher` to produce a GitHub-style side-by-side diff. Each diff entry contains:
- `type`: `equal` | `insert` | `delete` | `replace`
- `left_line_no` / `right_line_no`: Line numbers (null for insertions/deletions)
- `left_content` / `right_content`: The actual text content

**Helper function — `_pil_to_base64(img)`:**

Converts a PIL Image to a base64-encoded JPEG data URI. Uses JPEG quality 82, which provides ~4× payload reduction versus PNG while maintaining excellent visual quality.

**Helper function — `_run_ai_comparison()`:**

Wraps the AI comparison call in a try/except. On failure, returns a fallback result with `overall_change: "UNKNOWN"` and empty change lists — ensuring the comparison never crashes due to LLM issues.

**`GET /api/history`** — Returns the last 10 comparisons from the database.

### 5.6 API Layer — Chat Endpoint (`backend/api/chat.py`)

**`POST /api/chat`** — Interactive AI conversation about comparison results.

**Request schema (`ChatRequest`):**
```json
{
  "message": "What are the most significant changes?",
  "context": { /* comparison result data */ },
  "history": [ /* previous chat messages */ ]
}
```

**Logic flow:**
1. Loads the Groq API key from environment.
2. Constructs an OpenAI client pointing to Groq's endpoint.
3. Builds a **concise context summary** from the comparison data (total pages, change level, confidence, per-page breakdown with up to 5 text changes per page).
4. Constructs a **system prompt** instructing the AI to be a PDF comparison assistant.
5. Appends the last **10 conversation messages** for multi-turn context.
6. Sends to `llama-3.3-70b-versatile` with `temperature=0.3` and `max_tokens=1024`.
7. Returns the AI's reply as a `ChatResponse`.

---

## 6. Services Layer — Core Logic

### 6.1 PDF Parser — `pdf_parser.py`

Uses **PyMuPDF (fitz)** for both text extraction and page rendering.

**`extract_text(pdf_path) → List[str]`**
- Opens the PDF with `fitz.open()`.
- Iterates each page with `doc.load_page(page_index)`.
- Extracts text with `page.get_text()` — returns unicode text preserving reading order.
- Returns a list of strings, one per page.

**`page_to_image(pdf_path, page_num, dpi=200) → PIL.Image`**
- Renders a single page at **200 DPI** (configurable).
- Uses `page.get_pixmap(dpi=dpi, alpha=False)` — alpha=False gives a clean white background.
- Converts the pixmap bytes to a PIL Image in RGB mode.
- 200 DPI provides excellent quality for text and embedded images while keeping sizes reasonable for 30+ page PDFs.

**`get_page_count(pdf_path) → int`**
- Quick page count without full page loading.

### 6.2 Diff Engine — `diff_engine.py`

A **character-level** text diff engine (used as an alternative/supplement to the line-level diff in `compare.py`).

**`text_diff(texts1, texts2) → Dict[str, List[Dict]]`**
- Compares page texts using `difflib.SequenceMatcher` at the **character level**.
- Returns per-page changes keyed as `"page_0"`, `"page_1"`, etc.
- Each change entry includes `type` (replace/insert/delete), `original`, and `revised` text (truncated to 200 chars).

**`summarize_changes(per_page_changes) → List[Dict]`**
- Flattens the per-page diff into a simple list of change summaries with page numbers.

### 6.3 Visual Diff Engine — `visual_diff.py`

**The crown jewel of the comparison pipeline.** Inspired by Adobe Acrobat-style comparison, it produces readable overlay images with coloured borders around changed regions.

**`generate_diff_overlay(img1, img2) → (PIL.Image, float, int)`**

**Algorithm (5-step process):**

1. **Convert to OpenCV**: PIL images → NumPy arrays → BGR colour space.
2. **Size normalization**: If dimensions differ, resizes `img2` to match `img1` using `INTER_LANCZOS4` interpolation.
3. **SSIM computation**: Converts both to grayscale, computes Structural Similarity Index with a full diff map.
4. **Region detection**: Thresholds the diff map → binary mask → morphological closing + dilation → contour extraction.
5. **Overlay rendering**: Draws semi-transparent highlighted bounding boxes on the revised image.

**Rendering technique:**
- Creates a highlight layer with filled rectangles (light red/pink fill).
- Alpha-blends the highlight onto the original at **18% opacity** — keeps text readable.
- Draws **crisp 2px red borders** on top after blending.
- Each region gets **6px padding** around the detected contour.

**Colour scheme:**
| Element | BGR Value | Visual |
|---|---|---|
| Red border | `(0, 0, 220)` | Crisp red outline |
| Red fill | `(200, 210, 255)` | Light pink tint |
| Green border | `(0, 180, 0)` | Green for additions |
| Green fill | `(210, 255, 210)` | Light green tint |

**`compute_similarity(img1, img2) → float`**
- Quick similarity score (0.0–1.0) using SSIM without overlay generation.

### 6.4 AI Comparison — `ai_compare.py`

**Groq LLM-powered semantic analysis** — goes beyond text/pixel diffs to understand *what changed and why it matters*.

**`ai_compare(text1, text2, image_summary) → Dict`**

1. Truncates input texts to **12,000 characters** to stay within context limits.
2. Formats texts with `===PAGE===` separators for clear page delineation.
3. Sends to Groq with `temperature=0` (deterministic output).
4. Parses the JSON response with safety handling for markdown code fences.
5. Validates and normalises the result structure with default values.

**Output schema:**
```json
{
  "summary": {
    "overall_change": "NONE | MINOR | MAJOR",
    "confidence": 0.95,
    "change_description": "One sentence describing the overall change"
  },
  "text_changes": [{
    "type": "ADDED | REMOVED | MODIFIED",
    "page": 1,
    "section": "Heading or area",
    "original": "exact original text",
    "revised": "exact revised text",
    "significance": "LOW | MEDIUM | HIGH"
  }],
  "image_changes": [{
    "page": 1,
    "description": "Detailed visual change description",
    "impact": "LOW | MEDIUM | HIGH",
    "element_type": "chart | table | diagram | screenshot | icon | photo"
  }]
}
```

See [Section 7](#7-llm-integration--deep-dive) for full prompt engineering details.

### 6.5 PDF Report Generator — `pdf_report.py`

**Pillow-based** simple report generator.

**`generate_diff_pdf(images1, images2) → (bytes, page_results)`**
- Iterates over paired page images.
- Generates diff overlays for each pair.
- Assembles all overlay images into a single multi-page PDF using Pillow's `save()` with `save_all=True`.
- Returns PDF bytes and per-page similarity results.

### 6.6 ReportLab Report Generator — `report_gen.py`

**ReportLab-based** comprehensive report with:
- **Cover page**: Logo, title, overall change summary, confidence score.
- **Table of contents**: Linked list of all pages with PASS/FAIL status.
- **Per-page detail sections**: Anchored headings, confidence/similarity metrics, change tables with colour-coded original/revised text.
- **Footer**: "Generated by PDF Comparator" on every page.

Uses custom colour constants: `HEADER_COLOR (#1F4FD8)`, `PASS_COLOR (#2ECC71)`, `FAIL_COLOR (#E74C3C)`.

---

## 7. LLM Integration — Deep Dive

### 7.1 Model & Provider

| Parameter | Value |
|---|---|
| **Provider** | Groq |
| **API Endpoint** | `https://api.groq.com/openai/v1` |
| **Model** | `llama-3.3-70b-versatile` |
| **SDK** | OpenAI Python SDK (OpenAI-compatible) |
| **Authentication** | Bearer token via `GROQ_API_KEY` |

**Why Groq?** Groq provides ultra-fast inference (hundreds of tokens/sec) via their custom LPU hardware, making real-time PDF analysis feasible. The OpenAI-compatible API means we use the standard `openai` Python SDK — just pointing the `base_url` to Groq.

**Why Llama 3.3 70B?** This Meta model offers state-of-the-art reasoning at the 70B parameter scale, with strong instruction-following and JSON output capabilities — critical for structured comparison results.

### 7.2 AI Semantic Comparison — Prompt Engineering

**System prompt** (deterministic engine role):
```
You are a deterministic PDF comparison engine specialised in detecting
differences between two document revisions.

Rules:
- Ignore logos, watermarks, headers, footers, branding images, page numbers
- Compare ONLY:
  1. Text content (paragraphs, headings, bullets, tables)
  2. Meaningful images (charts, tables, diagrams, UI screenshots)
  3. Layout changes that affect readability
- Each change MUST include the page number it occurs on
- For text changes: provide the EXACT original and revised text snippets
- For image changes: describe what changed visually in detail
- Assign image change impact based on visual significance:
  LOW  = minor cosmetic
  MEDIUM = noticeable UI change
  HIGH = major layout or data change
- Output MUST be valid JSON ONLY — no markdown, no explanations
- Do NOT hallucinate or invent changes that don't exist
```

**User prompt** provides:
1. Original text (per page, separated by `===PAGE===` markers)
2. Revised text (same format)
3. Image similarity scores from the visual diff engine
4. Strict JSON schema to follow

**LLM parameters:**
- `temperature=0` → fully deterministic, no creativity
- Max context: 12,000 chars per document to stay within token limits

### 7.3 AI Chat Assistant — Prompt Engineering

**System prompt** (conversational assistant role):
```
You are an AI assistant that helps users understand PDF comparison results.
You have access to the full comparison data between two PDF documents.

[Injected context: total pages, change level, confidence, per-page breakdown]

Rules:
- Answer questions clearly and specifically
- Reference specific page numbers and exact changes when relevant
- If asked about something not in the data, say so honestly
- Be concise but thorough. Use bullet points for clarity
- If the user asks for a summary, provide a structured overview
- You can suggest what to look at or what changes are most important
```

**LLM parameters:**
- `temperature=0.3` → slightly creative for natural conversation
- `max_tokens=1024` → concise responses
- Conversation history: last **10 messages** retained for multi-turn context

### 7.4 JSON Parsing & Safety

The `_safe_json_parse()` function handles common LLM output issues:
1. Strips leading/trailing whitespace.
2. Removes markdown code fences (` ```json ... ``` `) that LLMs sometimes add despite instructions.
3. Attempts `json.loads()` parsing.
4. Logs malformed JSON for debugging and raises `RuntimeError`.

Post-parsing, the result is **validated and normalised** — missing keys get default values, ensuring downstream code never crashes on malformed LLM output.

---

## 8. Frontend — UI Deep Dive

### 8.1 Single-Page Application Architecture

The entire frontend is a **single HTML file** (`index.html`, 2710 lines) containing embedded CSS and JavaScript. No build tools, no bundler, no framework — pure vanilla HTML/CSS/JS.

**Design system** defined via CSS custom properties (`:root` variables):
- **Colours**: `--bg`, `--card`, `--accent`, `--success`, `--danger`, `--warning`
- **Typography**: Inter (UI) + JetBrains Mono (code/diffs)
- **Spacing**: `--radius: 16px`, `--radius-sm: 10px`
- **Shadows**: `--shadow` (subtle), `--shadow-lg` (elevated)
- **Diff colours**: Separate palette for additions (green), deletions (red), replacements (amber)

### 8.2 Views & Navigation

Four views, toggled by `switchView(viewName)`:

| View | ID | Purpose |
|---|---|---|
| **Dashboard** | `view-dashboard` | Statistics, performance chart, recent comparisons |
| **Compare** | `view-compare` | File upload, activity log |
| **Results** | `view-results` | Tabs for text diff, visual diff, AI chat |
| **History** | `view-history` | Past comparison records from database |

Navigation updates: active class on nav items, page title/subtitle in header.

### 8.3 File Upload & Drag-and-Drop

Two upload zones with full **drag-and-drop** support:
- `dragover` → adds visual "dragover" class (blue border + blue tint)
- `dragleave` → removes the class
- `drop` → filters for PDF files (`.pdf` extension or `application/pdf` MIME type)
- Click → triggers hidden `<input type="file">` via `onclick`
- File info card appears with filename, size, and remove button
- Compare button enables only when **both files are selected**

### 8.4 Comparison Workflow

`runCompare()` function:
1. Disables the compare button, shows spinner and progress bar.
2. Simulates progress (random increments up to 90%, real progress on completion).
3. Creates `FormData` with both files.
4. `POST /api/compare` with the form data.
5. On success: updates dashboard stats, renders results, switches to results view.
6. On failure: shows error in activity feed.
7. Cleanup: re-enables button, hides spinner.

### 8.5 Results Rendering

Three tabs in the results view:

**Tab 1 — Text Changes:**
- Collapsible page sections with headers showing page number, status badge, changes count, similarity percentage.
- GitHub-style side-by-side diff table using `<table>` with fixed-width columns.
- Colour-coded rows: green background for insertions, red for deletions, amber for replacements.
- Gutter columns show line numbers.
- Monospace font (JetBrains Mono) for code-like readability.

**Tab 2 — Visual Differences:**
- Collapsible page sections.
- For "compared" pages: full-width overlay image with change region count and similarity %.
- For "added" pages: green-bordered revised image with "New Page" label.
- For "removed" pages: red-bordered original image with "Removed Page" label.
- Identical pages (≥99.9% similarity): green checkmark message, no image shown.

**Tab 3 — AI Assistant:**
- Chat interface with message bubbles (user = blue, AI = purple).
- Pre-populated suggestion chips: "Summarize all changes", "Which pages have the most changes?", etc.
- Typing indicator animation (three bouncing dots).
- Markdown-like rendering for AI responses (bold, lists, code blocks).
- Auto-scrolls to bottom on new messages.

### 8.6 AI Chat Interface

`sendChatMessage()`:
1. Captures user input, adds to UI as user bubble.
2. Shows typing indicator.
3. Builds lightweight context (strips base64 images to save bandwidth).
4. `POST /api/chat` with message, context, and last 10 history messages.
5. Replaces typing indicator with AI response (rendered with markdown).
6. Manages `chatHistory` array for multi-turn conversation.

### 8.7 History View

`loadHistory()`:
- `GET /api/history` → fetches last 10 comparisons.
- Renders each as a task-item card with filenames, page count, timestamp, status dot, and optional report link.

### 8.8 Dashboard Charts

**Chart.js line chart** showing:
- **Dataset 1**: Similarity % per page (solid blue line, filled area)
- **Dataset 2**: AI Confidence % per page (dashed grey line)

Updated dynamically after each comparison via `updateChart(data)`.

---

## 9. Comparison Pipeline — End-to-End Flow

```
User uploads 2 PDFs
        │
        ▼
┌───────────────────┐
│ Validate PDF ext  │
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ Create job UUID   │──── uploads/<uuid>/original.pdf
│ Save to disk      │──── uploads/<uuid>/revised.pdf
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ PyMuPDF: extract  │──── texts_original: List[str]
│ text per page     │──── texts_revised: List[str]
└───────┬───────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│ FOR each page (0..max_pages):             │
│                                           │
│   ┌─ Determine disposition ─────────────┐ │
│   │ both exist → "compared"             │ │
│   │ only original → "removed"           │ │
│   │ only revised → "added"              │ │
│   └─────────────────────────────────────┘ │
│                                           │
│   ┌─ Line-level text diff ──────────────┐ │
│   │ difflib.SequenceMatcher on lines    │ │
│   │ → equal/insert/delete/replace       │ │
│   └─────────────────────────────────────┘ │
│                                           │
│   ┌─ Render pages to images ────────────┐ │
│   │ PyMuPDF → 200 DPI → PIL Image      │ │
│   └─────────────────────────────────────┘ │
│                                           │
│   ┌─ Visual diff (if both exist) ───────┐ │
│   │ SSIM → threshold → morphology →     │ │
│   │ contours → bounding box overlay     │ │
│   └─────────────────────────────────────┘ │
│                                           │
│   ┌─ Encode images as base64 JPEG ──────┐ │
│   │ Quality 82 → ~4× smaller than PNG │ │
│   └─────────────────────────────────────┘ │
│                                           │
│   ┌─ Determine status ─────────────────┐  │
│   │ No changes & similarity ≥ 0.98 → PASS│
│   │ Otherwise → FAIL / ADDED / REMOVED │  │
│   └─────────────────────────────────────┘ │
└───────────────┬───────────────────────────┘
                │
                ▼
┌───────────────────────────────┐
│ Groq LLM: Semantic analysis  │
│ temperature=0, strict JSON   │
│ → summary, text_changes,     │
│   image_changes              │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ Merge AI results into pages  │
│ Generate PDF report (Pillow) │
│ Save to history (SQLite)     │
│ Cleanup temp files           │
└───────────────┬───────────────┘
                │
                ▼
        JSON response to client
```

---

## 10. Algorithm Details

### 10.1 Line-Level Text Diff Algorithm

**Implementation:** `_build_line_diff()` in `compare.py`

Uses Python's `difflib.SequenceMatcher`, which implements the **Ratcliff/Obershelp algorithm** (a variant of the longest common subsequence). The algorithm:

1. Splits both texts into **lines** (preserving line structure).
2. Finds the longest contiguous matching subsequence.
3. Recursively matches the text before and after the match.
4. Returns **opcodes**: `equal`, `insert`, `delete`, `replace`.

For `replace` operations, the code handles **asymmetric replacements** — when the replaced block in the original has a different number of lines than in the revised. It iterates up to `max(original_lines, revised_lines)`, filling with null line numbers where one side is shorter.

### 10.2 SSIM-Based Visual Diff Algorithm

**Structural Similarity Index (SSIM)** measures perceived visual similarity between two images. Unlike pixel-by-pixel comparison, SSIM considers:
- **Luminance** (brightness)
- **Contrast** (dynamic range)
- **Structure** (spatial correlation)

This makes it robust to minor rendering differences (anti-aliasing, font hinting) that would trigger false positives in simple pixel diff.

**Implementation:** `_compute_diff_regions()` in `visual_diff.py`

```python
score, diff_map = ssim(gray1, gray2, full=True)
```

The `full=True` parameter returns the **per-pixel SSIM map** (not just the scalar score), enabling spatial localisation of changes.

### 10.3 Morphological Operations for Region Grouping

Raw SSIM diff maps produce many tiny scattered change pixels. Morphological operations group them into coherent regions:

1. **Inversion**: `(1.0 - diff_map) * 255` → changed pixels become bright (255).
2. **Thresholding**: `cv2.threshold(diff_uint8, 25, 255, THRESH_BINARY)` → removes minor noise.
3. **Morphological closing** (9×5 kernel, 2 iterations): Fills small gaps between nearby change pixels — "closes" holes.
4. **Dilation** (7×3 kernel, 3 iterations): Expands regions outward to group nearby clusters into single connected components.
5. **Contour detection**: `cv2.findContours(RETR_EXTERNAL)` → extracts outer boundaries of each change region.

The kernel sizes (9×5 for closing, 7×3 for dilation) are tuned for document comparison — wider than tall to group changes that span across a line of text.

### 10.4 Bounding Box Overlay Rendering

**Three-layer compositing technique:**

1. **Highlight layer**: A copy of the canvas with filled rectangles in the fill colour (light pink).
2. **Alpha blend**: `cv2.addWeighted(highlight, 0.18, canvas, 0.82, 0)` — 18% highlight, 82% original → text stays readable.
3. **Border layer**: Crisp 2px red borders drawn **after** blending (not affected by alpha).

This produces an Adobe Acrobat-style result where changed regions are clearly visible but the underlying document remains fully legible.

---

## 11. Database Schema

**Table: `comparisons`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique record ID |
| `timestamp` | TEXT | NOT NULL | ISO-format datetime string |
| `original_filename` | TEXT | NOT NULL | Name of the original PDF file |
| `revised_filename` | TEXT | NOT NULL | Name of the revised PDF file |
| `total_pages` | INTEGER | | Number of pages compared |
| `status` | TEXT | | `"NO CHANGES"` or `"CHANGES FOUND"` |
| `report_url` | TEXT | | URL path to the generated report PDF |

---

## 12. API Reference

### `POST /api/compare`

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `original` | File (PDF) | Yes | The original/baseline PDF document |
| `revised` | File (PDF) | Yes | The revised/updated PDF document |

**Response (200 OK):**
```json
{
  "job_id": "uuid-string",
  "report_url": "/static/reports/<uuid>_diff.pdf",
  "total_pages": 5,
  "original_pages": 5,
  "revised_pages": 5,
  "original_name": "document_v1.pdf",
  "revised_name": "document_v2.pdf",
  "overall": {
    "overall_change": "MINOR",
    "confidence": 0.92,
    "change_description": "Minor text changes on pages 2 and 4"
  },
  "pages": [
    {
      "page": 1,
      "disposition": "compared",
      "status": "PASS",
      "text_changes_count": 0,
      "image_similarity": 0.9987,
      "diff_region_count": 0,
      "original_image": "data:image/jpeg;base64,...",
      "revised_image": "data:image/jpeg;base64,...",
      "overlay_image": "data:image/jpeg;base64,...",
      "line_diff": [...],
      "ai_text_changes": [...],
      "ai_image_changes": [...],
      "confidence": 0.92
    }
  ]
}
```

### `POST /api/chat`

**Content-Type:** `application/json`

**Request body:**
```json
{
  "message": "What are the most significant changes?",
  "context": { /* comparison result data (without base64 images) */ },
  "history": [
    { "role": "user", "content": "previous question" },
    { "role": "assistant", "content": "previous answer" }
  ]
}
```

**Response:**
```json
{
  "reply": "The most significant changes are on page 3..."
}
```

### `GET /api/history`

**Response:** Array of comparison records (newest first, max 10).

### `GET /health`

**Response:** `{"status": "UP"}`

---

## 13. Configuration & Environment Variables

Create a `.env` file in the project root:

```env
# Required: Groq API key for LLM features
GROQ_API_KEY=gsk_your_api_key_here

# Optional: Azure AD (future SSO)
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id

# Optional: Session secret
SECRET_KEY=change-this-to-a-secure-random-string
```

---

## 14. Testing

**Test file:** `tests/test_compare.py`

**Test 1 — `test_extract_text_and_page_to_image()`:**
- Creates a sample one-page PDF using ReportLab.
- Verifies `extract_text()` returns non-empty text containing "Original Document".
- Verifies `page_to_image()` returns a valid PIL Image with positive dimensions.

**Test 2 — `test_text_and_visual_diff()`:**
- Creates two sample PDFs with different content.
- Runs `text_diff()` and verifies changes are detected.
- Runs `generate_diff_overlay()` and verifies the overlay image exists and similarity is between 0.0 and 1.0.

**Run tests:**
```bash
python -m pytest tests/ -v
```

---

## 15. Deployment & Running

### Local Development

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate (Windows)
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up .env file with GROQ_API_KEY

# 5. Run the application
python main.py
```

The application will be available at **http://localhost:8000**.

### Production Considerations

- Replace `reload=True` with `reload=False` and use multiple workers: `uvicorn.run(..., workers=4)`.
- Use a reverse proxy (Nginx/Caddy) for TLS termination.
- Migrate from SQLite to PostgreSQL for concurrent access.
- Configure `UPLOAD_DIR` on a volume with adequate disk space.
- Set a strong `SECRET_KEY` for session security.

---

## 16. Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| **JPEG at quality 82** for base64 images | ~4× smaller payload than PNG; quality is visually indistinguishable for document pages |
| **200 DPI rendering** | Sweet spot between quality and performance; readable text + clear embedded images |
| **SSIM over pixel diff** | Robust to anti-aliasing, font rendering differences; measures perceptual similarity |
| **Morphological closing/dilation** | Groups scattered change pixels into meaningful regions; prevents hundreds of tiny boxes |
| **18% alpha blend** for overlay fills | Subtle enough to keep text readable; strong enough to clearly mark change regions |
| **Temperature=0 for comparison** | Deterministic output; same input always produces same result |
| **Temperature=0.3 for chat** | Slightly creative for natural conversation; still focused and accurate |
| **12,000 char context limit** | Stays within Groq/Llama token limits while covering most document content |
| **Line-level diff (not character)** | GitHub-style readability; character diff is available in `diff_engine.py` for finer granularity |
| **Single HTML file** | Zero build complexity; instant deployment; no frontend framework learning curve |
| **SQLite for history** | Zero configuration; single-file database; sufficient for single-user/small-team use |
| **Groq (not OpenAI/Claude)** | Ultra-fast inference; good price/performance; OpenAI-compatible SDK makes switching trivial |
| **Graceful AI fallback** | If LLM fails, comparison still returns text + visual diffs; AI enrichment is additive |
| **UUID job directories** | Prevents file collisions in concurrent comparisons; auto-cleaned after processing |

---

*This documentation covers every aspect of the FSB_TPE_Comparator project. For questions or contributions, please refer to the repository or contact the development team.*
