# Customer Sentiment Analysis System

A modern, AI-powered web application that helps businesses understand customer opinions by analysing feedback with large language models via OpenRouter. Supports individual comment analysis and bulk analysis of PDF / TXT documents.

## Features

- **Individual feedback analysis** – paste a customer comment and receive sentiment classification, explanation, keywords, complaint categories, and suggested actions.
- **Document analysis** – upload PDF or TXT files; the system extracts text, segments feedback, analyses each portion, and produces an aggregated report.
- **Dashboard** – live statistics, doughnut distribution chart, and sentiment trends over time (Chart.js).
- **Feedback history** – searchable, filterable list of all analysed feedback with detail view.
- **Customer insights** – recurring complaints, positive themes, and improvement areas derived from stored results.
- **Secure design** – API keys stay on the server; uploads are validated and stored outside the public directory.

## Technology Stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Frontend     | HTML5, CSS3, JavaScript, Chart.js, Lucide icons |
| Backend      | Python 3.10+, Flask, Flask-CORS     |
| AI           | OpenRouter Chat Completions API     |
| Database     | SQLite                              |
| PDF parsing  | PyMuPDF (fitz)                      |

## Prerequisites

- Python 3.10 or newer
- An [OpenRouter](https://openrouter.ai/) account and API key
- Internet access for AI analysis requests

## Installation (Windows)

1. **Clone or extract** the project into a folder, e.g. `C:\Projects\customer-sentiment-analysis`.

2. **Open a terminal** (Command Prompt or PowerShell) in that folder.

3. **Create a virtual environment:**
   ```bat
   python -m venv venv
   ```

4. **Activate it:**
   ```bat
   venv\Scripts\activate
   ```

5. **Install dependencies:**
   ```bat
   pip install -r requirements.txt
   ```

6. **Configure environment variables:**
   ```bat
   copy .env.example .env
   ```
   Edit `.env` with a text editor and set:
   ```
   OPENROUTER_API_KEY=sk-or-v1-your-actual-key
   OPENROUTER_MODEL=openai/gpt-4o-mini
   SECRET_KEY=any-long-random-string
   ```

### Selecting a model

OpenRouter supports many models. Recommended starting points:

- `openai/gpt-4o-mini` – fast and cost-effective
- `openai/gpt-4o` – higher quality
- `anthropic/claude-3.5-sonnet` – strong reasoning
- `google/gemini-flash-1.5` – good balance

Change `OPENROUTER_MODEL` in `.env` and restart the app. No code changes are required.

## Running the Application

With the virtual environment activated:

```bat
python app.py
```

Open a browser at **http://127.0.0.1:5000**.

The AI service status indicator in the sidebar shows whether OpenRouter is reachable with the configured key.

## Usage Overview

1. **Analyse Feedback** – enter a comment and click *Analyse Sentiment*.
2. **Document Analysis** – drag a PDF or TXT file, then *Upload & Analyse*. Large documents are automatically chunked.
3. **Overview** – view totals, percentages, charts, and top complaint categories.
4. **History** – search and filter past analyses; open any record for full detail.
5. **Insights** – see aggregated complaint and praise themes.

## API Endpoints

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/api/health`                     | App + AI service status              |
| POST   | `/api/analyze`                    | Analyse a single feedback string     |
| POST   | `/api/documents/upload`           | Upload PDF/TXT                       |
| POST   | `/api/documents/<id>/analyze`     | Process an uploaded document         |
| GET    | `/api/documents`                  | List documents                       |
| GET    | `/api/documents/<id>`             | Document detail + report             |
| DELETE | `/api/documents/<id>`             | Delete document and related records  |
| GET    | `/api/feedback`                   | List feedback (filters + pagination) |
| GET    | `/api/stats`                      | Dashboard statistics                 |
| GET    | `/api/trends`                     | Sentiment over time                  |
| GET    | `/api/insights`                   | Aggregated customer insights         |

## Testing

Basic automated tests (mocked OpenRouter calls):

```bat
pip install pytest pytest-mock
pytest tests/ -v
```

Manual checklist:

1. Start the app and confirm the health endpoint returns AI status.
2. Analyse a short positive and a short negative comment.
3. Upload a small TXT file with a few paragraphs of feedback.
4. Upload a PDF that contains selectable text.
5. Try an empty file, a `.docx`, and a file larger than 10 MB – expect clear errors.
6. Confirm dashboard numbers update after new analyses.
7. Search and filter history.
8. Open a completed document report from the documents list.
9. Stop the server, set an invalid API key, restart, and verify friendly error messages.

## Troubleshooting

| Problem                         | Suggestion                                              |
|---------------------------------|---------------------------------------------------------|
| “API key is not configured”     | Ensure `.env` exists and contains a real key            |
| “Invalid OpenRouter API key”    | Check the key on openrouter.ai                          |
| “Insufficient credits”          | Top up your OpenRouter account                          |
| “No selectable text found”      | PDF is likely scanned; OCR is not enabled by default    |
| Charts show “No data yet”       | Analyse at least one piece of feedback first            |
| Port already in use             | Set `PORT=5001` in `.env` or stop the other process     |

## Project Structure

```
customer-sentiment-analysis/
├── app.py                  # Flask entry point
├── requirements.txt
├── .env.example
├── README.md
├── backend/
│   ├── database.py
│   ├── sentiment_analyzer.py
│   ├── document_processor.py
│   ├── insights.py
│   ├── routes.py
│   └── validators.py
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
├── uploads/                # Stored documents (not public)
├── instance/               # SQLite database
└── tests/
```

## Security Notes

- Never commit `.env` or expose `OPENROUTER_API_KEY`.
- Uploaded files are stored under `uploads/` with randomised names.
- File type and size are validated on the server.
- AI prompts instruct the model to treat document content as data only.
- Customer feedback is stored in a local SQLite database; apply your own retention policy as needed.

## License

This project is provided as a complete reference implementation for educational and commercial adaptation.
