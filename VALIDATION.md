# Doğrulama — 30 Eylül 2026

## Çalıştırılan kontroller

- Python 3.12.13 ortamında `uv run --frozen pytest -q`: **14 geçti**.
- Üç ayrı FastAPI uygulamasını ASGI transport ile bağlayarak local → aggregator →
  answer akışı; koordinatörün kendi local endpoint'ine katılımı, worker'da aggregator
  yasağı, node/query kimliği kontrolü ve body-byte sayaçları.
- Timeout, farklı embedding şeması, yanlış node kimliği, HTTP hatası, bozuk cevap:
  varsayılan strict 503, izin verilirse partial 200; tüm worker'lar başarısızsa 503.
- Kaynakları koruyan tekrar eleme ve skor sıralaması; boş prompt bütçesinde modelin
  çağrılmaması; dosya yükleme, yerel sorgu, API anahtarı ve boş soru doğrulaması.
- Qdrant adapter HTTP sözleşmesi: HTTP transport test taklidi istekleri gerçek
  `qdrant-client` embedded bellek veritabanına çevirir. İndeksleme, aynı belgenin
  tekrar yüklenmesinde idempotence, gerçek cosine vector search, servis restart ve
  kalıcı embedding şeması uyuşmazlığı kontrol edildi.
- 1/2/3 worker manifestlerinde aynı corpus SHA, ayrık dosya ataması ve tekrar eden
  dosyaların elenmesi.
- `compileall`: Python dosyaları derlenebilir.
- Dört node config'i Settings şemasıyla doğrulandı.
- `uv lock --check`: lock geçerli.
- Kopyalanan chunker ve extractors kaynak Belleq dosyalarıyla birebir aynı.

## Bu kontrollerin sınırı

- Ollama embedding/cevap üretimi testlerde kontrollü taklitlerdir; model indirilmedi.
- Qdrant'ın Linux sunucusu/container'ı çalıştırılmadı. Docker istemcisi var,
  Docker daemon bu oturumda çalışmıyor. Embedded test, gerçek sunucu entegrasyonunun
  yerine geçmez; REST ve client adapter sözleşmesini sınar.
- ASGI testler gerçek Ethernet/SSH trafiği değildir.
- Mac mini'lere bağlanılmadı; 8 GB bellek yeterliliği, GPU kullanımı, LAN throughput,
  launchd/Colima/Ollama reboot davranışı ve gerçek PDF retrieval kalitesi doğrulanmadı.
- Model atıf doğruluğu ve recall@k ground truth değerlendirmesi henüz yapılmadı.
- Oluşturulan servis bir laboratuvar başlangıç paketidir; canlı performans sonucu yok.

## Mini'lerde ilk kabul sırası

1. mini-2'de Qdrant + Ollama + API; `/health/ready` 200.
2. Küçük TXT yükle; `/query` ilgili parçayı ve skoru döndürsün.
3. Diğer worker'larda aynı digest ve schema; farklı belgeler yükle.
4. mini-1 aggregate: tüm node status'ları ok, sonuç kaynakları doğru.
5. Bir worker'ı durdur: strict 503 ve partial görünürlüğünü doğrula, tekrar başlat.
6. mini-1 answer: seçilen context_chunks ile cevabın kaynaklarını kontrol et.
7. SSH oturumunu kapat; API'nin erişilebilir kaldığını doğrula.
8. Wi-Fi kapalıyken aynı deney çalışsın (yönetim MacBook'undaki interneti koruyabilirsin).
9. 1/2/3 koşullarını yeni collection'lar ve aynı corpus manifestiyle ölç.
