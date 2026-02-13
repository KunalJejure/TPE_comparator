# 🎯 AuditLens — Interview-Ready Technical Guide

> **Project Name:** AuditLens (PDF Comparator)
> **Version:** 1.0.0
> **Description:** An enterprise-grade, AI-powered PDF comparison tool with visual diffs, text analysis, and intelligent report generation.

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack Summary](#2-tech-stack-summary)
3. [Architecture & Design Patterns](#3-architecture--design-patterns)
4. [Backend Deep Dive](#4-backend-deep-dive)
5. [Frontend Deep Dive](#5-frontend-deep-dive)
6. [AI/LLM Integration](#6-aillm-integration)
7. [Key Algorithms & Logic](#7-key-algorithms--logic)
8. [Database](#8-database)
9. [API Endpoints](#9-api-endpoints)
10. [Common Interview Q&A](#10-common-interview-qa)

---

## 1. Project Overview

AuditLens is a full-stack web application that compares two PDF documents and produces:
- **Visual Diffs** — pixel-level comparison with bounding-box overlays (Adobe Acrobat-style)
- **Text Diffs** — GitHub-style line-by-line text comparison
- **AI Analysis** — LLM-powered semantic analysis identifying meaningful changes
- **Downloadable Reports** — professional PDF reports summarizing all differences
- **AI Chat Assistant** — interactive conversational interface to ask questions about comparison results
- **Comparison History** — persistent history of past comparisons stored in SQLite

### Problem It Solves
In enterprises, document revisions (contracts, regulatory filings, compliance reports) need careful review. Manual comparison is error-prone and time-consuming. AuditLens automates this by combining pixel-level visual diffing with AI-driven semantic understanding.

---

## 2. Tech Stack Summary

### 🔤 Programming Languages
| Language | Usage |
|----------|-------|
| **Python 3.9+** | Backend logic, API, PDF processing, AI integration, image processing |
| **HTML5** | Frontend structure and templates |
| **CSS3** | Styling, animations, responsive design |
| **JavaScript (ES6+)** | Frontend interactivity, DOM manipulation, API calls |
| **SQL** | Database queries (SQLite) |

### 🖥️ Backend Framework
| Technology | Purpose |
|------------|---------|
| **FastAPI** | High-performance async web framework for REST APIs |
| **Uvicorn** | ASGI server to run the FastAPI application |
| **Jinja2** | Server-side HTML templating engine |
| **Pydantic** | Data validation and serialization (used with FastAPI) |

### 📄 PDF Processing
| Library | Purpose |
|---------|---------|
| **PyMuPDF (fitz)** | PDF parsing, text extraction, and page-to-image rendering at 200 DPI |
| **ReportLab** | PDF report generation with tables, styling, and page layout |

### 🖼️ Image Processing & Computer Vision
| Library | Purpose |
|---------|---------|
| **OpenCV (cv2)** | Image manipulation, morphological operations, contour detection, bounding boxes |
| **NumPy** | Array operations for image data processing |
| **scikit-image (skimage)** | Structural Similarity Index (SSIM) computation |
| **Pillow (PIL)** | Image format conversion, resizing, and I/O |

### 🤖 AI / LLM
| Technology | Purpose |
|------------|---------|
| **Groq API** | LLM inference provider (ultra-fast inference) |
| **LLaMA 3.3 70B Versatile** | The specific LLM model used for semantic analysis |
| **OpenAI Python SDK** | Client library (Groq is OpenAI API-compatible) |

### 🗄️ Database
| Technology | Purpose |
|------------|---------|
| **SQLite** | Lightweight embedded database for comparison history |

### 🔧 DevOps & Tooling
| Tool | Purpose |
|------|---------|
| **python-dotenv** | Environment variable management (.env files) |
| **Git** | Version control |
| **Poetry / pip** | Dependency management (pyproject.toml / requirements.txt) |

### 🎨 Frontend Libraries (CDN)
| Library | Purpose |
|---------|---------|
| **Lucide Icons** | Modern SVG icon set for the UI |
| **Chart.js** | Interactive performance charts on the dashboard |
| **Google Fonts (Inter, JetBrains Mono)** | Professional typography |

---

## 3. Architecture & Design Patterns

### High-Level Architecture
```
┌─────────────────────────────────────────────────┐
│                    FRONTEND                      │
│  (Single-Page HTML + CSS + JavaScript)           │
│  ┌─────────┐  ┌──────────┐  ┌────────────────┐  │
│  │Dashboard│  │ Compare  │  │   Results View  │  │
│  │  View   │  │   View   │  │ (Text/Visual/AI)│  │
│  └─────────┘  └──────────┘  └────────────────┘  │
└──────────────────────┬──────────────────────────┘
                       │ HTTP (REST API)
┌──────────────────────▼──────────────────────────┐
│                  FASTAPI SERVER                  │
│  ┌────────────┐  ┌────────────┐                  │
│  │ /api/compare│  │ /api/chat  │                  │
│  └──────┬─────┘  └─────┬──────┘                  │
│         │              │                          │
│  ┌──────▼──────────────▼──────────────────────┐  │
│  │           SERVICE LAYER                     │  │
│  │  ┌────────────┐  ┌─────────────┐            │  │
│  │  │ pdf_parser │  │ visual_diff │            │  │
│  │  │ (PyMuPDF)  │  │ (SSIM+CV2)  │            │  │
│  │  ├────────────┤  ├─────────────┤            │  │
│  │  │diff_engine │  │ ai_compare  │            │  │
│  │  │ (difflib)  │  │ (Groq LLM)  │            │  │
│  │  ├────────────┤  ├─────────────┤            │  │
│  │  │ report_gen │  │  database   │            │  │
│  │  │(ReportLab) │  │  (SQLite)   │            │  │
│  │  └────────────┘  └─────────────┘            │  │
│  └─────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

### Design Patterns Used
| Pattern | Where |
|---------|-------|
| **MVC (Model-View-Controller)** | Backend (Services) → API (Controller) → Templates (View) |
| **Service Layer** | Business logic separated into `services/` modules |
| **Repository Pattern** | `database.py` encapsulates all DB operations |
| **REST API** | Clean RESTful endpoints (`/api/compare`, `/api/chat`) |
| **Template Rendering** | Jinja2 templates served via FastAPI |
| **Observer Pattern** | Frontend JS listens for events (drag/drop, form submit) |

---

## 4. Backend Deep Dive

### Project Structure
```
backend/
├── __init__.py          # Package init
├── app.py               # FastAPI app setup, routing, static files
├── config.py            # Centralized configuration (env vars, paths)
├── database.py          # SQLite operations (init, add, query)
├── api/
│   ├── compare.py       # POST /api/compare — main comparison endpoint
│   └── chat.py          # POST /api/chat — AI chat endpoint
└── services/
    ├── pdf_parser.py    # Text extraction + page rendering (PyMuPDF)
    ├── visual_diff.py   # SSIM + bounding-box overlay engine
    ├── diff_engine.py   # Text diff using difflib
    ├── ai_compare.py    # Groq LLM semantic analysis
    ├── report_gen.py    # ReportLab PDF report generation
    └── pdf_report.py    # Additional PDF report utilities
```

### Key Backend Modules

#### `pdf_parser.py` — PDF Parsing
- Uses **PyMuPDF (fitz)** to extract text page-by-page
- Renders pages to images at **200 DPI** for visual comparison
- Handles edge cases: missing files, out-of-range pages

#### `visual_diff.py` — Visual Diff Engine
- Computes **SSIM (Structural Similarity Index)** between page images
- Uses **morphological operations** (closing + dilation) to group nearby changes
- Draws **semi-transparent bounding boxes** with alpha blending
- Returns: overlay image, similarity score (0-1), region count

#### `diff_engine.py` — Text Diff
- Uses Python's built-in **`difflib.SequenceMatcher`**
- Generates per-page text diffs (insert, delete, replace, equal)
- Outputs structured change summaries

#### `ai_compare.py` — AI Semantic Analysis
- Sends document text + image similarity data to **Groq's LLM**
- Uses **LLaMA 3.3 70B Versatile** model
- Returns structured JSON with text changes, image changes, confidence scores
- Includes robust JSON parsing with markdown fence stripping

#### `report_gen.py` — PDF Report Generation
- Uses **ReportLab** to create professional PDF reports
- Includes cover page, table of contents, per-page details
- Color-coded pass/fail status indicators

---

## 5. Frontend Deep Dive

### Single-Page Application (SPA-like)
The frontend is a **single HTML file** (`index.html`) that functions like an SPA:
- Multiple "views" (Dashboard, Compare, Results, History) toggled via JavaScript
- No page reloads — view switching is handled client-side

### Key Frontend Features
| Feature | Implementation |
|---------|----------------|
| **Login Page** | Form with session persistence via `localStorage` |
| **Collapsible Sidebar** | CSS transitions + JS toggle with tooltips |
| **Dashboard** | Stat cards, Chart.js performance graph, recent comparisons |
| **Drag & Drop Upload** | HTML5 Drag & Drop API for PDF files |
| **Results View** | Tabbed interface (Text Changes, Visual Diffs, AI Chat) |
| **GitHub-style Text Diff** | Side-by-side diff table with line numbers & color coding |
| **Image Modal** | Full-screen lightbox for viewing diff images |
| **Welcome Popup** | Glassmorphism-style modal with backdrop blur |
| **Session Management** | `localStorage` for login state persistence |

### CSS Techniques Used
- **CSS Custom Properties (Variables)** for theming
- **Flexbox** for layout
- **CSS Transitions** for smooth animations
- **Backdrop Filter** for blur effects
- **CSS Grid** for icon centering
- **Media queries concept** for responsive design

---

## 6. AI/LLM Integration

### How AI Is Used
1. **Semantic Comparison** (`ai_compare.py`):
   - Page texts from both PDFs + visual similarity scores are sent to the LLM
   - The LLM identifies **meaningful** changes (ignoring logos, headers, footers)
   - Returns structured JSON: text changes, image changes, confidence, impact levels

2. **Interactive Chat** (`chat.py`):
   - Users can ask natural language questions about comparison results
   - Context-aware: the comparison data is injected into the system prompt
   - Maintains conversation history (last 10 messages)

### LLM Details
| Aspect | Detail |
|--------|--------|
| **Provider** | Groq (ultra-fast LLM inference) |
| **Model** | `llama-3.3-70b-versatile` (Meta's LLaMA 3.3, 70B parameters) |
| **API Compatibility** | OpenAI-compatible API (uses `openai` Python SDK) |
| **Temperature** | 0 for comparison (deterministic), 0.3 for chat |
| **Context Window** | Text truncated to ~12,000 chars to stay within limits |
| **Output Format** | Strict JSON schema enforced via system prompt |

### Prompt Engineering Techniques
- **System prompt** defines the AI as a "deterministic PDF comparison engine"
- **Few-shot-like schema** — exact JSON template provided in the prompt
- **Guardrails** — rules like "Do NOT hallucinate", "Output MUST be valid JSON ONLY"
- **Semantic filtering** — instructed to ignore logos, watermarks, page numbers

---

## 7. Key Algorithms & Logic

### SSIM (Structural Similarity Index)
```
Purpose: Measure visual similarity between two page images
Library: scikit-image (skimage.metrics.structural_similarity)
Output: Score from 0.0 (completely different) to 1.0 (identical)
```
**How it works:**
1. Convert both page images to grayscale
2. Compute SSIM with a full diff map
3. Invert the diff map (changed areas become bright)
4. Threshold to isolate significant changes
5. Apply morphological closing + dilation to group nearby pixels
6. Extract contours → draw bounding boxes

### Text Diffing (difflib)
```
Purpose: Line-by-line text comparison
Library: Python's built-in difflib.SequenceMatcher
Output: List of operations (equal, insert, delete, replace)
```
**Process:**
1. Extract text from each page of both PDFs
2. Compare corresponding pages using `SequenceMatcher`
3. Generate opcodes (equal, insert, delete, replace)
4. Build GitHub-style side-by-side diff with line numbers

### Page Count Mismatch Handling
The system gracefully handles PDFs with different page counts:
- **Extra pages in revised** → marked as "ADDED"
- **Missing pages in revised** → marked as "REMOVED"
- **Common pages** → compared normally

---

## 8. Database

### Schema
```sql
CREATE TABLE comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    revised_filename TEXT NOT NULL,
    total_pages INTEGER,
    status TEXT,
    report_url TEXT
);
```

### Why SQLite?
- **Zero configuration** — no separate database server needed
- **File-based** — single `history.db` file
- **Thread-safe** — uses Python's `threading.Lock`
- **Perfect for single-server deployment**

---

## 9. API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/` | Serve the main HTML page |
| `GET` | `/health` | Health check (`{"status": "UP"}`) |
| `POST` | `/api/compare` | Upload 2 PDFs, receive comparison results |
| `GET` | `/api/history` | Fetch last 10 comparison records |
| `POST` | `/api/chat` | Chat with AI about comparison results |

### `/api/compare` Request
- **Content-Type:** `multipart/form-data`
- **Fields:** `original` (File), `revised` (File)
- **Response:** JSON with page-by-page results, base64 images, text diffs, AI analysis

---

## 10. Common Interview Q&A

### Q1: "What is this project about?"
> AuditLens is an enterprise-grade PDF comparison tool. It takes two PDF documents and produces a comprehensive comparison — visual diffs with bounding-box overlays (like Adobe Acrobat), GitHub-style text diffs, and AI-powered semantic analysis using LLaMA 3.3 via Groq. It also generates downloadable PDF reports and has an interactive AI chat feature for follow-up questions.

### Q2: "Why did you choose FastAPI over Flask/Django?"
> FastAPI offers async support out of the box, automatic OpenAPI documentation, built-in request validation via Pydantic, and significantly better performance. For a tool that processes large PDFs and makes API calls to LLMs, async capabilities are crucial to prevent blocking.

### Q3: "How does the visual comparison work?"
> We use SSIM (Structural Similarity Index) from scikit-image to compute a pixel-level difference map between two page images. Then we apply morphological operations (closing and dilation) via OpenCV to group nearby changed pixels into regions. Finally, we draw semi-transparent bounding boxes with alpha blending on the revised page image, keeping the underlying content readable.

### Q4: "Why Groq instead of OpenAI directly?"
> Groq provides extremely fast inference speeds (tokens per second are significantly higher than standard providers) while maintaining compatibility with the OpenAI API format. This means we can use the same `openai` Python SDK but get much faster responses, which is critical for user experience. We use Meta's LLaMA 3.3 70B model which is open-source and performs comparably to GPT-4 for structured tasks.

### Q5: "How do you handle large PDFs?"
> Multiple strategies: (1) Pages are rendered at 200 DPI — a balance between quality and memory. (2) Text is truncated to ~12,000 chars for LLM context limits. (3) Images are served as JPEG at quality 82 (not PNG), reducing payload ~4x. (4) Processing is done page-by-page to avoid loading entire documents into memory.

### Q6: "How is session management handled?"
> Currently, we use client-side `localStorage` to persist login state. When a user logs in, we set `isLoggedIn=true` in localStorage. On page load, a self-executing function checks this flag and skips the login screen if the user is already authenticated. On logout, the flag is removed.

### Q7: "What's the frontend architecture?"
> It's a single-page HTML file that behaves like an SPA. Multiple views (Dashboard, Compare, Results, History) are toggled via JavaScript without page reloads. We use CSS custom properties for theming, Lucide for icons, and Chart.js for data visualization. The design follows modern SaaS aesthetics with a collapsible sidebar, glassmorphism elements, and smooth micro-animations.

### Q8: "How does the AI chat feature work?"
> After a comparison is completed, the results data (page counts, similarity scores, text changes) is injected into the system prompt of the LLM. Users can ask natural language questions like "Which pages have the most changes?" or "Summarize all differences." The chat maintains history for contextual follow-up questions.

### Q9: "What challenges did you face?"
> Key challenges included: (1) Handling PDFs with different page counts gracefully. (2) Making SSIM-based visual diffs readable without obscuring the document content — solved with alpha-blended overlays. (3) Getting consistent JSON output from the LLM — solved with strict schema enforcement and fallback parsing. (4) Keeping the single-page frontend responsive while managing complex state across multiple views.

### Q10: "How would you scale this for production?"
> (1) Replace SQLite with PostgreSQL. (2) Add Redis for task queuing (process PDFs asynchronously via Celery). (3) Move file uploads to cloud storage (S3/Azure Blob). (4) Add proper authentication (Azure AD integration is already partially configured). (5) Containerize with Docker and deploy on Kubernetes. (6) Add rate limiting and API keys for the comparison endpoint.

---

## Quick Reference Card

```
Language:      Python 3.9+, HTML5, CSS3, JavaScript ES6+
Backend:       FastAPI + Uvicorn (ASGI)
Templating:    Jinja2
PDF Library:   PyMuPDF (fitz)
Vision:        OpenCV + scikit-image (SSIM) + NumPy + Pillow
AI/LLM:        Groq API → LLaMA 3.3 70B (via OpenAI SDK)
Database:      SQLite
Reports:       ReportLab
Charts:        Chart.js
Icons:         Lucide Icons
Fonts:         Google Fonts (Inter, JetBrains Mono)
Auth Config:   Azure AD (prepared), localStorage (current)
```

---

*Generated for interview preparation — AuditLens v1.0.0*
