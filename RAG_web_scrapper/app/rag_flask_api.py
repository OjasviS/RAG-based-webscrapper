from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, render_template
import asyncio
from crawler import WebsiteCrawler
from indexing import create_vector_store
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS 
from openai import OpenAI
import time
import os



app = Flask(__name__, template_folder='templates', static_folder='static')



@app.route('/crawl', methods = ['POST'])
def crawl():
    """
    POST/crawl
    {
        "url": "https://example.com",
        "max_pages": max number of pages to crawl,
        "crawl_delay": some delay
    }
    """
    data = request.get_json()
    url = data.get('url')
    max_pages = data.get('max_pages', 1)
    crawl_delay = data.get('crawl_delay', 0.5)
    if not url:
        return jsonify({"error": "URL is required"}), 400
    crawler = WebsiteCrawler(url, max_pages=max_pages, crawler_delay=crawl_delay)
    start = time.time()
    asyncio.run(crawler.crawl(n_workers=1))
    end = time.time()
    elapsed = end - start
    if not os.path.exists('data/crawled_data.json'):
        return jsonify({"error": "Crawling failed"}), 500
    return jsonify({
        "message": f"Crawling complete ({elapsed}s)",
        "page_count": len(crawler.results),
        "urls": list(crawler.results.keys())
    })

@app.route('/', methods = ['GET'])
def home():
    return render_template('index.html')

@app.route('/index', methods = ['POST'])
def index():
    """
    POST/index
    {
        "chunk_size": 800,
        "chunk_overlap": 100
    }
    """
    data = request.get_json()
    chunk_size = data.get('chunk_size', 800)
    chunk_overlap = data.get('chunk_overlap', 100)
    start = time.time()
    try:
        chunk_count, vector_store_path = create_vector_store(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 500
    end = time.time()
    elapsed = end - start
    if not os.path.exists(vector_store_path):
        return jsonify({"error": "Vector store creation failed"}), 500
    return jsonify({
        "message": f"Indexing complete {elapsed}s",
        "chunk_count": chunk_count,
        "vector_store_path": vector_store_path
    })

@app.route('/ask', methods = ['POST'])
def ask():
    """
    POST/ask
    {
        "question": some question,
        "top_k": number of top similar chunks to retrieve (default 3)
        
    }
    """
    data = request.get_json()
    question = data.get('question')
    top_k = data.get('top_k', 3)
    if not question:
        return jsonify({"error": "Question is required"}), 400

    embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    try:
        vs = FAISS.load_local('/Users/ojasvihallikhede/Projects/RAG_web_scrapper/data/faiss_index', embedder, allow_dangerous_deserialization=True)

    except Exception as e:
        return jsonify({"error": 'vector store loading failed'}), 500

    t0 = time.time()
    docs = vs.similarity_search(question, k=top_k)
    retrieval_time = time.time() - t0
    context = '\n\n'.join([doc.page_content for doc in docs])
    sources = [{"url": doc.metadata["source"], "snippet": doc.page_content[:200]} for doc in docs]

    systemPrompt = """You are a precise and factual assistant. Your job is to answer the questions only based on the provided context. If context is insufficient, say "Answer to question not found in crawled data". Keep the answers as concise as possible."""
    user_prompt = f"""Context:\n{context}\n\nQuestion: {question}"""

    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    t1 = time.time()
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": systemPrompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"error": f"LLM query failed: {e}"}), 500
    answer_time = time.time() - t1
    return jsonify({
        "question": question,
        "answer": answer,
        "sources": sources,
        "timings": {
            "retrieval_time": retrieval_time,
            "answer_time": answer_time,
            "total_time": retrieval_time + answer_time
        }
    })
if __name__ == "__main__":
    app.run(debug=True)


