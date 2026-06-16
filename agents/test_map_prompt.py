import os
import json
from dotenv import load_dotenv
from groq import Groq
from prompts import MAP_EXTRACTION_PROMPT

load_dotenv("agents/.env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

sample_circular_text = """
RBI Circular: Customer Due Diligence and KYC Update Requirements.
Banks shall ensure that all customer KYC records are updated within 30 days from the date of this circular.
Banks must maintain documentary evidence of KYC update completion and submit compliance confirmation
to the Compliance Department. Failure to comply may attract supervisory action under applicable RBI guidelines.
"""

response = client.chat.completions.create(
    model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    messages=[
        {"role": "system", "content": MAP_EXTRACTION_PROMPT},
        {"role": "user", "content": sample_circular_text}
    ],
    temperature=0
)

content = response.choices[0].message.content.strip()

print("Raw response:")
print(content)

print("\nJSON check:")
try:
    parsed = json.loads(content)
    print(json.dumps(parsed, indent=2))
    print("\nMAP extraction prompt is working ✅")
except json.JSONDecodeError as e:
    print("Invalid JSON ❌")
    print(e)