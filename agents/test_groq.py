import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv("agents/.env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

paragraph = """
The Reserve Bank of India has directed banks to ensure that all customer KYC records
are updated within the prescribed timeline. Non-compliance may attract supervisory action.
"""

response = client.chat.completions.create(
    model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    messages=[
        {"role": "system", "content": "You are a banking compliance assistant."},
        {"role": "user", "content": f"Extract the compliance obligation from this RBI circular:\n\n{paragraph}"}
    ],
)

print(response.choices[0].message.content)