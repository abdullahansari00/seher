from pathlib import Path

import chromadb
from django.conf import settings

VECTOR_STORE_PATH = Path(settings.BASE_DIR) / "data" / "chroma"


def get_client():
    VECTOR_STORE_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    return chromadb.PersistentClient(
        path=str(VECTOR_STORE_PATH),
    )


def get_collection():
    client = get_client()

    return client.get_or_create_collection(
        name="seher_knowledge",
    )
