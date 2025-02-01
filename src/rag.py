from langchain_community.document_loaders import PyPDFLoader
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
        Process uploaded PDF file and split into chunks
        
        Args:
            file: Can be either:
                - A string path to the PDF file
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
                filename = "temp.pdf"
            file_path = f"./temp/{filename}"
            
            with open(file_path, "wb") as buffer:
                if hasattr(file, 'read'):
                    shutil.copyfileobj(file, buffer)
                else:
                    buffer.write(file)

        # Load and parse PDF content
        loader = PyPDFLoader(file_path)
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

    def save(self, path: Union[str, Path]):
        """
        Save vector storage to specified path

        Args:

        path: Path to save vector storage
        """
        if self.vectorstore is None:
            raise ValueError("No vector store to save. Please ingest documents first.")
            
        # 确保目录存在
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存向量存储
        self.vectorstore.save_local(str(save_path))
        
    def load(self, path: Union[str, Path]):
        """
        Load vector storage from the specified path

        Args:

        path: Path to the vector storage
        """
        if not Path(path).exists():
            raise ValueError(f"Vector store path does not exist: {path}")
            

        embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)

        self.vectorstore = FAISS.load_local(
            str(path), 
            embeddings,
            allow_dangerous_deserialization=True
        )
        

        self.qa = RetrievalQA.from_chain_type(
            llm=OpenAI(api_key=self.openai_api_key), 
            retriever=self.vectorstore.as_retriever()
        )
