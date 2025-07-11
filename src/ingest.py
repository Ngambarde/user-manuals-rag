import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

DATA_PATH = "documents/"
DB_FAISS_PATH = "vector_store/"

def create_vector_db():
    print("Loading documents...")
    loader = PyPDFDirectoryLoader(DATA_PATH)
    documents = loader.load()

    if not documents:
        print("No documents found")
        return
    
    print("Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size = 500, chunk_overlap = 50)
    texts = text_splitter.split_documents(documents)

    if not texts:
        print("Error splitting documents")
        return
    
    print("Creating embeddings...")
    embeddings = OpenAIEmbeddings()

    if not embeddings:
        print("Error creating embeddings")
        return
    
    print("Creating and saving vector store...")
    db = FAISS.from_documents(texts, embeddings)
    db.save_local(DB_FAISS_PATH)
    print(f"Vector store created and saved at {DB_FAISS_PATH}")


if __name__ == "__main__":
    load_dotenv()
    create_vector_db()