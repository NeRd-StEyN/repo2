import os
import base64
import tempfile
import gc
import sys
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from deep_translator import GoogleTranslator

def safe_print(*args, **kwargs):
    """Print that ignores characters that cannot be encoded by the terminal."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        new_args = []
        encoding = sys.stdout.encoding or "ascii"
        for arg in args:
            if isinstance(arg, str):
                new_args.append(arg.encode(encoding, errors="ignore").decode(encoding))
            else:
                new_args.append(arg)
        print(*new_args, **kwargs)


load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    safe_print("Warning: GROQ_API_KEY not found in environment variables!")

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
safe_print("Loaded HuggingFace Embeddings: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


chat_sessions = {}  


def init_chat_from_base64(session_id: str, pdf_base64: str):
    """Initialize chat session using Base64 PDF (Render memory safe)."""
    temp_file_path = None
    try:
       
        pdf_bytes = base64.b64decode(pdf_base64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            temp_file_path = tmp.name

      
        loader = PyPDFLoader(temp_file_path)
        docs = loader.load()
        
        if not docs:
            raise ValueError("No documents loaded from PDF.")
            
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_documents(docs)
        
        if not chunks:
            raise ValueError("No readable text found in the uploaded PDF.")

        test_embedding = embedding_model.embed_query("test")
        safe_print(f"Embedding dimension = {len(test_embedding)}")

        temp_path = f"/tmp/vectorstore_{session_id}"
        vectorstore = FAISS.from_documents(chunks, embedding_model)
        vectorstore.save_local(temp_path)

        chat_sessions[session_id] = {
            "vectorstore_path": temp_path,
            "chat_history": [],
        }

        safe_print(f"Chat session '{session_id}' initialized successfully.")
        return {"message": f"Chat session '{session_id}' initialized successfully."}

    except Exception as e:
        safe_print(f"Error initializing chat: {e}")
        return {"error": str(e)}
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                safe_print(f"Could not delete temp file: {e}")
        
        gc.collect()


def chat_with_pdf(session_id: str, message: str):
    """Chat with initialized PDF session (Render-safe)."""
    try:
        if session_id not in chat_sessions:
            return {"error": f"No chat session found for '{session_id}'."}

        session = chat_sessions[session_id]
        temp_path = session["vectorstore_path"]
        chat_history = session["chat_history"]

      
        try:
            user_message_en = GoogleTranslator(source="auto", target="en").translate(message)
        except:
            user_message_en = message  

        vectorstore = FAISS.load_local(
            temp_path, embedding_model, allow_dangerous_deserialization=True
        )

        retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
        
 
        docs = retriever.invoke(user_message_en)

        translated_docs = []
        translator = GoogleTranslator(source='auto', target='en')
        
        for d in docs:
            try:
                trans_text = translator.translate(d.page_content)
                translated_docs.append(trans_text)
            except Exception as e:
                safe_print(f"Translation failed for chunk: {e}")
                translated_docs.append(d.page_content)

        context = "\n\n".join(translated_docs) if translated_docs else "No context found."

        history_context = ""
        if chat_history:
            past_exchanges = chat_history[-5:]
            history_context = "\n".join([
                f"User: {u}\nAssistant: {a[:150]}" 
                for u, a in past_exchanges
            ])
            history_context = f"\nPrevious conversation:\n{history_context}\n"
        
        prompt = f"""You are an AI assistant that ONLY speaks English.
The user has provided a document (context) which may be in a different language.
Your task is to answer the user's question based on the context, but you must TRANSLATE your answer into ENGLISH.

### STRICT RULES:
1. **ENGLISH ONLY**: Your response must be 100% in English. 
2. **TRANSLATE**: If the answer is found in non-English context, translate to English.
3. **ACCURACY**: Use only the context. If not found, say:
   "Sorry, I cannot answer this question based on the provided context."

### Context:
{context}

### Conversation History:
{history_context}

### User Question (normalized to English):
{user_message_en}

### Answer (in English):"""

        llm = ChatGroq(
            api_key=groq_api_key,
            model="llama-3.1-8b-instant",
            temperature=0.3,
            max_tokens=400,
            model_kwargs={"top_p": 0.9}
        )
        
        response = llm.invoke(prompt)
        answer = getattr(response, "content", "").strip() or "No relevant information found."

     
        chat_history.append((message, answer))

        safe_print(f"[Chat] {session_id} | Q: {message} | A: {answer[:120]}...")
        return {"response": answer}

    except Exception as e:
        safe_print(f"Error in chat_with_pdf: {e}")
        return {"error": str(e)}
    finally:
        gc.collect()

def chat_with_pdf_stream(session_id: str, message: str):
    """Chat with initialized PDF session and stream response character by character."""
    try:
        if session_id not in chat_sessions:
            yield f"Error: No chat session found for '{session_id}'."
            return

        session = chat_sessions[session_id]
        temp_path = session["vectorstore_path"]
        chat_history = session["chat_history"]

        try:
            user_message_en = GoogleTranslator(source="auto", target="en").translate(message)
        except:
            user_message_en = message  

        vectorstore = FAISS.load_local(
            temp_path, embedding_model, allow_dangerous_deserialization=True
        )

        retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
        docs = retriever.invoke(user_message_en)

        translated_docs = []
        translator = GoogleTranslator(source='auto', target='en')
        
        for d in docs:
            try:
                trans_text = translator.translate(d.page_content)
                translated_docs.append(trans_text)
            except Exception as e:
                translated_docs.append(d.page_content)

        context = "\n\n".join(translated_docs) if translated_docs else "No context found."

        history_context = ""
        if chat_history:
            past_exchanges = chat_history[-5:]
            history_context = "\n".join([f"User: {u}\nAssistant: {a[:150]}" for u, a in past_exchanges])
            history_context = f"\nPrevious conversation:\n{history_context}\n"
        
        prompt = f"""You are an AI assistant that ONLY speaks English.
The user has provided a document (context) which may be in a different language.
Your task is to answer the user's question based on the context, but you must TRANSLATE your answer into ENGLISH.

### STRICT RULES:
1. **ENGLISH ONLY**: Your response must be 100% in English. 
2. **TRANSLATE**: If the answer is found in non-English context, translate to English.
3. **ACCURACY**: Use only the context. If not found, say:
   "Sorry, I cannot answer this question based on the provided context."

### Context:
{context}

### Conversation History:
{history_context}

### User Question:
{user_message_en}

### Answer (in English):"""

        llm = ChatGroq(
            api_key=groq_api_key,
            model="llama-3.1-8b-instant",
            temperature=0.3,
            max_tokens=400,
        )
        
        full_answer = ""
        for chunk in llm.stream(prompt):
            content = getattr(chunk, "content", str(chunk))
            if content:
                full_answer += content
                for char in content:
                    yield char
        
        chat_history.append((message, full_answer))

    except Exception as e:
        yield f"Error: {str(e)}"
    finally:
        gc.collect()
