import json
from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")

def create_vector_store(chunk_size = 800, chunk_overlap = 100):
    data_path = Path('/Users/ojasvihallikhede/Projects/RAG_web_scrapper/data/crawled_data.json')
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found at {data_path}")
    print(f"Loading data from {data_path}...")
    with open(data_path, 'r') as f:
        data = json.load(f)

    docs = [{'text': c['text'], 'source': url} for url, c in data.items() if c['text'].strip()]
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = []
    print('creating chunks...')
    for doc in docs:
        chunks_for_curr_doc = text_splitter.split_text(doc['text'])
        for i in chunks_for_curr_doc:
            chunks.append({'text': i, 'source': doc['source']})
    embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    texts = [chunk['text'] for chunk in chunks]
    metadatas = [{'source': chunk['source']} for chunk in chunks]
    print(f"Creating vector store with {len(texts)} chunks...")
    path_with_vector_store = '/Users/ojasvihallikhede/Projects/RAG_web_scrapper/data/faiss_index'
    vector_store = FAISS.from_texts(texts, embedder, metadatas=metadatas)
    vector_store.save_local(path_with_vector_store)
    
    return len(chunks), path_with_vector_store






   