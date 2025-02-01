import sqlite3
import pandas as pd
from pathlib import Path

def init_db():
    db_path = Path(__file__).parent.parent / "data" / "progress.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS quizzes
                 (id INTEGER PRIMARY KEY, 
                  student_id INTEGER, 
                  timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS questions
                 (id INTEGER PRIMARY KEY,
                  quiz_id INTEGER,
                  question TEXT,
                  student_answer TEXT,
                  correct_answer TEXT,
                  topic TEXT)''')  # ← MUST HAVE THIS LINE
    c.execute('''CREATE INDEX IF NOT EXISTS idx_quiz_id 
                 ON questions (quiz_id)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_student_id 
                 ON quizzes (student_id)''')
    conn.commit()
    conn.close()

def log_quiz_result(student_id: int, questions: list):
    db_path = Path(__file__).parent.parent / "data" / "progress.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''INSERT INTO quizzes (student_id, timestamp)
                 VALUES (?, datetime('now'))''', (student_id,))
    quiz_id = c.lastrowid
    for q in questions:
        c.execute('''INSERT INTO questions 
                     (quiz_id, question, student_answer, correct_answer, topic)
                     VALUES (?, ?, ?, ?, ?)''',
                  (quiz_id, 
                   q['question'], 
                   q.get('student_answer', ''), 
                   q['answer'],
                   q.get('topic', 'general')))  # Added topic
    conn.commit()
    conn.close()

def get_student_progress(student_id: int) -> pd.DataFrame:
    db_path = Path(__file__).parent.parent / "data" / "progress.db"
    conn = sqlite3.connect(db_path)
    query = '''
    SELECT qz.timestamp, 
           SUM(CASE WHEN q.student_answer = q.correct_answer THEN 1 ELSE 0 END) AS correct,
           COUNT(*) AS total,
           (SUM(CASE WHEN q.student_answer = q.correct_answer THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) * 100 AS score
    FROM quizzes qz
    JOIN questions q ON qz.id = q.quiz_id
    WHERE qz.student_id = ?
    GROUP BY qz.id
    '''
    df = pd.read_sql_query(query, conn, params=(student_id,))
    conn.close()
    return df

def get_weak_topics(student_id: int) -> pd.DataFrame:
    db_path = Path(__file__).parent.parent / "data" / "progress.db"
    conn = sqlite3.connect(db_path)
    query = '''
    SELECT q.topic,
           (SUM(CASE WHEN q.student_answer = q.correct_answer THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) * 100 AS accuracy
    FROM questions q
    JOIN quizzes qz ON q.quiz_id = qz.id
    WHERE qz.student_id = ?
    GROUP BY q.topic
    HAVING accuracy < 60
    ORDER BY accuracy ASC
    LIMIT 5
    '''
    df = pd.read_sql_query(query, conn, params=(student_id,))
    conn.close()
    return df