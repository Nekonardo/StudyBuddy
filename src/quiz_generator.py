import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / "config" / ".env")

def generate_quiz(chunk: str, api_key: str = None) -> dict:
    """
    Generates technical questions with bulletproof JSON formatting
    Returns format: {questions: [{question, options, answer, explanation, topic}]}
    """
    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    system_prompt = """You are an expert academic quiz generator. Follow these rules:
    1. Format ALL text elements using LaTeX with $...$ wrappers
    2. Escape ALL quotes and special characters with double backslashes
    3. Use DOUBLE curly braces for JSON templates
    4. Never include markdown formatting
    5. Ensure proper JSON syntax with balanced brackets and quotes"""

    user_prompt = f"""
    Generate 5 questions from this content. Use EXACT format:
    
    {{
        "questions": [
            {{
                "question": "$\\text{{Example question}}$",
                "options": ["$\\mathrm{{Option 1}}$", "$\\mathrm{{Option 2}}$"],
                "answer": "$\\mathrm{{Option 1}}$",
                "explanation": "$\\text{{Example explanation}}$",
                "topic": "Subject"
            }}
        ]
    }}
    
    === CONTENT ===
    {chunk[:3000]}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1500
        )
        
        # Debugging: Print raw response
        raw_response = response.choices[0].message.content
        print("Raw API Response:", raw_response)
        
        return _validate_quiz(json.loads(raw_response))
    
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON format: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"API Error: {str(e)}")

def _validate_quiz(quiz_data: dict) -> dict:
    """Validate and sanitize quiz data"""
    required = {"question", "options", "answer", "explanation", "topic"}
    
    for q in quiz_data.get("questions", []):
        if missing := required - set(q.keys()):
            raise ValueError(f"Missing fields: {missing}")
            
        # Sanitize string fields
        for field in ["question", "answer", "explanation", "topic"]:
            if isinstance(q[field], str):
                q[field] = q[field].replace('"', '\\"').strip('"')
                
        # Sanitize options list
        if isinstance(q["options"], list):
            q["options"] = [
                opt.replace('"', '\\"').strip('"') 
                for opt in q["options"]
                if isinstance(opt, str)
            ]
            
        # Validate answer exists
        if q["answer"] not in q["options"]:
            raise ValueError("Correct answer missing from options")
            
    return quiz_data