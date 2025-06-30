# Two-Tier Recommendation System
Run the project
  uvicorn app.main:app --reload
A sophisticated recommendation system for professional networking and event platforms, featuring a two-tier architecture:

1. **Tier 1**: Knowledge Graph-based recommendations using Neo4j
2. **Tier 2**: ML-based semantic recommendations (coming soon)

## 🏗️ Project Structure

```
.
├── app/
│   ├── api/                 # FastAPI endpoints
│   ├── core/               # Core business logic
│   ├── db/                 # Database models and connections
│   ├── models/             # Pydantic models
│   ├── services/           # Business services
│   └── utils/              # Utility functions
├── data_processing/        # Data ingestion and processing
│   ├── transcript/         # Transcript processing pipeline
│   └── enrichment/         # Knowledge graph enrichment
├── tests/                  # Test suite
├── .env.example           # Example environment variables
├── requirements.txt       # Project dependencies
└── README.md             # This file
```

## 🚀 Getting Started

1. **Environment Setup**
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Copy environment variables
   cp .env.example .env
   ```

2. **Neo4j Setup**
   - Install Neo4j Desktop or use Neo4j Aura (cloud)
   - Update `.env` with your Neo4j credentials

3. **Start the Application**
   ```bash
   uvicorn app.main:app --reload
   ```

## 📚 API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔄 Data Flow

1. **Data Ingestion**
   - Transcripts from ElevenLabs
   - LinkedIn data
   - Event data from organizers
   - Product information from exhibitors

2. **Knowledge Graph Enrichment**
   - NLP processing of transcripts
   - Entity extraction
   - Relationship inference
   - Graph updates

3. **Recommendation Generation**
   - Rule-based recommendations (Tier 1)
   - Semantic recommendations (Tier 2 - coming soon)

## 🛠️ Development

### Running Tests
```bash
pytest
```

### Code Style
```bash
black .
flake8
```
## 🛠️ Setup Instructions

1. **Clone the repository**

   ```bash
   git clone <your-repo-url>
   cd <project-folder>
   ```

2. Initialize the environment

   ```bash
   uv venv
   ```

3. **Sync dependencies**

   ```bash
   uv sync
   ```
## 📝 License

MIT License - see LICENSE file for details 
