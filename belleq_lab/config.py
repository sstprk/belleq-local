import json
import os
from pathlib import Path
from pydantic import BaseModel, Field, model_validator

class Node(BaseModel):
    id: str
    url: str

class Settings(BaseModel):
    node_id: str = "mini-1"
    coordinator: bool = False
    bind: str = "127.0.0.1"
    port: int = 8000
    qdrant_url: str = "http://127.0.0.1:6333"
    collection: str = Field(default="lab", pattern=r"^[A-Za-z0-9_-]+$")
    ollama_url: str = "http://127.0.0.1:11434"
    embedding_model: str = "nomic-embed-text:latest"
    embedding_dimension: int = Field(default=768, ge=1)
    embedding_digest: str = ""
    distance: str = "Cosine"
    query_prefix: str = "search_query: "
    document_prefix: str = "search_document: "
    generation_url: str = "http://127.0.0.1:11434"
    generation_model: str = "qwen3:1.7b"
    context_chars: int = Field(default=5000, ge=1, le=12000)
    node_timeout: float = Field(default=60, gt=0)
    backend_timeout: float = Field(default=120, gt=0)
    nodes: list[Node] = Field(default_factory=list)
    max_upload_bytes: int = 20 * 1024 * 1024
    api_key: str = ""  # set using BELLEQ_API_KEY, never commit secrets

    @model_validator(mode="after")
    def valid(self):
        if self.distance != "Cosine":
            raise ValueError("This experiment supports Cosine only (higher score is better)")
        if len({n.id for n in self.nodes}) != len(self.nodes):
            raise ValueError("duplicate node ids")
        if len({n.url.rstrip('/') for n in self.nodes}) != len(self.nodes):
            raise ValueError("duplicate node URLs")
        if self.coordinator and not self.nodes:
            raise ValueError("coordinator requires nodes")
        return self

    def signature(self, digest: str) -> dict:
        return dict(model=self.embedding_model, digest=digest,
                    dimension=self.embedding_dimension, distance=self.distance,
                    query_prefix=self.query_prefix, document_prefix=self.document_prefix,
                    chunking="belleq-512chars-64overlap-v1")

def load_settings():
    path = Path(os.getenv("BELLEQ_CONFIG", "config/local.json"))
    data = json.loads(path.read_text())
    data["api_key"] = os.getenv("BELLEQ_API_KEY", "")
    return Settings(**data)
