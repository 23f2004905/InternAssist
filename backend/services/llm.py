from google import genai
from dotenv import load_dotenv
import os
import time

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def ask_gemini(context, question):

    context = context[:12000]

    prompt = f"""
You are InternAssist, an AI assistant for an internship placement platform.

Answer ONLY using the context below.
If the answer isn't in the context, say you don't have enough information.

Context:
{context}

Question:
{question}
"""

    for i in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )

            return response.text

        except Exception as e:
            print("Gemini attempt", i + 1, "failed:", e)

            if i < 2:
                time.sleep(2 * (i + 1))

    return "Gemini is temporarily unavailable. Please try again."