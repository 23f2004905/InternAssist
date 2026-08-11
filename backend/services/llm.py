from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def ask_gemini(context, question):
    prompt = f"""
You are InternAssist, an AI assistant for an internship placement platform.

Answer ONLY using the context below. If the answer isn't in the context, say you don't have enough information.

Context:
{context}

Question:
{question}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt
    )

    return response.text