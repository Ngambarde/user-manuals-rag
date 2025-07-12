# This project is currently under developement, but please feel free to take a look!
## Some features may not work optimally and will be improved

# Equipment RAG Project

This project is a Retrieval-Augmented Generation (RAG) system to assist in troubleshooting, setup, and information retrieval for equipment based on user manuals and work instructions.

## Setup

1.  Place all your PDF user manuals into the `documents` directory.
2.  Create a `.env` file in the root of the project and add your OpenAI API key:
    ```
    OPENAI_API_KEY="your_api_key_here"
    ```
3.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

To ingest documents, execute the document ingestion script:

```bash
python src/ingest.py
```

To query the model, modify the `my_query` field and execute the query script:

```bash
python src/query.py
```
