# Kaynak kökeni

Belleq kaynağı: `https://github.com/Salih-Toprak/belleq-user.git`
İncelenen commit: `1fcd009dadd54eec3531f8ce9fee29022fb6d9fa`.

Aynen alınan dosyalar:
- `app/ingestion/chunker.py` → `belleq_lab/chunker.py`
- `app/ingestion/extractors.py` → `belleq_lab/extractors.py`

Uyarlanan fikir ve sözleşmeler:
- `app/conversation/kb_writer.py`: chunk → embed → payload + deterministic ID → upsert.
- `app/embeddings/ollama_adapter.py`: Ollama `/api/embed` batch protokolü.
- `app/vectordb/qdrant_adapter.py`: koleksiyon, vektör upsert ve payload'lı arama.
- `app/query/pipeline.py` / `app/api/outward/query_routes.py`: query/top_k → chunks.

Yeni: bağımsız FastAPI servis, REST tabanlı Qdrant adapter, schema fingerprint,
aggregator, strict/partial hata sözleşmesi, Qwen answer endpoint'i, config ve lab araçları.
Qdrant adapter eski `.search` istemci çağrısına bağımlı olmadan `/points/query` kullanır.
Belleq'in mevcut kaynakları değiştirilmedi. Yeni bir açık kaynak lisansı atanmadı;
kaynak sahibinin yayın/lisans kararı korunur.
