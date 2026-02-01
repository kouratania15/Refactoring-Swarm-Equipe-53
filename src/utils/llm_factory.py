
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

def get_llm(model_name: str = "gemini-2.5-flash", temperature: float = 0):
    """
    Returns a configured ChatGoogleGenerativeAI instance.
    
    Args:
        model_name: Name of the Gemini model (default: gemini-1.5-flash)
        temperature: Creativity of the model (0 = deterministic)
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file.")
        
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
        convert_system_message_to_human=True # Sometimes needed for older LangChain versions or specific models
    )
    return llm
