import re
import streamlit as st
import plotly.express as px
import os
from ingestion import LectureNotesIngester, LectureDB
from quiz_generator import generate_quiz
from database import init_db, log_quiz_result, get_student_progress, get_weak_topics
import pandas as pd
import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
import json
import uuid
from datetime import datetime
import time
from langchain_openai import ChatOpenAI  # Update import
from openai import OpenAI  
from pathlib import Path
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
import html

from rag import RAG





st.set_page_config(
    page_title="StudyBuddy",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)
from sklearn.feature_extraction.text import TfidfVectorizer
from ingestion import TagDB
import io
import zipfile
import json
from functools import lru_cache



# Add this near the top of the file, after st.set_page_config
st.markdown("""
<script type="text/javascript" async
    src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML">
</script>
<script type="text/x-mathjax-config">
    MathJax.Hub.Config({
        tex2jax: {
            inlineMath: [['$','$'], ['\\(','\\)']],
            displayMath: [['$$','$$'], ['\\[','\\]']],
            processEscapes: true,
            processEnvironments: true
        },
        displayAlign: 'center'
    });
</script>
""", unsafe_allow_html=True)


def get_key_chunks(chunks):
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform(chunks)
    scores = tfidf.sum(axis=1).A1
    
    return [chunks[i] for i in scores.argsort()[-5:]]


init_db()
tag_db = TagDB()
lecture_db = LectureDB()

st.title("StudyBuddy 🧠")

# ===== Sidebar =====
st.sidebar.header("Quick Access")

# Version-aware lecture loader
@st.cache_data(show_spinner=False, ttl=60)
def load_sidebar_lectures(_lecture_db, cache_version):
    try:
        lectures = _lecture_db.get_all_lectures()
        if not lectures:
            st.warning("No lectures found in database")
            return []
        return lectures
    except Exception as e:
        st.error(f"Error loading lectures: {str(e)}")
        return []

if 'lecture_cache_version' not in st.session_state:
    st.session_state.lecture_cache_version = 0

# Get lectures with cache versioning
selected_lecture = None

try:
    sidebar_lectures = load_sidebar_lectures(
        lecture_db, 
        st.session_state.lecture_cache_version
    )
    
    if sidebar_lectures:
        selected_lecture = st.sidebar.selectbox(
            "📚 Select Note for Quiz:",
            options=sidebar_lectures,
            format_func=lambda x: f"{x['title']} ({len(x['chunks'])} chunks)",
            index=0 if sidebar_lectures else None,
            help="Choose a note to start a quiz"
        )
    else:
        st.sidebar.warning("No notes available. Please upload some lecture notes first.")
except Exception as e:
    st.sidebar.error(f"Error loading lectures: {str(e)}")

#
if st.sidebar.button("🔄 Refresh note list"):
    st.session_state.lecture_cache_version += 1
    st.rerun()
with st.sidebar:
    st.divider()
    # Store previous chat mode in session state if not exists
    if 'previous_chat_mode' not in st.session_state:
        st.session_state.previous_chat_mode = "General Chat"
    
    chat_mode = "General Chat"

    if selected_lecture:
        chat_mode = st.radio(
            "Chat Mode",
            ["General Chat", f"Chat with PDF: {selected_lecture['title']}"],
            index=1
        )
    SYSTEM_MESSAGE1 ="""
You are an AI teaching assistant specializing in STEM subjects, with expertise in using Mermaid diagrams to explain concepts and answer questions. Your goal is to provide clear, comprehensive, and visually-aided explanations to user queries. Follow these instructions carefully:

1. Analyze the following user question

2. Determine if the question is suitable for explanation using a Mermaid diagram. Consider using diagrams for processes, hierarchies, timelines, relationships,mind maps, or other structured information. Diagrams are should be used when it is suitable and helpful for the user to understand the question.

3. If a diagram is appropriate:
    a. Choose the most suitable Mermaid diagram type (e.g., Flowchart, Sequence Diagram, Class Diagram, etc.).
    b. Write the Mermaid diagram code using correct syntax. Enclose the code in mermaid and tags.
    c. Ensure the diagram is clear, concise, and not overcomplicated.
    d. When generating Class Diagrams (classDiagram), follow these best practices to ensure correct rendering:
    - Avoid using + - # access modifiers; define attributes and methods without prefixes.
    - Always use the class keyword to explicitly declare classes.
    - Use <|-- for class inheritance and <|.. for interface implementation, and do not mix them incorrectly.
    - Ensure interface is used only for defining interfaces, not regular classes.
    - Keep relationships simple and structured, avoiding excessive arrow types or complex hierarchies.
    - Avoid mathematical operators (`x`, `+`, `-`, `/`, `*`) directly appearing in node names, otherwise Mermaid parsing will throw an error. Use `_` or `-` instead of operators, such as `Current_x_Resistance` or `Current-Times-Resistance`.


4. Provide a textual explanation before the diagram, introducing the concept and why a diagram is helpful.

5. After the diagram, explain its key points and how it relates to the question.

6. For complex questions, consider using multiple diagrams to explain different aspects. Introduce each diagram separately.

7. If the question is not suitable for a diagram, provide a clear textual explanation without forcing diagram use.

8. When explaining STEM concepts:
   a. Use simple terms and concrete examples.
   b. Provide step-by-step guidance for problem-solving.
   c. Use analogies to clarify misunderstandings.
   d. Suggest relevant study strategies and practice exercises.

9. Use LaTeX for mathematical equations. Enclose equations in single dollar signs for inline equations (e.g., $E=mc^2$) and double dollar signs for display equations (e.g., $$F = G\frac{m_1m_2}{r^2}$$).

10. Use code blocks for programming concepts. Enclose code in triple backticks with the language specified (e.g., ```python).



12. Structure your response as follows:

    [Introduction and context]
    [Diagram(s) with explanations (if applicable)]
    [Detailed explanation of concepts]
    [Problem-solving steps or examples (if relevant)]
    [Suggested study strategies or exercises]
    [Conclusion or summary]

Remember, your primary goal is to enhance understanding through clear explanations and visual aids when appropriate.

"""

    SYSTEM_MESSAGE2 ="""
You are an AI teaching assistant specializing in STEM subjects, with expertise in using Mermaid diagrams to explain concepts and answer questions. Your goal is to provide clear, comprehensive, and visually-aided explanations to user queries. Follow these instructions carefully:

1. Analyze the following user question

2. Determine if the question is suitable for explanation using a Mermaid diagram. Consider using diagrams for processes, hierarchies, timelines, relationships,mind maps, or other structured information. Diagrams are should be used when it is suitable and helpful for the user to understand the question.

3. If a diagram is appropriate:
    a. Choose the most suitable Mermaid diagram type (e.g., Flowchart, Sequence Diagram, Class Diagram, etc.).
    b. Write the Mermaid diagram code using correct syntax. Enclose the code in mermaid and tags.
    c. Ensure the diagram is clear, concise, and not overcomplicated.
    d. When generating Class Diagrams (classDiagram), follow these best practices to ensure correct rendering:
    - Avoid using + - # access modifiers; define attributes and methods without prefixes.
    - Always use the class keyword to explicitly declare classes.
    - Use <|-- for class inheritance and <|.. for interface implementation, and do not mix them incorrectly.
    - Ensure interface is used only for defining interfaces, not regular classes.
    - Keep relationships simple and structured, avoiding excessive arrow types or complex hierarchies.
    - Avoid mathematical operators (`x`, `+`, `-`, `/`, `*`) directly appearing in node names, otherwise Mermaid parsing will throw an error. Use `_` or `-` instead of operators, such as `Current_x_Resistance` or `Current-Times-Resistance`.


4. Provide a textual explanation before the diagram, introducing the concept and why a diagram is helpful.

5. After the diagram, explain its key points and how it relates to the question.

6. For complex questions, consider using multiple diagrams to explain different aspects. Introduce each diagram separately.

7. If the question is not suitable for a diagram, provide a clear textual explanation without forcing diagram use.

8. When explaining STEM concepts:
   a. Use simple terms and concrete examples.
   b. Provide step-by-step guidance for problem-solving.
   c. Use analogies to clarify misunderstandings.
   d. Suggest relevant study strategies and practice exercises.

9. Use LaTeX for mathematical equations. Enclose equations in single dollar signs for inline equations (e.g., $E=mc^2$) and double dollar signs for display equations (e.g., $$F = G\frac{m_1m_2}{r^2}$$).

10. Use code blocks for programming concepts. Enclose code in triple backticks with the language specified (e.g., ```python).

11. Focus strictly on academic topics and avoid non-educational content. 

12. Structure your response as follows:

    [Introduction and context]
    [Diagram(s) with explanations (if applicable)]
    [Detailed explanation of concepts]
    [Problem-solving steps or examples (if relevant)]
    [Suggested study strategies or exercises]
    [Conclusion or summary]

13. When answering questions:
    a. First check if the question is related to the lecture notes provided
    b. If related, provide answers using only information from those lecture notes
    c. If unrelated, politely explain that you can only answer questions about the available lecture content. Explicitly mention that the user should only ask questions about the lecture notes provided.
    d. Suggest relevant sections from the lecture notes that may help address their question
    e. Maintain focus on the lecture material to ensure accurate and consistent responses

Remember, your primary goal is to enhance understanding through clear explanations and visual aids when appropriate.

"""
    # Reset messages when chat mode changes
    # if chat_mode != st.session_state.previous_chat_mode:
    #     st.session_state.messages = [
    #         {
    #             "role": "system", 
    #             "content": SYSTEM_MESSAGE2 if chat_mode.startswith("Chat with PDF:") else SYSTEM_MESSAGE1
    #         },
    #         {
    #             "role": "assistant", 
    #             "content": "Welcome to your AI-powered study session! 📚 How can I help you with your learning today?"
    #         }
    #     ]
    #     st.session_state.previous_chat_mode = chat_mode
    # Only update system message when chat mode changes
    if chat_mode != st.session_state.previous_chat_mode and "messages" in st.session_state:
        new_system_message = SYSTEM_MESSAGE2 if chat_mode.startswith("Chat with PDF:") else SYSTEM_MESSAGE1
        # Update only the system message (first message)
        st.session_state.messages[0] = {
            "role": "system",
            "content": new_system_message
        }
        st.session_state.previous_chat_mode = chat_mode
    st.divider()
    openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
    model = st.selectbox(
        "Select OpenAI Model",
        [     
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-0125-preview",  # GPT-4 Turbo
            "gpt-4-turbo",
            "gpt-4",               # GPT-4
            "gpt-3.5-turbo-0125",  # GPT-3.5 Turbo
            "gpt-3.5-turbo",       # GPT-3.5 Turbo
        ],
        index=0,
        help="Choose the OpenAI model to use for chat responses"
    )
    "[Get an OpenAI API key](https://platform.openai.com/account/api-keys)"
    "[View the source code](https://github.com/)"
    "[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nekonardo-studybuddy-srcapp-fjgveg.streamlit.app/)"
    
client = ChatOpenAI(
    api_key=openai_api_key,
    model_name=model,
    temperature=0.3
)
# client = ChatOpenAI(
#     api_key= os.getenv("GROQ_API_KEY"),
#     model_name='deepseek-r1-distill-llama-70b',
#     base_url="https://api.groq.com/openai/v1",
#     temperature=0.3
# )

# Modify the cache function to include the title as a parameter.
@st.cache_data(ttl=3600)
def get_cached_quiz(chunk, lecture_id, title):
    return generate_quiz(chunk)

def main():

    if 'quiz' not in st.session_state:
        st.session_state.quiz = None
    if 'user_answers' not in st.session_state:
        st.session_state.user_answers = {}
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'current_lecture_id' not in st.session_state:
        st.session_state.current_lecture_id = None



# ===== Main Content =====
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Upload Notes", "Take Quiz", "Progress Dashboard", "Manage Notes", "Buddy Chat"])

# Tab 1: Upload Notes
with tab1:
    st.header("📂 Upload & Organize Your Study Materials")
    uploaded_file = st.file_uploader("Upload PDF/DOCX/TXT", type=["pdf", "docx", "txt"])
    if uploaded_file:
        title = st.text_input("Lecture Title", "My Lecture Notes")
        
        # Initialize tags from persistent storage
        if 'available_tags' not in st.session_state:
            st.session_state.available_tags = tag_db.load_tags()
        
        # Tag management UI
        col1, col2 = st.columns(2)
        with col1:
            new_tag = st.text_input("Create New Tag", help="Enter a new tag and click Add")
            if st.button("➕ Add Tag"):
                if new_tag and (clean_tag := new_tag.strip()) and clean_tag not in st.session_state.available_tags:
                    st.session_state.available_tags.append(clean_tag)
                    tag_db.save_tags(st.session_state.available_tags)  # Save to file
        
        with col2:
            if st.session_state.available_tags:
                tag_to_remove = st.selectbox(
                    "Select Tag to Remove",
                    st.session_state.available_tags,
                    help="Select tag to remove from available options"
                )
                if st.button("🗑️ Remove Tag"):
                    st.session_state.available_tags.remove(tag_to_remove)
                    tag_db.save_tags(st.session_state.available_tags)  # Save to file
        
        # Tag selection
        tags = st.multiselect(
            "Select Tags",
            st.session_state.available_tags,
            help="Select or create tags for this lecture"
        )
        
        # Process and save
        if st.button("Process and Save"):
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            try:
                # Initialize RAG with the API key
                rag = RAG(openai_api_key=os.getenv("OPENAI_API_KEY") or openai_api_key)
                chunks = rag.ingest(temp_path)
                
                vector_store_path = os.path.join("data/vector_stores", f"{title}_{hash(uploaded_file.name)}")
                
                rag.save(vector_store_path)
                
                lecture_db.save_lecture(
                    title=title,
                    file_name=uploaded_file.name,
                    chunks=chunks,
                    tags=tags,
                    vector_store_path=vector_store_path  
                )
                
                st.session_state.lecture_cache_version += 1
                st.success("Lecture saved successfully!")
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"Error: {str(e)}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

# Tab 2: Take Quiz
with tab2:
    st.header("🎯 Test Your Knowledge & Improve")
    if selected_lecture:
        header_name = f"Selected Note: {selected_lecture['title']}"
        st.subheader(header_name)
        chunks = selected_lecture["chunks"]
        
        # Session state initialization
        if 'quiz' not in st.session_state:
            st.session_state.quiz = None
        if 'user_answers' not in st.session_state:
            st.session_state.user_answers = {}
        if 'submitted' not in st.session_state:  # New submission state
            st.session_state.submitted = False

        # Quiz generation
        if st.button("Generate New Quiz"):
            try:
                key_chunks = get_key_chunks(chunks)
                quiz_data = generate_quiz(
                    "\n".join(key_chunks),
                    api_key=st.session_state.get("chatbot_api_key")  
                )
                
                # Process LaTeX in quiz data
                # if isinstance(quiz_data, dict) and 'questions' in quiz_data:
                #     for question in quiz_data['questions']:
                #         # Fix LaTeX in question text
                #         if 'question' in question:
                #             question['question'] = question['question'].replace('rac{', '\\frac{').replace('imes{', '\\times{').replace('ext{', '\\text{')
                        
                #         # Fix LaTeX in options
                #         if 'options' in question:
                #             question['options'] = [
                #                 opt.replace('rac{', '\\frac{')
                #                 .replace('imes{', '\\times{')
                #                 .replace('ext{', '\\text{')
                #                 for opt in question['options']
                #             ]
                        
                #         # Fix LaTeX in explanation
                #         if 'explanation' in question:
                #             question['explanation'] = question['explanation'].replace('rac{', '\\frac{').replace('imes{', '\\times{').replace('ext{', '\\text{')
                
                if quiz_data:
                    st.session_state.quiz = quiz_data
                    st.session_state.user_answers = {}
                    st.session_state.submitted = False
                    st.rerun()
                else:
                    st.error("Invalid quiz format")
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state.quiz = None

        # Quiz display
        if st.session_state.quiz and 'questions' in st.session_state.quiz:
            st.subheader("Current Quiz")
            
            # Add MathJax configuration at the beginning of the quiz display section
            st.markdown("""
            <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
            <script type="text/javascript" id="MathJax-script" async
                src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js">
            </script>
            <script>
                window.MathJax = {
                    tex: {
                        inlineMath: [['$', '$'], ['\\(', '\\)']],
                        displayMath: [['$$', '$$'], ['\\[', '\\]']],
                        processEscapes: true,
                        processEnvironments: true
                    },
                    options: {
                        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
                    }
                };
            </script>
            """, unsafe_allow_html=True)

            for i, q in enumerate(st.session_state.quiz['questions']):
                with st.container():
                    # Question display - Simplified
                    st.markdown(f"**Q{i+1}:** {q.get('question', '')}")
                    
                    options = q.get('options', [])
                    current_answer = st.session_state.user_answers.get(i)
                    
                    # Generate unique key
                    unique_key = f"quiz_{selected_lecture['id']}_{i}"
                    
                    # Render plain text options
                    selected = st.radio(
                        label="Select answer:",
                        options=options,
                        index=options.index(current_answer) if current_answer in options else None,
                        key=unique_key,  # Unique key per lecture/question
                        format_func=lambda x: x  # Remove markdown formatting
                    )
                    # plain text options
                    # Display original string options for debugging
                    with st.expander("Show in LaTeX code"):
                        st.write("View the text and LaTeX source code:")
                        for opt in options:
                            st.text(opt)

                    st.session_state.user_answers[i] = selected
                    
                    if selected:
                        is_correct = selected == q['answer']
                        if st.session_state.submitted:
                            # Modify the quiz result display section
                            st.markdown(f"""
                            <style>
                                .math-content {{
                                    font-size: 1.1em;
                                    margin: 8px 0;
                                }}
                                .MathJax {{
                                    display: inline !important;
                                }}
                            </style>
                            <div style="padding:12px; border-radius:8px; 
                                        background: {'#e6f4ea' if is_correct else '#fce8e6'}"
                                        id="quiz-result-{i}">
                                <div style="color: {'#137333' if is_correct else '#a50e0e'}; 
                                        margin-bottom: 8px;" class="math-content">
                                    Your answer: {selected} {'✅' if is_correct else '❌'}
                                </div>
                                <div style="font-weight: bold; margin-bottom: 8px;" class="math-content">
                                    Correct answer: {q['answer']}
                                </div>
                                <div class="math-content">
                                    Explanation: {q.get('explanation', '')}
                                </div>
                            </div>

                            <script>
                                document.addEventListener('DOMContentLoaded', function() {{
                                    // Force MathJax to reprocess the entire quiz result container
                                    if (typeof MathJax !== 'undefined') {{
                                        MathJax.texReset();
                                        MathJax.typesetPromise([document.getElementById('quiz-result-{i}')])
                                            .catch((err) => console.log('MathJax error:', err));
                                    }}
                                }});
                            </script>
                            """, unsafe_allow_html=True)
                    st.divider()

            # Submission handling
            if st.button("Submit Quiz", type="primary"):
                if None in st.session_state.user_answers.values():
                    st.error("Please answer all questions!")
                else:
                    try:
                        log_quiz_result(
                            student_id=1,
                            questions=[
                                {**q, 'student_answer': st.session_state.user_answers[i]}
                                for i, q in enumerate(st.session_state.quiz['questions'])
                            ]
                        )
                        st.success("Quiz submitted successfully!")
                        st.session_state.submitted = True  # Add this line
                        st.rerun()
                    except Exception as e:
                        st.error(f"Submission error: {str(e)}")

            # Add retake button at the end of tab2
            if st.session_state.submitted:
                if st.button("🔄 Retake Quiz"):
                    st.session_state.submitted = False
                    st.session_state.user_answers = {}
                    st.rerun()
    else:
        st.info("Please complete the quiz to view the results.")
                    
                
    # Tab 3: Progress Dashboard
    with tab3:
        st.header("📊 Track Your Learning Progress")
        
        col1, col2 = st.columns([1, 5])
        # with col1:
        #     if st.button("Initialize Database"):
        #         try:
        #             base_dir = os.path.dirname(os.path.abspath(__file__))
        #             db_path = os.path.join(base_dir, "../data/lectures_db.json")
                    
        
        #             os.makedirs(os.path.dirname(db_path), exist_ok=True)
                    
        #             # create example lectures
        #             example_lectures = [
        #                 {
        #                     "id": str(uuid.uuid4()),
        #                     "title": "Biology 101",
        #                     "upload_date": datetime.now().strftime("%Y-%m-%d"),
        #                     "file_name": "Biology_101.pdf",
        #                     "chunks": [
        #                         "Biology 101: Cellular Respiration Key Concepts: Mitochondria, ATP, Glycolysis, Krebs Cycle, Electron Transport Chain\n\n" +
        #                         "1. Overview\nCellular respiration is the process by which cells convert glucose and oxygen into ATP (adenosine triphosphate), " +
        #                         "the cell's energy currency.\n\nEquation: C6H12O6 + 6O2 → 6CO2 + 6H2O + ATP",
                                
        #                         "2. Stages of Cellular Respiration\n" +
        #                         "a. Glycolysis\n• Occurs in the cytoplasm\n• Breaks 1 glucose molecule into 2 pyruvate molecules\n• Produces 2 ATP and 2 NADH\n\n" +
        #                         "b. Krebs Cycle\n• Takes place in mitochondrial matrix\n• Generates 2 ATP, 6 NADH, and 2 FADH2 per glucose"
        #                     ],
        #                     "tags": ["Biology", "Cellular Processes"]
        #                 },
        #                 {
        #                     "id": str(uuid.uuid4()),
        #                     "title": "Computer Science 101",
        #                     "upload_date": datetime.now().strftime("%Y-%m-%d"),
        #                     "file_name": "CS_101.pdf",
        #                     "chunks": [
        #                         "Introduction to Computer Science\n\n" +
        #                         "1. Basic Concepts\n• Algorithm: A step-by-step procedure for solving a problem\n" +
        #                         "• Program: Implementation of an algorithm in a programming language\n" +
        #                         "• Data Structure: A way of organizing data for efficient access and modification",
                                
        #                         "2. Programming Fundamentals\n" +
        #                         "• Variables and Data Types\n• Control Structures\n• Functions and Procedures\n" +
        #                         "• Object-Oriented Programming Concepts"
        #                     ],
        #                     "tags": ["Computer Science", "Programming"]
        #                 }
        #             ]
                    
                    
        #             with open(db_path, "w", encoding="utf-8") as f:
        #                 json.dump(example_lectures, f, ensure_ascii=False, indent=2)
                    
        #             st.session_state.lecture_cache_version += 1
        #             st.success("Database initialized successfully! 🎉")
        #             time.sleep(0.75)  
        #             st.rerun()
                    
        #         except Exception as e:
        #             st.error(f"Failed to initialize database: {str(e)}")

    

        progress_df = get_student_progress(1)
        weak_topics_df = get_weak_topics(1)
        
        if not progress_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Quizzes", len(progress_df))
            with col2:
                avg_score = progress_df['score'].mean().round(1)
                st.metric("Average Score", f"{avg_score}%")
            with col3:
                st.metric("Weak Topics", len(weak_topics_df))
            
            st.subheader("Accuracy Over Time")
            fig = px.line(progress_df, x='timestamp', y='score', markers=True)
            fig.update_layout(
                xaxis_title="Timestamp"
            )
            st.plotly_chart(fig)
            
            st.subheader("Weak Topics")
            if not weak_topics_df.empty:
                fig = px.bar(weak_topics_df, x='accuracy', y='topic', orientation='h')
                fig.update_layout(
                xaxis_title="Accuracy"
            )
                st.plotly_chart(fig)
            else:
                st.success("🎉 No weak topics identified!")
        else:
            st.info("📊 No quiz data available yet. Take some quizzes to see progress!")


#Tab 4: Lecture Management
with tab4:
    st.header("🗂 Organize & Access Your Notes Anytime")
    
    # Real-time sync controls
    # col1, col2 = st.columns([3, 1])
    # with col1:
    #     search_query = st.text_input("🔍 Search lectures by title or tags")
    # with col2:
    #     if st.button("🔄 Refresh Now", help="Force refresh lecture list"):
    #         st.session_state.lecture_cache_version += 1
    #         st.rerun()
    search_query = st.text_input("🔍 Search lectures by title or tags")
    # Load lectures with reactive caching
    @st.cache_data(show_spinner=False, ttl=60)
    def load_managed_lectures(_lecture_db, cache_version):
        return _lecture_db.get_all_lectures()
    
    lectures = load_managed_lectures(
        lecture_db, 
        st.session_state.lecture_cache_version
    )

    # Filtering and sorting logic
    filtered_lectures = [lec for lec in lectures if 
        search_query.lower() in lec["title"].lower() or
        any(tag.lower().startswith(search_query.lower()) 
            for tag in lec.get("tags", []))
    ]
    
    # Display lectures with instant delete
    for lecture in filtered_lectures:
        with st.expander(f"📖 {lecture['title']}", expanded=False):
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.caption(f"📅 Uploaded: {lecture['upload_date']}")
                st.write(f"🏷️ Tags: {', '.join(lecture.get('tags', [])) or 'None'}")
                st.write(f"📦 Chunks: {len(lecture['chunks'])} sections")
            
            with col2:
                if st.button("🗑️ Delete", key=f"del_{lecture['id']}"):
                    lecture_db.delete_lecture(lecture["id"])
                    st.session_state.lecture_cache_version += 1
                    st.rerun()
            
            with col3:
                st.download_button(
                    label="📥 Export",
                    data=json.dumps(lecture, indent=2),
                    file_name=f"{lecture['title'].replace(' ', '_')}.json",
                    mime="application/json",
                    key=f"exp_{lecture['id']}"
                )

    # Bulk actions with instant feedback
    if filtered_lectures:
        with st.container(border=True):
            st.subheader("Bulk Operations")
            selected = st.multiselect(
                "Select lectures:",
                filtered_lectures,
                format_func=lambda x: x["title"]
            )
            
            if st.button("🔥 Delete Selected", type="primary") and selected:
                for lec in selected:
                    lecture_db.delete_lecture(lec["id"])
                st.session_state.lecture_cache_version += 1
                st.rerun()


# Helper function for tab5
def render_mermaid(mermaid_code):
    def sanitize_mermaid_code(mermaid_code):
        def clean_node_name(match):
            node_id = match.group(1)
            node_label = match.group(2)


            sanitized_label = re.sub(r"[()]", "", node_label)

            return f"{node_id}[{sanitized_label}]"

        cleaned_code = re.sub(r"(\w+)\[(.*?)\]", clean_node_name, mermaid_code)

        return cleaned_code

    mermaid_code = sanitize_mermaid_code(mermaid_code)
    def display_html_dynamic(html_code, height):

        screen_width = st.components.v1.html(
            """
            <script>
                const width = Math.min(window.innerWidth * 0.9, 1200); // 90% of screen width, max 1200px
                document.write(width);
            </script>
            """,
            height=0,
        )
        

        st.components.v1.html(
            html_code, 
            width=screen_width, 
            height=height, 
            scrolling=True
        )
        
    def calculate_height(mermaid_code):
        """Calculate approximate height based on mermaid code content."""
        lines = mermaid_code.count('\n') + 1
        default_height = 350
        
        # Class Diagram - refined height calculation
        if 'classDiagram' in mermaid_code:
            # Count classes
            class_count = mermaid_code.count('class ')
            
            # Count relationships (both inheritance and associations)
            relationship_count = sum(1 for line in mermaid_code.split('\n') 
                                  if any(x in line for x in ['-->', '<--', '--|>', '<|--', '--o', 'o--', '--', '..>', '<..']))
            
            # Count methods and attributes (lines starting with + or -)
            member_count = sum(1 for line in mermaid_code.split('\n') 
                             if line.strip().startswith('+') or line.strip().startswith('-'))
            
            parameter = 0.25
            # Base height per class
            height_per_class = 100 * parameter
            # Additional height for members
            height_per_member = 50 * parameter
            # Height for relationships
            height_per_relationship = 50 * parameter
            # Padding
            padding = 400
            
            total_height = (
                (class_count * height_per_class) +
                (member_count * height_per_member) +
                (relationship_count * height_per_relationship) +
                padding
            )
            
            return max(default_height, total_height)
        
        # Entity Relationship Diagram - similar to class diagram but with different metrics
        elif 'erDiagram' in mermaid_code:
            entity_count = mermaid_code.count('||') + mermaid_code.count('|{')
            relationship_count = sum(1 for line in mermaid_code.split('\n') if '--' in line)
            attribute_count = mermaid_code.count('\n    ')  # Count indented lines as attributes
            return max(default_height, (entity_count * 100) + (relationship_count * 50) + (attribute_count * 25))
        
        elif ('graph TD' in mermaid_code or 'graph TB' in mermaid_code or 
            'flowchart TD' in mermaid_code or 'flowchart TB' in mermaid_code):
            depth, max_nodes_per_layer = calculate_graph_depth(mermaid_code)
            
            # Base height per layer
            height_per_layer = 100

            # Padding for margins
            padding = 100
            
            total_height = (depth * height_per_layer) + padding
            return max(default_height, total_height)
            
        elif ('graph LR' in mermaid_code or 'graph RL' in mermaid_code or 
            'flowchart LR' in mermaid_code or 'flowchart RL' in mermaid_code):
            return default_height - 200
            
        elif 'sequenceDiagram' in mermaid_code:
            relation = mermaid_code.count('-->')
            return max(default_height, lines * 40 + relation * 30)
        elif 'pie' in mermaid_code:
            return 550
        else:
            return default_height
    html_code = f"""
    <div style="background-color: white; padding: 1rem; border-radius: 0.5rem;">
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        <div class="mermaid">
            {mermaid_code}
        </div>
    </div>
    """
    height = calculate_height(mermaid_code)
    st.components.v1.html(html_code, height=height, scrolling=True)

def calculate_graph_depth(mermaid_code):
    """Calculate the depth (number of layers) and nodes per layer in a graph."""
    # Extract relationships from the code
    relationships = [line.strip() for line in mermaid_code.split('\n') 
                    if '-->' in line and not line.strip().startswith('%')]
    
    # Build adjacency list
    graph = {}
    nodes = set()
    
    for rel in relationships:
        # Split on --> and clean up any styling
        parts = rel.split('-->')
        if len(parts) != 2:
            continue
            
        source = parts[0].strip()
        target = parts[1].strip()
        
        # Remove styling information [...]
        source = source.split('[')[0].strip()
        target = target.split('[')[0].strip()
        
        # Build graph
        if source not in graph:
            graph[source] = set()
        graph[source].add(target)
        nodes.add(source)
        nodes.add(target)
    
    # For cyclic graphs, treat each node as a separate layer
    if any(target in graph and source in graph[target] 
           for source in graph for target in graph[source]):
        return len(nodes), 1
    
    # Find root nodes (nodes with no incoming edges)
    roots = set()
    for node in nodes:
        is_root = True
        for edges in graph.values():
            if node in edges:
                is_root = False
                break
        if is_root:
            roots.add(node)
    
    # If no roots found (due to cycle), use any node as root
    if not roots and nodes:
        roots = {next(iter(nodes))}
    
    # Calculate max depth using BFS
    max_depth = 0
    nodes_per_layer = {}
    visited = set()
    
    for root in roots:
        queue = [(root, 1)]
        layer_visited = set()
        
        while queue:
            node, depth = queue.pop(0)
            if node in layer_visited:
                continue
                
            layer_visited.add(node)
            max_depth = max(max_depth, depth)
            
            # Count nodes per layer
            nodes_per_layer[depth] = nodes_per_layer.get(depth, 0) + 1
            
            # Add children to queue
            if node in graph:
                for child in graph[node]:
                    if child not in visited:  # Only visit each node once
                        queue.append((child, depth + 1))
                        visited.add(child)
    
    return max_depth, max(nodes_per_layer.values() if nodes_per_layer else [1])

# Tab 5: AI Teacher
with tab5:
    st.header("🤖 Chat & Learn with Your AI Buddy")
    st.subheader(f"Selected Note: {selected_lecture['title']}")

    if not openai_api_key:
        load_dotenv(Path(__file__).parent.parent / "config" / ".env")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            st.info("Please add your OpenAI API key in the sidebar or configure OPENAI_API_KEY in the config/.env file.")
            st.stop()

    # Initialize RAG instance at the beginning of tab5
    rag = RAG(openai_api_key=openai_api_key)

    # Select appropriate system message based on chat mode
    SYSTEM_MESSAGE = SYSTEM_MESSAGE2 if chat_mode.startswith("Chat with PDF:") else SYSTEM_MESSAGE1
    # Initialize with teaching assistant context
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {
                "role": "system", 
                "content": SYSTEM_MESSAGE
            },
            {
                "role": "assistant", 
                "content": "Welcome to your AI-powered study session! 📚 How can I help you with your learning today?"
            }
        ]


 
    if chat_mode.startswith("Chat with PDF:"):
        try:
            vector_store_path = selected_lecture.get('vector_store_path')
            if vector_store_path and os.path.exists(vector_store_path):
                rag.load(vector_store_path)
            else:
                st.warning("Vector store not found for this lecture. Falling back to general chat mode.")
                chat_mode = "General Chat"
        except Exception as e:
            st.error(f"Error loading RAG: {str(e)}")
            chat_mode = "General Chat"        

    messages_container = st.container()
    with messages_container:
        for msg in st.session_state.messages:
            if msg["role"] == "system":  # Hide system message from UI
                continue
            
            role = msg["role"]
            content = msg["content"]
            
            # Create a single message container for all content
            message_placeholder = st.chat_message(role)
            
            if "```mermaid" in content:
                segments = content.split("```mermaid")
                # Write initial text if exists
                if segments[0].strip():
                    message_placeholder.write(segments[0].strip())
                
                # Process each mermaid diagram and following text
                for segment in segments[1:]:
                    parts = segment.split("```", 1)
                    if len(parts) >= 1:
                        mermaid_code = parts[0].strip()
                        with message_placeholder:
                            # Create a separate client for Mermaid validation using GPT-3.5 Turbo
                            validation_client = ChatOpenAI(
                                api_key=openai_api_key,
                                model_name="gpt-4-turbo",
                                temperature=0.1
                            )
                            
                            validation_prompt = f"""Please validate this mermaid diagram code and return either:
                            1. The original code if it's valid, or
                            2. A corrected version if there are any errors
                            3. Do not change the code if it's valid

                            Pay attention to the following:
                            - Use <|-- for class inheritance and <|.. for interface implementation, and do not mix them incorrectly.
                            - Ensure interface is used only for defining interfaces, not regular classes.
                            - Keep relationships simple and structured, avoiding excessive arrow types or complex hierarchies.
                            - Avoid mathematical operators (`x`, `+`, `-`, `/`, `*`) and special characters like `()[]` directly appearing in node names, otherwise Mermaid parsing will throw an error. Use `_` or `-` instead of operators, such as `Current_x_Resistance` or `Current-Times-Resistance`.
                            
                            Code to validate:
                            ```mermaid
                            {mermaid_code}
                            ```
                            """

                            try:
                                validation_response = validation_client.invoke([{
                                    "role": "user",
                                    "content": validation_prompt
                                }])
                                
                                # Extract validated/corrected code
                                validated_code = validation_response.content
                                if "```mermaid" in validated_code:
                                    validated_code = validated_code.split("```mermaid")[1].split("```")[0].strip()
                                else:
                                    validated_code = mermaid_code
                                    
                                mermaid_code = validated_code
                            except Exception as e:
                                st.error(f"Error validating mermaid code: {str(e)}")
                            # Display source code first
                            st.code(mermaid_code, language="mermaid")
                            # Then render the diagram
                            render_mermaid(mermaid_code)
                    if len(parts) > 1 and parts[1].strip():
                        message_placeholder.markdown(parts[1].strip())
            else:
                message_placeholder.write(content)

    prompt = st.chat_input("Ask your study question here...")
    
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        if chat_mode.startswith("Chat with PDF:"):
            try:
                # Use RAG to get context-aware response
                context = rag.ask_question(prompt)
                # Add context to the system message
                context_message = {
                    "role": "system",
                    "content": f"Use this context to answer the question: {context}\n\n" + st.session_state.messages[0]["content"]
                }
                
                # Prepare messages for API call
                api_messages = [context_message]
                api_messages.extend([msg for msg in st.session_state.messages[-4:] if msg["role"] != "system"])
                
            except Exception as e:
                st.error(f"Error using RAG: {str(e)}")
                # Fallback to regular chat if RAG fails
                api_messages = [msg for msg in st.session_state.messages if msg["role"] != "system"]
                api_messages.insert(0, st.session_state.messages[0])
        else:
            # Regular chat mode
            api_messages = [msg for msg in st.session_state.messages if msg["role"] != "system"]
            api_messages.insert(0, st.session_state.messages[0])
        
        response = client.invoke(api_messages)
        msg = response.content  # Extract content from the response
        
        st.session_state.messages.append({"role": "assistant", "content": msg})
        st.rerun()

    # Add export button in a container
    export_container = st.container()
    with export_container:
        col1, col2 = st.columns([2, 1])
        with col2:
            subcol1, subcol2 = st.columns([1, 1])
            with subcol1:
                if st.button("🔄 Clear Chat", key=f"clear_chat_button_{{current_lecture_id}}"):
                    # Reset chat history but keep system message and welcome message
                    st.session_state.messages = [
                        st.session_state.messages[0],  # Keep system message
                        {"role": "assistant", "content": "Welcome to your AI-powered study session! 📚 How can I help you with your learning today?"}
                    ]
                    st.rerun()
            with subcol2:
                if st.button("📑 Export Chat", key=f"export_chat_button_{{current_lecture_id}}"):
                    # Create PDF
                    buffer = BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=letter)
                    styles = getSampleStyleSheet()
                    
                    # Create custom styles for different message types
                    styles.add(ParagraphStyle(
                        name='User',
                        parent=styles['Normal'],
                        textColor=colors.HexColor('#2C3E50'),
                        spaceAfter=10,
                        fontSize=11,
                        leftIndent=0
                    ))
                    styles.add(ParagraphStyle(
                        name='Assistant',
                        parent=styles['Normal'],
                        textColor=colors.HexColor('#34495E'),
                        spaceAfter=15,
                        fontSize=11,
                        leftIndent=20,
                        borderPadding=(10, 10, 10, 10),
                        borderWidth=1,
                        borderColor=colors.HexColor('#E8E8E8'),
                        borderRadius=5
                    ))

                    # Build PDF content
                    content = []
                    content.append(Paragraph("Chat History", styles['Title']))
                    content.append(Spacer(1, 20))
                    
                    # Add timestamp and model info
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    content.append(Paragraph(f"Generated on: {timestamp}", styles['Normal']))
                    content.append(Paragraph(f"Model: {model}", styles['Normal']))
                    content.append(Spacer(1, 20))

                    for msg in st.session_state.messages:
                        if msg["role"] == "system":
                            continue
                            
                        # Clean and format message content
                        text = msg["content"]
                        # Handle code blocks
                        text = text.replace("```", "")
                        # Escape HTML special characters
                        text = html.escape(text)
                        # Replace newlines with HTML breaks
                        text = text.replace("\n", "<br/>")
                        
                        # Format based on role
                        if msg["role"] == "user":
                            text = f"<b>You:</b> {text}"
                            style = styles["User"]
                        else:
                            text = f"<b>Assistant:</b> {text}"
                            style = styles["Assistant"]
                        
                        content.append(Paragraph(text, style))
                        content.append(Spacer(1, 10))

                    # Build PDF
                    doc.build(content)
                    
                    # Prepare download button
                    pdf_bytes = buffer.getvalue()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"chat_history_{timestamp}.pdf"
                    
                    # Create download button
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                    )
                    st.success("PDF generated successfully! Click the button above to download.")

# Add custom CSS for right-aligned buttons
st.markdown("""
<style>
    .stButton {
        position: relative;
        float: right;
        margin-left: 10px;
    }
    .button-container {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)



# ===== Run the App =====
if __name__ == "__main__":
    main()