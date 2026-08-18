import json
from typing import Dict, Any
import ollama


class FormQAAgent:
    def __init__(self, model_name: str = "llama3.1"):
        self.model_name = model_name

    def answer_question(self, question: str, profile: Dict[str, Any], job: Dict[str, Any]) -> str:
        job_title = job.get("title", "")
        company = job.get("company", "")

        prompt = f"""You are answering an application form question for candidate {profile.get('personal', {}).get('full_name')}.

TARGET ROLE: {job_title} at {company}
QUESTION: "{question}"

CANDIDATE DATA:
{json.dumps(profile, indent=2)}

RULES:
1. Provide a professional, factual response in 2-3 sentences.
2. Use ONLY facts present in the candidate profile.
3. For authorization: State the candidate is authorized to work without sponsorship where applicable based on profile.
4. Output raw answer text only. No greetings, quotes, or conversational meta-text.
"""
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.15, "num_predict": 250}
            )
            return response["message"]["content"].strip()
        except Exception as e:
            print(f"[FormQAAgent] Fallback: {e}")
            return "Available upon request."