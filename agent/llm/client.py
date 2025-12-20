# this file creates an ollama connection
import os
from langchain_ollama import ChatOllama

def get_llm():
    """
    Initialises the Ollama Chat Model
    Ensure ollama serve is running and the model is pulled:
    $ ollama pull qwen2.5:7b
    """

    model_name = os.getenv("LLM_MODEL", "qwen2.5:7b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    print(f"Initialising LLM: {model_name} at {base_url}")

    return ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0,
        format="json"
    )