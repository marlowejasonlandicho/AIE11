"""Stage 1: load, split, embed the corpus, and hand back a retriever.

YOUR CODE GOES HERE. `build_retriever` raises NotImplementedError.

You did all of this in the Session 4 notebook (`Agentic_RAG_From_Scratch.ipynb`,
Task 4). Two differences here:
  - `api.py` calls this exactly once, in the FastAPI lifespan, and holds the retriever for
    the life of the process — never once per request (Week 1's CLI re-embedded every run).
  - Qdrant is **on disk**, not `:memory:`. It memory-maps its files, so the collection
    survives restarts — you embed once, ever, and later boots load from disk for free.
"""

from pathlib import Path

from langchain_core.retrievers import BaseRetriever
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QDRANT_PATH = Path(__file__).resolve().parent.parent / "qdrant_storage"  # on-disk, gitignored

# gpt-5.4-mini: newest-gen, strong tool-calling, fast + cheap for repeated runs.
# (gpt-5.6-luna/terra are reasoning-only and can't tool-call over chat completions.)
CHAT_MODEL = "gpt-5.4-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
COLLECTION_NAME = "ai_engineering_technical_challenge_docs_v1"


def build_retriever(corpus_path: Path, k: int = 3) -> BaseRetriever:
    """Load the corpus, split it, embed it into Qdrant, and return a retriever.

    Args:
        corpus_path: the .txt file to index.
        k: how many chunks the retriever returns per query.

    Returns:
        A LangChain retriever (`vector_store.as_retriever(...)`) ready to `.invoke(query)`.

    The moves, all from Session 4 Task 4 (now on disk):
      1. `TextLoader(corpus_path).load()` -> Documents.
      2. `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)` -> chunks.
      3. `OpenAIEmbeddings(model=EMBEDDING_MODEL)`, and an on-disk client:
             client = QdrantClient(path=str(QDRANT_PATH))
         Create the collection only if it's missing (`client.collection_exists(name)`), build a
         `QdrantVectorStore`, and `.add_documents(chunks)` ONLY when the collection is empty
         (`client.count(name).count == 0`) — otherwise reuse what's already on disk.
      4. `vector_store.as_retriever(search_kwargs={"k": k})`.

    Two things persistence forces you to get right:
      - Idempotency: don't re-create or re-embed an index that already exists, or you pay to
        embed every boot (and `create_collection` throws on a collision). Guard both.
      - `chunk_id`: the chunk's position in the split list is the only id you have. Stamp it
        into metadata (`chunk.metadata["chunk_id"] = i`) BEFORE adding — it's what makes
        `Source.chunk_id` mean anything, and once on disk you can't add it retroactively.

    Note: on-disk Qdrant locks its folder to one client, so one server owns it at a time.
    Delete `qdrant_storage/` if you change the corpus, chunking, or embedding model.
    Hosted/shared instead? Run a Qdrant server and swap the client for
    `QdrantClient(url="http://localhost:6333")` — that's the multi-process production path.
    """

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    embedding_dim = len(embeddings.embed_query("test"))

    _prev_client = globals().get("qdrant_client")
    if _prev_client is not None:
        _prev_client.close()

    qdrant_client = QdrantClient(path=str(QDRANT_PATH))

    if not qdrant_client.collection_exists(COLLECTION_NAME):
      qdrant_client.create_collection(collection_name=COLLECTION_NAME,
                                      vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE))

    text_splitter = RecursiveCharacterTextSplitter(chunk_size = 1000, 
                                                   chunk_overlap = 200, 
                                                   length_function=len)
    vector_store = QdrantVectorStore(client = qdrant_client,
                                     collection_name = COLLECTION_NAME,
                                     embedding=embeddings)

    if corpus_path.exists():
      loader = TextLoader(str(corpus_path))
      documents = loader.load()
      chunks = text_splitter.split_documents(documents)

      print(f"Loaded {len(documents)} document(s), split into {len(chunks)} chunks")
      print("-" * 50)
      print(chunks[0].page_content[:300] + "...")

      for index, chunk in enumerate(chunks):
         chunk.metadata["chunk_id"] = index

      if qdrant_client.count(COLLECTION_NAME).count == 0:
        vector_store.add_documents(chunks)
        print(f"Embedded and stored {len(chunks)} chunks in '{COLLECTION_NAME}'")
      else:
        print(f"Loaded existing '{COLLECTION_NAME}' from disk — skipped re-embedding")

    else:
      raise FileNotFoundError(f"Invalid file: {corpus_path}")

    return vector_store.as_retriever(search_type="similarity_score_threshold", 
                                     search_kwargs={"k": k,"score_threshold": 0.3})
