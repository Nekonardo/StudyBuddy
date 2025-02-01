import re
import io
import uuid
import json
import fitz
from pathlib import Path
from datetime import datetime
from docx import Document
from PIL import Image
import pytesseract
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

# ===== Lecture Notes Ingestion =====
class LectureNotesIngester:
    def __init__(self):
        self.supported_formats = [".pdf", ".docx", ".txt"]
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=300,
            separators=["\n\n## ", "\n# ", "\n\n", "\n", " "]
        )

    def _determine_file_type(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext not in self.supported_formats:
            raise ValueError(f"Unsupported format: {ext}. Supported: {self.supported_formats}")
        return ext

    def _extract_text_from_pdf(self, file_path: str) -> str:
        text = ""
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
            for img in page.get_images():
                try:
                    base_image = doc.extract_image(img[0])
                    image = Image.open(io.BytesIO(base_image["image"]))
                    text += f"\n[DIAGRAM]: {pytesseract.image_to_string(image)}\n"
                except Exception as e:
                    text += f"\n[IMAGE ERROR: {str(e)}]\n"
        return text

    def _extract_text_from_docx(self, file_path: str) -> str:
        return "\n".join([p.text for p in Document(file_path).paragraphs])

    def _extract_text_from_txt(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _clean_text(self, text: str) -> str:
        """Preserve LaTeX equations while cleaning"""
        # Identify and protect equations
        protected = []
        text = re.sub(
            r'\$(.*?)\$|\$\$(.*?)\$\$',  # Matches $...$ and $$...$$
            lambda m: f"__EQUATION_{len(protected)}__", 
            text
        )
        
        # Clean non-equation text
        text = re.sub(r'\s+', ' ', text)
        
        # Restore equations
        for i in range(len(protected)):
            text = text.replace(f"__EQUATION_{i}__", protected[i])
            
        return text

    def ingest(self, file_path: str) -> list[str]:
        ext = self._determine_file_type(file_path)
        if ext == ".pdf":
            raw_text = self._extract_text_from_pdf(file_path)
        elif ext == ".docx":
            raw_text = self._extract_text_from_docx(file_path)
        else:
            raw_text = self._extract_text_from_txt(file_path)
        cleaned_text = self._clean_text(raw_text)
        return self.text_splitter.split_text(cleaned_text)

class LectureDB:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), "../data/lectures_db.json")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def save_lecture(self, title: str, file_name: str, chunks: list, tags: list = [], vector_store_path: str = None):
        """
        Save lecture information to the database
        
        Args:
            title: Lecture title
            file_name: File name
            chunks: List of Document objects
            tags: List of tags
            vector_store_path: Path to the vector store
        """
        try:
            # Convert the Document object to a serializable format
            serializable_chunks = []
            for chunk in chunks:
                if hasattr(chunk, 'page_content'):
                    # If it is a Document object, extract the page_content.
                    serializable_chunks.append(chunk.page_content)
                else:
                    # If it is already a string, use it directly.
                    serializable_chunks.append(chunk)

            if not os.path.exists(self.db_path):
                with open(self.db_path, "w") as f:
                    json.dump([], f)

            with open(self.db_path, "r+") as f:
                try:
                    lectures = json.load(f)
                except json.JSONDecodeError:
                    lectures = []
                
                lectures.append({
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "upload_date": datetime.now().strftime("%Y-%m-%d"),
                    "file_name": file_name,
                    "chunks": serializable_chunks, 
                    "tags": tags,
                    "vector_store_path": vector_store_path
                })
                
                f.seek(0)
                json.dump(lectures, f, ensure_ascii=False, indent=2)
                f.truncate()
                
        except Exception as e:
            print(f"Error saving lecture: {str(e)}")
            raise
    
    def get_lecture(self, lecture_id: str):
        with open(self.db_path, "r") as f:
            lectures = json.load(f)
            return next((lec for lec in lectures if lec["id"] == lecture_id), None)
    
    def get_all_lectures(self):
        try:
            if not os.path.exists(self.db_path):
                return []
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading lectures: {str(e)}")
            return []
        
    def delete_lecture(self, lecture_id: str):
        """Optimized deletion with direct file overwrite"""
        try:
            with open(self.db_path, "r+") as f:
                lectures = json.load(f)
                new_lectures = [lec for lec in lectures if lec["id"] != lecture_id]
                f.seek(0)
                json.dump(new_lectures, f, indent=2)
                f.truncate()
            return True
        except Exception as e:
            print(f"Delete error: {str(e)}")
            return False
        
class TagDB:
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / "data" / "tags_db.json"
        else:
            self.db_path = Path(db_path)
        self._initialize_db()
    
    def _initialize_db(self):
        if not Path(self.db_path).exists():
  
            tags_file = Path(__file__).parent.parent / "data" / "tags_db.json"
            try:
                with open(tags_file, 'r', encoding='utf-8') as f:
                    default_tags = json.load(f)
                self.save_tags(default_tags)
            except FileNotFoundError:
           
                fallback_tags = ["Biology", "Chemistry", "Physics"]
                self.save_tags(fallback_tags)
    
    def load_tags(self):
        try:
            with open(self.db_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def save_tags(self, tags):
        with open(self.db_path, "w") as f:
            json.dump(tags, f, indent=2)