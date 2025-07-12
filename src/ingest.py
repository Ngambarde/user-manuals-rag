import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from document_parser import parse_pdf_elements

DATA_PATH = "documents/"
DB_FAIS_PATH = "vector_store/"

def create_vector_db():
    print("Starting document ingestion process...")
    
    all_chunks = []
    pdf_files = [f for f in os.listdir(DATA_PATH) if f.endswith('.pdf')]

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

    for pdf_file in pdf_files:
        file_path = os.path.join(DATA_PATH, pdf_file)
        print(f"Processing {file_path}...")
        
        elements = parse_pdf_elements(file_path)

        for element in elements:
            category = element.metadata.get('category')
            
            if category == "Table":
                # For tables, they will be stored in an HTML representation as a single, complete chunk
                table_html = element.metadata.get('text_as_html', '')
                if table_html:
                    all_chunks.append(Document(
                        page_content=table_html,
                        metadata={
                            'source': pdf_file,
                            'page_number': element.metadata.get('page_number'),
                            'content_type': 'table'
                        }
                    ))
            elif category in ["Title", "NarrativeText", "ListItem"]:
                # For text based elements, use a standard text splitter
                chunks = text_splitter.split_documents([element])
                for chunk in chunks:
                    chunk.metadata['content_type'] = 'text'
                    all_chunks.append(chunk)

    if not all_chunks:
        print("No chunks were created. Exiting")
        return

    print(f"Total chunks created: {len(all_chunks)}")
    print("Creating embeddings and vector store...")
    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(all_chunks, embeddings)
    db.save_local(DB_FAIS_PATH)
    print(f"Vector store created successfully at {DB_FAIS_PATH}")
    
    # --- Print statistics ---
    content_types = {}
    for text in all_chunks:
        content_type = text.metadata.get('content_type', 'unknown')
        content_types[content_type] = content_types.get(content_type, 0) + 1
    
    print("\nChunk statistics:")
    for content_type, count in content_types.items():
        print(f"  {content_type}: {count} chunks")

if __name__ == "__main__":
    load_dotenv()
    create_vector_db()