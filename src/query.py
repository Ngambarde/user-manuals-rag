from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

DB_FAISS_PATH = "vector_store/"


def run_query(query):
    embeddings = OpenAIEmbeddings()
    db = FAISS.load_local(
        DB_FAISS_PATH, embeddings, allow_dangerous_deserialization=True
    )

    llm = ChatOpenAI(model="gpt-4.1-nano-2025-04-14")
    print(f"LLM loaded: {llm}")

    retriever = db.as_retriever(search_kwargs={"k": 2})

    prompt = ChatPromptTemplate.from_template(
        """Answer the following question based only on the provided context:

        <context>
        {context}
        </context>
        Question: {input}"""
    )

    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    response = retrieval_chain.invoke({"input": query})

    print("---Answer---")
    print(response["answer"])
    print("\n --- Source Documents ---")

    for doc in response["context"]:
        print(
            f"source: {doc.metadata.get('source', 'N/A')}, Page: {doc.metadata.get('page', 'N/A')}"
        )


if __name__ == "__main__":
    load_dotenv()
    my_query = "How can I determine the firmware version of the v243?"
    print(f"Running query: {my_query}")
    run_query(my_query)
