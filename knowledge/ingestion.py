from pathlib import Path

from .models import Document, DocumentChunk
from .rag import index_chunk


def ingest_text_file(
    file_path: str,
    *,
    title: str,
    chunk_size: int = 1000,
) -> Document:
    path = Path(file_path)

    text = path.read_text(encoding="utf-8").strip()

    if not text:
        raise ValueError("The document is empty.")

    document = Document.objects.create(
        title=title,
        source_type="file",
        source_uri=str(path),
        raw_text=text,
        status="processing",
    )

    try:
        chunks = []

        for start in range(0, len(text), chunk_size):
            content = text[start : start + chunk_size].strip()

            if not content:
                continue

            chunk = DocumentChunk.objects.create(
                document=document,
                chunk_index=len(chunks),
                content=content,
            )

            chunks.append(chunk)

        for chunk in chunks:
            index_chunk(chunk)

        document.status = "ready"
        document.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return document

    except Exception:
        document.status = "failed"
        document.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )
        raise
