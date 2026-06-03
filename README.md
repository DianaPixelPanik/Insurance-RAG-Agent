# 🛡️ InsurAI — Intelligent Insurance Automation System

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Anthropic-D97757?style=flat-square&logo=anthropic&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-orange?style=flat-square)
![Agno](https://img.shields.io/badge/Agno-AI_Framework-6366F1?style=flat-square)
![ReportLab](https://img.shields.io/badge/ReportLab-PDF-red?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

An end-to-end InsurTech platform that combines **computer vision**, **retrieval-augmented generation (RAG)**, and an **AI-guided claims workflow** to automate vehicle damage assessment, insurance knowledge retrieval, and claim filing — powered by Anthropic Claude.

---

## 🌟 Key Features

- **🔍 Computer Vision Damage Assessment** — Upload a photo of a damaged vehicle; Claude Vision automatically identifies damaged parts, severity levels, and estimated repair costs
- **📄 PDF Report Generation** — Download a professional damage assessment report or claim receipt with a single click
- **🤖 RAG Insurance Assistant** — Ask natural-language questions about policies, customers, and claims; answers are retrieved from your PDF knowledge base via ChromaDB vector search
- **📋 AI-Guided Claims Workflow** — A three-step claim filing flow: incident chat → Pledge of Honesty → instant claim decision
- **🧠 Session Memory** — Claude remembers conversation context across turns using SQLite-backed agent storage
- **⚡ Real-Time Streaming** — Responses stream character-by-character for a natural conversational feel

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Frontend                      │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │ Damage       │  │ File a Claim   │  │ Insurance      │  │
│  │ Analysis     │  │ (3-step flow)  │  │ Chat (RAG)     │  │
│  └──────┬───────┘  └───────┬────────┘  └───────┬────────┘  │
└─────────┼──────────────────┼───────────────────┼───────────┘
          │                  │                   │
          ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                      Flask Backend                          │
│  ┌──────────────────┐         ┌───────────────────────────┐ │
│  │  /analyze-damage │         │         /query            │ │
│  │  Claude Vision   │         │  Agno Agent + RAG         │ │
│  │  (claude-opus)   │         │  (claude-sonnet)          │ │
│  └──────────────────┘         └───────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
          │                                      │
          ▼                                      ▼
   Anthropic API                    ┌────────────────────┐
   (Vision + Chat)                  │   ChromaDB Vector  │
                                    │   SQLite Storage   │
                                    └────────────────────┘
```

---

## 📁 Project Structure

```
Insurance-RAG-Agent/
├── backend_app.py            # Flask API server (damage analysis + RAG agent)
├── streamlit_app.py          # Streamlit UI (3 tabs: damage, claims, chat)
├── agent_instructions.txt    # System prompt for the RAG insurance agent
├── requirements.txt          # Python dependencies
├── .env                      # API keys and configuration (not committed)
├── .env.example              # Environment variable template
├── data/                     # PDF knowledge base documents (add your PDFs here)
├── database_files/
│   ├── agent_storage.db      # SQLite session + memory storage
│   └── insurance_data/       # ChromaDB vector store
├── creating_postgres_database.py   # Optional: PostgreSQL integration
├── first_vector_embedding.py       # Optional: standalone embedding script
└── syncing_databases.py            # Optional: Milvus sync utility
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com) (required)
- An [OpenAI API key](https://platform.openai.com) (required for embeddings)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/Insurance-RAG-Agent.git
cd Insurance-RAG-Agent
```

### 2. Create a virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** If `psycopg2` fails to build, use `psycopg2-binary` instead (PostgreSQL integration is optional).

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
# Required
ANTHROPIC_API_KEY="sk-ant-..."
OPENAI_API_KEY="sk-proj-..."

# Backend URL (used by Streamlit)
BACKEND_URL=http://localhost:8000

# Optional: PostgreSQL
PG_DB_URL="postgresql://user:password@localhost:5432/dbname"
```

### 5. Add your PDF knowledge base

Place insurance policy PDFs, customer records, or any relevant documents in the `data/` folder:

```bash
mkdir -p data
cp your-insurance-docs/*.pdf data/
```

> The knowledge base is automatically loaded when the backend starts (skipping existing documents on subsequent runs).

### 6. Start the backend

```bash
python backend_app.py
```

The Flask server starts on **http://localhost:8000**

### 7. Start the Streamlit frontend

Open a second terminal:

```bash
streamlit run streamlit_app.py
```

The app opens at **http://localhost:8501**

---

## 🖥️ Application Tabs

### 🔍 Tab 1 — Damage Analysis

| Step | Action |
|------|--------|
| 1 | Upload a photo of a damaged vehicle (JPG, PNG, WEBP) |
| 2 | Click **"Analyze damage"** |
| 3 | View the AI-generated report: damaged parts, severity, cost estimates |
| 4 | Download a professional **PDF report** |

**Report includes:**
- Overall severity rating (Low / Medium / High / Critical)
- Per-component breakdown with repair type and cost range
- Safety concerns and actionable recommendations
- AI confidence score and estimated repair time

### 📋 Tab 2 — File a Claim

A guided, three-step claim filing workflow:

| Step | Screen | Description |
|------|--------|-------------|
| 1 | **Incident Report** | AI chatbot asks guided questions; user selects property category |
| 2 | **Pledge of Honesty** | Identity photo, electronic signature, honesty confirmation |
| 3 | **Claim Approved** | Instant decision, payout amount, downloadable PDF receipt |

> **Pledge of Honesty** is a psychological anti-fraud mechanism — users affirm they are only claiming genuine losses before submission.

### 💬 Tab 3 — Insurance Chat

Natural-language Q&A over your insurance knowledge base:

```
User:  "What is John Smith's policy number?"
Agent: Searches ChromaDB → Extracts answer → "John Smith's policy number is LIFE-001."
```

**Capabilities:**
- Policy lookup by customer name or ID
- Claims status queries
- Coverage comparison across multiple policies
- Date calculations (policy expiry, claim deadlines)
- Multi-turn conversation with session memory

---

## 🧠 AI Components

| Component | Model | Purpose |
|-----------|-------|---------|
| Damage Vision | `claude-opus-4-5` | Analyze vehicle photos, detect damage, estimate costs |
| RAG Agent | `claude-sonnet-4-5` | Answer insurance questions using retrieved documents |
| Embeddings | `text-embedding-3-large` | Convert PDF content into searchable vectors |
| Vector Store | ChromaDB | Store and retrieve document embeddings |
| Agent Memory | SQLite (Agno) | Persist conversation history and session summaries |

---

## 📦 Core Dependencies

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude Vision + Chat API |
| `agno` | AI agent framework with RAG, memory, and storage |
| `streamlit` | Web UI |
| `flask` | REST API backend |
| `chromadb` | Vector database for document embeddings |
| `openai` | Text embeddings (`text-embedding-3-large`) |
| `pypdf` | PDF document parsing |
| `chonkie` | Document chunking |
| `reportlab` | PDF report generation |
| `sqlalchemy` | SQLite ORM for agent storage |

---

## 🔒 Security Notes

- **Never commit `.env`** — it contains your API keys. The `.gitignore` should exclude it.
- Rotate API keys immediately if accidentally exposed in public repositories or chats.
- The `database_files/` directory contains your vector store and session data — back it up regularly.

---

## 🔮 Future Enhancements

- [ ] Video damage assessment (frame-by-frame analysis)
- [ ] Multi-vehicle support in a single claim
- [ ] Integration with real repair shop APIs for live cost quotes
- [ ] Email/SMS notifications on claim approval
- [ ] Admin dashboard for claims management
- [ ] Support for additional document types (DOCX, Excel)
- [ ] Multilingual support (auto-detect user language)
- [ ] PostgreSQL + Milvus production deployment mode

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

Built with ❤️ using [Anthropic Claude](https://anthropic.com) and [Agno](https://github.com/agno-agi/agno).

*Inspired by the InsurTech industry's push toward AI-driven claims automation and instant settlements.*
