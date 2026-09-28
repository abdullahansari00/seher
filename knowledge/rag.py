from .embeddings import embed_text
from .models import DocumentChunk
from .vector_store import get_collection


def index_chunk(chunk: DocumentChunk) -> None:
    embedding = embed_text(chunk.content)

    collection = get_collection()

    vector_id = f"chunk-{chunk.id}"

    collection.upsert(
        ids=[vector_id],
        embeddings=[embedding],
        documents=[chunk.content],
        metadatas=[
            {
                "document_id": chunk.document_id,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
            }
        ],
    )

    chunk.vector_id = vector_id

    chunk.save(
        update_fields=[
            "vector_id",
            "updated_at",
        ]
    )


def retrieve_chunks(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    if not query.strip():
        return []

    query_embedding = embed_text(query)

    collection = get_collection()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved = []

    for rank, (document, metadata, distance) in enumerate(
        zip(documents, metadatas, distances),
        start=1,
    ):
        retrieved.append(
            {
                "rank": rank,
                "content": document,
                "score": distance,
                "metadata": metadata or {},
            }
        )

    return retrieved
