import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from google.cloud import secretmanager

def get_gcp_secret(secret_id, project_id, version_id="latest"):
    """
    Retrieves a secret from Google Cloud Secret Manager.
    If the secret is not found, it fall back to environment variables.
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name":name})
        print(f"Secret {secret_id} retrieved successfully")
        key = response.payload.data.decode("UTF-8").strip()
    except Exception as e:
        print(f"Error retrieving secret {secret_id} from GCP: {e}")
        print("Falling back to environment variable '{secret_id}'.")
        key = os.getenv(secret_id).strip()
        if not key:
            raise ValueError(f"Secret {secret_id} is not found in the environment variables or GCP")
    return key


class RAGSystem:
    def __init__(self):
        # Configuration from environment variables
        load_dotenv()
        gcp_project_id = os.getenv("GCP_PROJECT_ID")
        if not gcp_project_id:
            raise ValueError("GCP_PROJECT_ID is not set in the environment variables")

        os.environ["OPENAI_API_KEY"] = get_gcp_secret("OPENAI_API_KEY", gcp_project_id)

        db_path = os.getenv("DB_FAISS_PATH", "vector_store")


        print("Initializing RAG System...")

        self.embeddings = OpenAIEmbeddings()

        print(f"Loading FAISS Database from: ", db_path)
        self.db = FAISS.load_local(
            db_path,
            self.embeddings,
            allow_dangerous_deserialization=True
        )

        self.llm = ChatOpenAI(model="gpt-4.1-nano-2025-04-14")
        self.retriever = self.db.as_retriever(search_kwargs={"k": 2})

        prompt = ChatPromptTemplate.from_template(
            """Answer the following question based only on the provided context:

            <context>
            {context}
            </context>

            Question: {input}"""
        )

        self.document_chain = create_stuff_documents_chain(self.llm, prompt)
        self.retrieval_chain = create_retrieval_chain(self.retriever, self.document_chain)

        print("RAG System initialized successfully")

    def get_rag_response(self, query_text: str) -> dict:
        """
        Retrieves the answer and source documents for a given query
        """
        response = self.retrieval_chain.invoke({"input": query_text})

        source_documents = []

        if "context" in response and response["context"]:
            for doc in response["context"]:
                source_info = f"source: {doc.metadata.get('source', 'N/A')}"
                source_page = f"page: {doc.metadata.get('page', 'N/A')}"

                source_documents.append(f"{source_info}, {source_page}")

        return {"answer": response["answer"], "source_documents": source_documents}