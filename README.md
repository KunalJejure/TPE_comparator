# AI-Powered PDF Comparator

AI-powered PDF comparison application with visual diff capabilities and comprehensive report generation.

## Features

- **Visual Comparison**: Compare two PDF files side-by-side with visual difference highlighting.
- **Report Generation**: Generate detailed PDF reports summarizing the differences.
- **Interactive UI**: Built with Streamlit for a user-friendly experience.
- **Upload Support**: Easily upload reference and comparison PDF files.

## Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python, FastAPI
- **PDF Processing**: ReportLab, PyPDF2 (or similar libraries used)
- **Image Processing**: OpenCV, Pillow, Scikit-image
- **AI Integration**: OpenAI API (for AI-powered analysis)

## Setup

### Prerequisites

- Python 3.10+
- Git

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/continuous-intelligence/FSB_TPE_Comparator-.git
    cd FSB_TPE_Comparator-
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the root directory and add your API keys (e.g., OpenAI API key) if required.
    ```
    OPENAI_API_KEY=your_api_key_here
    ```

## Usage

Run the Streamlit application:

```bash
streamlit run main.py
```

Navigate to the URL provided in the terminal (usually `http://localhost:8501`).

## Contributing

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/amazing-feature`).
3.  Commit your changes (`git commit -m 'Add some amazing feature'`).
4.  Push to the branch (`git push origin feature/amazing-feature`).
5.  Open a Pull Request.
