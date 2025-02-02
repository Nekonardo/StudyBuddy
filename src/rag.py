from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_community.llms import OpenAI
import os
import shutil
from typing import BinaryIO, Union, List, Dict
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter


class RAG:
    def __init__(self, openai_api_key: str):
        """Initialize RAG with OpenAI API key"""
        self.openai_api_key = openai_api_key
        self.vectorstore = None
        self.qa = None

    def ingest(self, file: Union[str, BinaryIO, Path]) -> list[str]:
        """
        Process uploaded PDF/TXT file and split into chunks
        
        Args:
            file: Can be either:
                - A string path to the PDF/TXT file
                - A file-like object (BinaryIO)
                - A Path object
        """
        if isinstance(file, (str, Path)):
            file_path = str(file)
        else:
            os.makedirs("temp", exist_ok=True)
            if hasattr(file, 'name'):
                filename = os.path.basename(file.name)
            else:
                filename = "temp_file"  # Remove default .pdf extension
            file_path = f"./temp/{filename}"
            
            with open(file_path, "wb") as buffer:
                if hasattr(file, 'read'):
                    shutil.copyfileobj(file, buffer)
                else:
                    buffer.write(file)

        # Determine file type and use appropriate loader
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == '.pdf':
            loader = PyPDFLoader(file_path)
        elif file_extension == '.txt':
            loader = TextLoader(file_path, encoding='utf-8')
        elif file_extension == '.md':
            loader = UnstructuredMarkdownLoader(file_path)
        elif file_extension in ['.doc', '.docx']:
            loader = UnstructuredWordDocumentLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        # Load and parse PDF content
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=300,
            separators=["\n\n## ", "\n# ", "\n\n", "\n", " "]
        )
        
        # Use split_documents method directly instead of calling the splitter
        chunks = text_splitter.split_documents(documents)
        
        # Create vector index
        embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)
        self.vectorstore = FAISS.from_documents(chunks, embeddings)

        # Initialize QA chain
        self.qa = RetrievalQA.from_chain_type(
            llm=OpenAI(api_key=self.openai_api_key), 
            retriever=self.vectorstore.as_retriever()
        )
        
        # Clean up temporary file if we created one
        if not isinstance(file, (str, Path)):
            os.remove(file_path)
            
        return chunks

    def ask_question(self, question: str) -> Dict:
        """
        Ask a question and get relevant content from the vector database
        
        Args:
            question: The question to ask
            
        Returns:
            Dict containing the question and relevant texts
        """
        if not self.qa or not self.vectorstore:
            raise ValueError("No PDF has been ingested yet. Please call ingest() first.")

        # Retrieve relevant content using vector database
        retriever = self.vectorstore.as_retriever()
        docs = retriever.get_relevant_documents(question)
        relevant_texts = [doc.page_content for doc in docs]

        return {
            "question": question,
            "relevant_texts": relevant_texts
        }

    def save(self, path: Union[str, Path]) -> None:
        """Save the vector store to disk."""
        path = Path(path)
        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the vector store
        self.vectorstore.save_local(str(path))

    def load(self, path: Union[str, Path]) -> None:
        """Load the vector store from disk."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Vector store not found at {path}")
            
        try:
            self.vectorstore = FAISS.load_local(
                str(path),
                OpenAIEmbeddings(api_key=self.openai_api_key),
                allow_dangerous_deserialization=True
            )
            
            # Reinitialize QA chain with loaded vectorstore
            self.qa = RetrievalQA.from_chain_type(
                llm=OpenAI(api_key=self.openai_api_key),
                retriever=self.vectorstore.as_retriever()
            )
        except Exception as e:
            raise Exception(f"Error loading vector store: {str(e)}")
