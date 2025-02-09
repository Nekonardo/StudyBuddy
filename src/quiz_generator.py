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
    model="gpt-4-turbo"

    # Groq model
    # client = OpenAI(
    # api_key=api_key or os.getenv("GROQ_API_KEY"),
    # base_url="https://api.groq.com/openai/v1"  
    # )
    # model="deepseek-r1-distill-llama-70b"
    # model="llama3-70b-8192"
    # model="deepseek-r1-distill-llama-70b"
    # model="llama3-70b-8192"

    # original system prompt
    system_prompt = f"""You are an expert quiz generator specializing in academic content.
    Rules:
    1. Focus ONLY on technical/scientific concepts from the provided text. 
    2. NEVER create questions about schedules, logistics, or course administration, grade bonus, management, etc.
    3. Adapt to the subject matter (biology, CS, physics, etc.), focus on content which is important for the student to learn. Focus on the theoretical concepts.
    4. For mathematical expressions, ALWAYS wrap them in LaTeX math delimiters and use double braces:
       - Use `$...$` for inline math: $\\\\frac{{1}}{{2}}$
       - Use `$...$` for displayed equations
       - Use `$...$` for mathematical variables such as f,x and any other mathematical expressions 
    5. Include fundamental concepts and key terminology
    6. For LaTeX formatting:
       - Powers: Use ^ (e.g., $x^{{2}}$)
       - Subscripts: Use _ (e.g., $x_{{1}}$)
       - Fractions: $\\\\frac{{numerator}}{{denominator}}$
       - Derivatives: $\\\\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$
       - Integrals: $\\\\int_{{a}}^{{b}} f(x)dx = F(b) - F(a)$
       - Limits: $\\\\lim_{{h \\to 0}} \\\\frac{{f(x + h) - f(x)}}{{h}}$
       - Greek letters: $\\\\alpha$, $\\\\beta$
       - Special functions: $\\\\sin$, $\\\\cos$, $\\\\log$
    7. Common commands needing double backslash:
        - $\\\\text{{x}}$
        - $\\\\to$
        - $\\\\triangle$
        - $\\\\sum$
        - $\\\\int$
    8. Every $ must have a corresponding $ 
    9. When using $\\\text{...}$, make sure to use $...$
    
    VALIDATION STEPS:
        1. Did you use double backslash (\\\\) for EVERY LaTeX command?
        2. Did you use four braces {{{{}}}} for EVERY argument?
        3. Did you properly wrap all math in $ or $$?
        4. Did you check \\\\frac, \\\\sin, \\\\cos, \\\\log, \\\\int, \\\\lim, \\\\sum, \\\\begin, \\\\end, \\\\alpha, \\\\beta, \\\\gamma, \\\\sin(x), \\\\cos(x), \\\\log(x)?
        5. Did you check mathematical expressions, formulas, and equations are wrapped in $  and begin and end with $ ?
        6. Did you check that every $ has a corresponding $?
    Return your response in JSON format. Include the word 'json' in your response.
    """

    # system_prompt = f'''You are an expert quiz generator specializing in academic content. You must follow these strict rules for LaTeX formatting in JSON:

    # CONTENT RULES:
    # 1. Focus ONLY on technical/scientific concepts from the provided text
    # 2. NEVER create questions about schedules, logistics, or course administration
    # 3. Adapt to the subject matter (biology, CS, physics, etc.)
    # 4. For mathematical expressions, ALWAYS wrap them in LaTeX math delimiters and use double braces:
    #    - Use `$...$` for inline math: $\\frac{{1}}{{2}}$
    #    - Use `$$...$$` for displayed equations
    # 5. Include fundamental concepts and key terminology

    # CRITICAL LATEX FORMATTING RULES:
    # 1. ALL LaTeX commands must use TWO backslashes (\\) when in JSON, not one
    # 2. ALL arguments must use double braces {{{{}}}}
    # 3. ALL math must be in delimiters ($ or $$)

    # CORRECT Examples (for JSON output):
    # - Fractions: $\\frac{{{{num}}}}{{{{den}}}}$
    # - Derivatives: $\\frac{{{{d}}}}{{{{dx}}}}$
    # - Text in math: $\\text{{{{word}}}}$
    # - Limits: $\\lim_{{{{x \\to 0}}}}$
    # - Special functions: $\\sin(x)$, $\\cos(x)$
    # - Matrices: $\\begin{{{{bmatrix}}}} 1 & 2 & 3 \\ 4 & 5 & 6 \\ 7 & 8 & 9 \\end{{{{bmatrix}}}}$

    # COMMON ERRORS TO AVOID:
    # × $\\frac{{x}}{{y}}$     → ✓ $\\frac{{{{x}}}}{{{{y}}}}$
    # × $\\text{{x}}$          → ✓ $\\text{{{{x}}}}$
    # × $\\forall{{x}}$        → ✓ $\\forall{{{{x}}}}$

    # VALIDATION STEPS:
    # 1. Did you use double backslash (\\) for EVERY LaTeX command?
    # 2. Did you use four braces {{{{}}}} for EVERY argument?
    # 3. Did you properly wrap all math in $ or $$?
    
    # Return your response in JSON format. Include the word 'json' in your response.
    # '''

    # system_prompt = f'''
    # You are an expert quiz generator specializing in academic content.
    # Rules:
    # 1. Focus ONLY on technical/scientific concepts from the provided text
    # 2. NEVER create questions about schedules, logistics, or course administration
    # 3. Adapt to the subject matter (biology, CS, physics, etc.)
    # 4. For mathematical expressions, ALWAYS wrap them in LaTeX math delimiters and use double braces:
    #    - Use `$...$` for inline math: $\frac{{1}}{{2}}$
    #    - Use `$$...$$` for displayed equations
    # 5. Include fundamental concepts and key terminology
    # 6. For LaTeX formatting:
    #    - Powers: Use ^ (e.g., $x^{{2}}$)
    #    - Subscripts: Use _ (e.g., $x_{{1}}$)
    #    - Fractions: $\frac{{numerator}}{{denominator}}$
    #    - Derivatives: $\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$
    #    - Integrals: $\int_{{a}}^{{b}} f(x)dx = F(b) - F(a)$
    #    - Limits: $\lim_{{h \to 0}} \frac{{f(x + h) - f(x)}}{{h}}$
    #    - Greek letters: $\alpha$, $\beta$
    #    - Special functions: $\sin$, $\cos$, $\log$
    # Return your response in JSON format. Include the word 'json' in your response.
    # '''

    # original prompt
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
                    "$\\\\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$",
                    "Other options..."
                ],
                "answer": "Correct answer",
                "explanation": "Explanation",
                "topic": "Specific subfield"
            }}
        ]
    }}

    IMPORTANT: 
    1. Always wrap mathematical expressions, formulas, and equations in $ or $$ delimiters!
    2. Always use double backslash (\\\\) for LaTeX commands!
    3. Always use double braces {{}} for LaTeX arguments!

    
    Examples of proper LaTeX formatting:
    - Fractions: $\\\\frac{{1}}{{2}}$
    - Derivatives: $\\\\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$
    - Integrals: $\\\\int_{{a}}^{{b}} f(x)dx = F(b) - F(a)$
    - Limits: $\\\\\lim_{{h \\to 0}} \\\\frac{{f(x + h) - f(x)}}{{h}}$
    - Summations: $\\\\sum_{{i=1}}^{{n}} i^{{2}}$
    - Matrices: $\\\\begin{{bmatrix}} a & b \\\\\\\\ c & d \\\\\\\\end{{bmatrix}}$
    - Greek letters: $\\\\alpha$, $\\\\beta$, $\\\\gamma$
    - Functions: $\\\\sin(x)$, $\\\\cos(x)$, $\\\\log(x)$

    Validation steps:
    1. Did you use double backslash (\\\\) for EVERY LaTeX command?
    2. Did you use four braces {{{{}}}} for EVERY argument?
    3. Did you properly wrap all math in $ or $$?
    4. Did you check \\\\frac, \\\\sin, \\\\cos, \\\\log, \\\\int, \\\\lim, \\\\sum, \\\\begin, \\\\end, \\\\alpha, \\\\beta, \\\\gamma, \\\\sin(x), \\\\cos(x), \\\\log(x)?
    5. Did you check mathematical expressions, formulas, and equations are wrapped in $ or $$, and begin and end with $ or $$?
    """


    # user_prompt = f"""
    # Generate 5 quiz questions from this text:
    
    # === TEXT TO PROCESS ===
    # {chunk[:3000]}
    
    # Format each question as:
    # {{
    #     "questions": [
    #         {{
    #             "question": "Question text with LaTeX notation",
    #             "options": [
    #                 "$\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$",
    #                 "Other options..."
    #             ],
    #             "answer": "Correct answer",
    #             "explanation": "Explanation",
    #             "topic": "Specific subfield"
    #         }}
    #     ]
    # }}

    # IMPORTANT: 
    # 1. Always wrap mathematical expressions in $ or $$ delimiters!
    # 2. Always use backslash (\) for LaTeX commands!
    # 3. Always use braces {{}} for LaTeX arguments!
    
    # Examples of proper LaTeX formatting:
    # - Fractions: $\frac{{1}}{{2}}$
    # - Derivatives: $\frac{{d}}{{dx}}(x^{{n}}) = nx^{{n-1}}$
    # - Integrals: $\int_{{a}}^{{b}} f(x)dx = F(b) - F(a)$
    # - Limits: $\lim_{{h \\to 0}} \\frac{{f(x + h) - f(x)}}{{h}}$
    # - Summations: $\sum_{{i=1}}^{{n}} i^{{2}}$
    # - Matrices: $\begin{{bmatrix}} a & b \\ c & d \\end{{bmatrix}}$
    # - Greek letters: $\alpha$, $\beta$, $\gamma$
    # - Functions: $\sin(x)$, $\cos(x)$, $\log(x)$
    # """


    try:
        response = client.chat.completions.create(
            model=model,
            # model=model,
            # model="gpt-4-turbo",
            # model="deepseek-r1-distill-llama-70b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
       
            temperature=0.4
        )

        quiz_data = json.loads(response.choices[0].message.content)
        return quiz_data
    except Exception as e:
        print(f"Error generating quiz: {str(e)}")
        raise