# RAG-Based Web Scrapper

This repository implements a small **Retrieval-Augmented Generation (RAG)** service that crawls a website, indexes its content, and answers questions grounded strictly in that content.  
It demonstrates practical skills in web data ingestion, embedding-based retrieval, grounded prompting, and API design.

---

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/RAG-webscrapper.git
   cd RAG-webscrapper

2. **Create and activate a virtual environment**
   ```bash
   conda create -n rag_env python=3.11
   conda activate rag_env
   
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   
4. **Set your OpenAi API key**
   ```bash
   export OPENAI_API_KEY="your_api_key_here"
   

---

## Run

1. **Start the Flask API**
   ```bash
   python app/rag_flask_api.py

2. **The server will run on local host**
   ```bash
   http://127.0.0.1:5000

3. **The enpoints in the API are**
   1. `/crawl` — crawl and extract website content
   2. `/index` — create embeddings and store them in FAISS
   3. `/ask` — query using a question grounded in crawled content

---

## Evaluation

1. **/crawl**
     
**Request**
```bash
curl -X POST http://127.0.0.1:5000/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://fastapi.tiangolo.com", "max_pages": 3, "crawl_delay": 0.5}'
```
**Response**
```json
{
  "message": "Crawling complete (8.3s)",
  "page_count": 3,
  "urls": [
    "https://fastapi.tiangolo.com",
    "https://fastapi.tiangolo.com/advanced/security/http-basic-auth/",
    "https://fastapi.tiangolo.com/deployment/https/"
  ]
}
```

2. **/index**
     
**Request**
```bash
curl -X POST http://127.0.0.1:5000/index \
     -H "Content-Type: application/json" \
     -d '{
           "chunk_size": 800,
           "chunk_overlap": 100
         }'
```
**Response**
```json
{
  "message": "Indexing complete (3.9s)",
  "chunk_count": 108,
  "vector_store_path": "data/faiss_index"
}
```

3. **/ask**
   
**Answer found in context**

**Request**
```bash
curl -X POST http://127.0.0.1:5000/ask \
     -H "Content-Type: application/json" \
     -d '{
           "question": "How can HTTPS be enabled when deploying a FastAPI app?",
           "top_k": 3
         }''
```
**Response**
```json
{
  "question": "How can HTTPS be enabled when deploying a FastAPI app?",
  "answer": "HTTPS can be enabled by running FastAPI behind a reverse proxy such as Nginx or Traefik with SSL certificates, or by using Uvicorn with --ssl-keyfile and --ssl-certfile.",
  "sources": [
    {
      "url": "https://fastapi.tiangolo.com/deployment/https/",
      "snippet": "You can add HTTPS by running FastAPI behind a reverse proxy like Nginx or Traefik configured with Let's Encrypt certificates."
    }
  ],
  "timings": {
    "retrieval_time": 0.42,
    "answer_time": 1.98,
    "total_time": 2.40
  }
}
```

**Answer not found in context**

**Request**
```bash
curl -X POST http://127.0.0.1:5000/ask \
     -H "Content-Type: application/json" \
     -d '{
           "question": "Who created FastAPI?",
           "top_k": 3
         }'
```
**Response**
```json
{
  "question": "Who created FastAPI?",
  "answer": "Answer to question not found in crawled data.",
  "sources": [
    {
      "url": "https://fastapi.tiangolo.com/",
      "snippet": "FastAPI is a modern web framework for building APIs with Python 3.6+..."
    }
  ],
  "timings": {
    "retrieval_time": 0.39,
    "answer_time": 1.67,
    "total_time": 2.06
  }
}
```
---
## Architecture Description

1.	**Crawler**: Uses aiohttp, BeautifulSoup, and readability-lxml to extract readable text.
2.	**Politeness**: Respects robots.txt and enforces a configurable delay.
3.	**Scope Control**: Limits crawling to the same registered domain.
4.	**Storage**: Saves extracted text in /data/crawled_data.json.
5.	**Chunking**: Uses RecursiveCharacterTextSplitter for overlapping text segmentation.
6.	**Embeddings**: Employs sentence-transformers/all-MiniLM-L6-v2 via HuggingFace.
7.	**Vector Index**: Stores embeddings in FAISS for efficient similarity retrieval.
8.	**Retrieval**: Returns top-k relevant chunks for each query.
9.	**LLM Layer**: GPT-3.5-Turbo generates grounded answers from context.
10.	**Refusal Logic**: Returns a polite fallback when information is missing.
11.	**Flask Backend**: Exposes /crawl, /index, /ask as HTTP APIs.
12.	**Timing Metrics**: Measures and returns retrieval and response latency.
13.	**File-based Design**: Simple JSON and FAISS files for easy reproducibility.
14.	**Extensible**: Embeddings, database, and model components can be swapped.
15.	**Optional Frontend**: Minimal HTML/JS frontend using Fetch API.

---

## Trade offs

	•	Crawling limited to ~30–50 pages to prevent overloading hosts.
	•	Uses CPU-based FAISS for portability; GPU could improve speed.
	•	Embedding quality depends on model choice (trade-off between accuracy and runtime).
	•	Minimal error handling for simplicity under a time constraint.
	•	OpenAI’s GPT model used for grounded generation; open models can replace it.
	•	Readability parser may skip dynamic JavaScript content.
	•	Simple file-based storage avoids DB complexity but limits scalability.
	•	Chose Flask over FastAPI for simplicity and lower learning overhead.
	•	RAG pipeline designed for reproducibility over performance.
	•	Balanced design — small, interpretable, and easy to extend.





   
   
    





  
   

   
   
