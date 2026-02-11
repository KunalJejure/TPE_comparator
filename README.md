# AI-Powered PDF Comparator

Enterprise-grade PDF comparison with text diffing, visual overlays, and AI-powered insights.

## Features

- **Side-by-Side Text Diff** — GitHub-style line-by-line comparison across all pages
- **Visual Difference Overlay** — SSIM-based image comparison with highlighted change regions
- **AI Chat Assistant** — Ask questions about the comparison results via Groq LLM
- **Modern Dashboard** — Clean, responsive single-page UI with stats and charts
- **PDF Report Generation** — Downloadable comparison report

## Tech Stack

| Layer     | Technology |
|-----------|-----------|
| Frontend  | HTML / CSS / JavaScript, Chart.js, Lucide Icons |
| Backend   | Python, FastAPI, Uvicorn |
| PDF       | PyMuPDF (fitz), ReportLab, Pillow |
| Vision    | OpenCV, scikit-image (SSIM) |
| AI        | Groq API (LLaMA 3.3 70B) via OpenAI SDK |

## Project Structure

```
FSB_TPE_Comparator-/
├── backend/
│   ├── __init__.py
│   ├── app.py              # FastAPI application
│   ├── config.py           # Environment + paths
│   ├── api/
│   │   ├── __init__.py
│   │   ├── compare.py      # POST /api/compare
│   │   └── chat.py         # POST /api/chat
│   └── services/
│       ├── __init__.py
│       ├── ai_compare.py   # Groq AI semantic comparison
│       ├── diff_engine.py  # Text diff calculations
│       ├── pdf_parser.py   # PDF text + image extraction
│       ├── pdf_report.py   # Simple diff PDF (PIL-based)
│       ├── report_gen.py   # Detailed PDF report (ReportLab)
│       └── visual_diff.py  # SSIM visual diffing
├── frontend/
│   ├── templates/
│   │   └── index.html      # Dashboard UI
│   └── static/
│       └── images/
├── tests/
│   └── test_compare.py
├── main.py                 # Entry point
├── requirements.txt
├── pyproject.toml
├── .env                    # (create this — not committed)
└── README.md
```

## Setup & Run

### Prerequisites

- **Python 3.9+** (3.10, 3.11, 3.12 all work)
- **Git**
- **pip** (comes with Python)

---

### macOS / Linux

```bash
# 1. Clone
git clone https://github.com/continuous-intelligence/FSB_TPE_Comparator-.git
cd FSB_TPE_Comparator-

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create .env file with your Groq API key
echo "GROQ_API_KEY=your_groq_api_key_here" > .env

# 5. Run the server
python main.py
```

Open **http://localhost:8000** in your browser.

---

### Windows (CMD / PowerShell)

```powershell
# 1. Clone
git clone https://github.com/continuous-intelligence/FSB_TPE_Comparator-.git
cd FSB_TPE_Comparator-

# 2. Create virtual environment
python -m venv venv

# 3. Activate (pick ONE based on your shell):
# CMD:
venv\Scripts\activate.bat
# PowerShell:
venv\Scripts\Activate.ps1
# Git Bash:
source venv/Scripts/activate

# 4. Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Create .env file
echo GROQ_API_KEY=your_groq_api_key_here > .env

# 6. Run the server
python main.py
```

Open **http://localhost:8000** in your browser.

#### Windows Troubleshooting

| Problem | Solution |
|---------|----------|
| `python` not found | Use `py` instead of `python`, or add Python to your system PATH. Reinstall Python from [python.org](https://www.python.org/downloads/) and check **"Add Python to PATH"** during installation. |
| PowerShell script execution error (`Activate.ps1 cannot be loaded`) | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` in PowerShell first, then try again. |
| `pip install` fails on `opencv-python` | Try: `pip install opencv-python-headless` instead. Edit `requirements.txt` to replace `opencv-python` with `opencv-python-headless`. |
| `pip install` fails on `scikit-image` | Make sure you have the latest pip: `python -m pip install --upgrade pip setuptools wheel`, then retry. |
| `ModuleNotFoundError: No module named 'backend'` | Make sure you are running `python main.py` from the **project root directory** (the folder containing `main.py` and the `backend/` folder). |
| Port 8000 already in use | Either close the other process, or change the port: `python -c "import uvicorn; uvicorn.run('backend.app:app', host='0.0.0.0', port=8080, reload=True)"` |
| `ImportError: DLL load failed` (numpy/cv2) | Install the Visual C++ Redistributable from [Microsoft](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). |
| `.env` file not loading | Make sure the `.env` file is in the project root (same folder as `main.py`), not inside `backend/`. |

---

### Using Poetry (alternative)

```bash
# Install Poetry if needed: https://python-poetry.org/docs/#installation
poetry install
poetry run python main.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes (for AI features) | Your [Groq API key](https://console.groq.com/keys). AI chat and semantic comparison won't work without it. The app still runs for text/visual diff. |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/`  | Dashboard UI |
| `GET`  | `/health` | Health check |
| `POST` | `/api/compare` | Upload two PDFs for comparison |
| `POST` | `/api/chat` | Chat with AI about comparison results |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
