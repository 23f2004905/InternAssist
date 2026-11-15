from google import genai
from dotenv import load_dotenv
import os
import time

load_dotenv()

class AIConfigurationError(RuntimeError):
    pass


class AIUpstreamError(RuntimeError):
    pass


def ask_gemini(context, question, history=None):

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise AIConfigurationError("The AI answer service is not configured.")

    client = genai.Client(api_key=api_key)

    context = context[:12000]

    history_text = "\n".join(
        f"{message['role'].capitalize()}: {message['content']}"
        for message in (history or [])[-12:]
    )

    prompt = f"""
You are InternAssist, an AI assistant for an internship placement platform.

Answer ONLY using the context below.
If the answer isn't in the context, say you don't have enough information.

Context:
{context}

Previous conversation:
{history_text or "(none)"}

Question:
{question}
"""

    for i in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )

            answer = (response.text or "").strip()
            if not answer:
                raise RuntimeError("The AI service returned an empty response.")
            return answer

        except Exception as e:
            print("Gemini attempt", i + 1, "failed:", e)

            if i < 2:
                time.sleep(2 * (i + 1))

    raise AIUpstreamError("The AI answer service is temporarily unavailable. Please try again.")
