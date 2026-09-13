import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

AION_API_KEY = os.getenv("AION_API_KEY")
AION_BASE_URL = os.getenv("AION_BASE_URL", "https://api.aionlabs.ai/v1")
AION_MODEL_NAME = os.getenv("AION_MODEL_NAME", "your-model-name")  # e.g., "aion-7b-chat"

if not AION_API_KEY:
    raise ValueError("AION_API_KEY not found in .env")

_llm_instance = None

def get_llm() -> ChatOpenAI:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=AION_MODEL_NAME,
            api_key=AION_API_KEY,
            base_url=AION_BASE_URL,
            temperature=0.3,
            max_tokens=512,
        )
    return _llm_instance

if __name__ == "__main__":
    llm = get_llm()
    response = llm.invoke("Say hello in one short sentence.")
    print(response.content)