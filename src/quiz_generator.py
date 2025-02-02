import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path


load_dotenv(dotenv_path=Path(__file__).parent.parent / "config" / ".env")

def generate_quiz(chunk: str, api_key: str = None) -> dict:
    """
    Generates technical questions relevant to ANY academic subject while 
    filtering out administrative/organizational questions with robust LaTeX handling
    Returns format: {questions: [{question, options, answer, explanation, topic}]}
    """

    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    system_prompt = """You are an expert quiz generator specializing in academic content.
    Rules:
    1. Focus ONLY on technical/scientific concepts from the provided text
    2. NEVER create questions about schedules, logistics, or course administration
    3. Adapt to the subject matter (biology, CS, physics, etc.)
    4. For mathematical expressions, ALWAYS wrap them in LaTeX math delimiters and use double braces:
       - Use `$...$` for inline math: $\\frac{{1}}{{2}}$
       - Use `$$...$$` for displayed equations
    5. Include fundamental concepts and key terminology
    6. For LaTeX formatting:
       - Powers: Use ^ (e.g., $x^{{2}}$)
       - Subscripts: Use _ (e.g., $x_{{1}}$)
       - Fractions: $\\frac{{numerator}}{{denominator}}$
       - Derivatives: $\\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$
       - Integrals: $\\int_{{a}}^{{b}} f(x)dx = F(b) - F(a)$
       - Limits: $\\lim_{{h \\to 0}} \\frac{{f(x + h) - f(x)}}{{h}}$
       - Greek letters: $\\alpha$, $\\beta$
       - Special functions: $\\sin$, $\\cos$, $\\log$
    Return your response in JSON format. Include the word 'json' in your response.
    """

    user_prompt = f"""
    Generate 5 quiz questions from this text:
    
    === TEXT TO PROCESS ===
    {chunk[:3000]}
    
    Format each question as:
    {{
        "questions": [
            {{
                "question": "Question text with LaTeX notation",
                "options": [
                    "$\\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$",
                    "Other options..."
                ],
                "answer": "Correct answer",
                "explanation": "Explanation",
                "topic": "Specific subfield"
            }}
        ]
    }}

    IMPORTANT: 
    1. Always wrap mathematical expressions in $ or $$ delimiters!
    2. Always use double backslash (\\\\) for LaTeX commands!
    3. Always use double braces {{}} for LaTeX arguments!
    
    Examples of proper LaTeX formatting:
    - Fractions: $\\frac{{1}}{{2}}$
    - Derivatives: $\\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$
    - Integrals: $\\int_{{a}}^{{b}} f(x)dx = F(b) - F(a)$
    - Limits: $\\lim_{{h \\to 0}} \\frac{{f(x + h) - f(x)}}{{h}}$
    - Summations: $\\sum_{{i=1}}^{{n}} i^{{2}}$
    - Matrices: $\\begin{{bmatrix}} a & b \\\\ c & d \\end{{bmatrix}}$
    - Greek letters: $\\alpha$, $\\beta$, $\\gamma$
    - Functions: $\\sin(x)$, $\\cos(x)$, $\\log(x)$
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        quiz_data = json.loads(response.choices[0].message.content)
        return quiz_data
    except Exception as e:
        print(f"Error generating quiz: {str(e)}")
        raise