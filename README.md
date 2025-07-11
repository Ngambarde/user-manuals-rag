# Company RAG Project

This project is a Retrieval-Augmented Generation (RAG) system to assist in troubleshooting, setup, and information retrieval for our current equipment

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

To run the application, execute the main script:

```bash
python src/main.py
``` 