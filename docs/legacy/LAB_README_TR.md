# Belleq Lab

Belleq'in belge alma ve retrieval çekirdeğinden türetilmiş bağımsız deney servisi.
Her mini kendi Qdrant verisini tutar. Koordinatör HTTP üzerinden yerel sorgu
API'lerini broadcast veya semantic sıralı modda çağırır, ortak top-k'yi oluşturur ve isteğe bağlı olarak
kanıtları Ollama'daki Qwen modeline gönderir. MCP, model bölme veya eğitim yoktur.

## Mimari ve kararlar

- `POST /query` ve `/v1/retrieve/local`: yalnızca bu mini'de arama.
- `POST /v1/retrieve/aggregate`: seçilen moda göre paralel veya erken duran sıralı arama.
- `POST /v1/answer`: aggregate + prompt'a kanıt ekleme + cevap üretimi.
- `POST /v1/documents/text`: JSON metin yükleme.
- `POST /v1/documents/upload`: PDF, DOCX, TXT, MD, HTML yükleme.
- `GET /health/live`, `/health/ready`: süreç ve bağımlılık kontrolleri.
- `/docs`: OpenAPI etkileşimli API belgesi.

Yeni mini-1 şablonunda semantic sıralı mod açıktır; eski config'ler broadcast kalır. İsteklerde `top_k` belirtilmezse yeni varsayılan 3'tür.

Varsayılan coordinator mini-1 (.11); arama düğümleri mini-2/3/4 (.12/.13/.14).
Mini-1'in yerel retrieval servisi de hazırdır. Kendi verisini de aramak için
`nodes` listesine `{"id":"mini-1","url":"http://192.168.50.11:8000"}` eklenebilir.
Koordinatöre geri dönen çağrı sadece `/v1/retrieve/local` olur; recursive aggregation yoktur.
İlk deneyde mini-1'i arama listesi dışında bırakmak, Qwen ile worker kaynaklarının
karışmasını azaltır. Yine de mini-1'de yerel Qdrant ve embedding modeli kurulur.

Bu Qdrant native cluster değil: bağımsız DB'lerin uygulama katmanında birleşmesidir.
Broadcast modunda bütün çalışanlara aynı soru gider. Semantic sıralı mod için [ROUTING.md](ROUTING.md) belgesine bak. Her worker kendi query
embedding'ini hesaplar. Dolayısıyla ölçülen süre embedding maliyetini de içerir;
`embedding_ms` ve `search_ms` ayrıdır. Embedding'i koordinatörde bir kere üretmek
ayrı bir sonraki deney olabilir; bu uygulama onu sessizce yapmaz.

## Mac mini kurulumu (her cihazda)

Önkoşul: macOS 14+, Apple Silicon, Python 3.12; mevcut lab macOS 26.2 uygundur.
Sabit Ethernet adresleri ve SSH hazır olmalı. Wi-Fi ilk indirmeler için açık kalabilir.

```bash
# SSH içinde Homebrew yolu görünmüyorsa:
eval "$(/opt/homebrew/bin/brew shellenv)"
brew install python@3.12 uv
```

### Ollama: macOS üzerinde yerel çalıştır

Resmî macOS uygulamasını https://ollama.com/download/mac adresinden yükle ve aç.
Ollama'yı Qdrant'ın Linux container'ına koyma; model servisi Mac üzerinde çalışsın.
Resmî platform desteği: https://docs.ollama.com/macos (Apple M serisinde CPU/GPU).
CLI kurulumunu ve API'yi kontrol et:

```bash
ollama --version
curl --fail http://127.0.0.1:11434/api/tags
ollama pull nomic-embed-text:latest
# Yalnızca koordinatörde; 8 GB için küçük başlangıç modeli:
ollama pull qwen3:1.7b
```

Bu pakette Ollama binary'si dağıtılmaz. Deney öncesi tüm cihazlarda aynı sürümü
kullan, `ollama --version` ve `/api/tags` çıktısını kaydet. Model etiketi değişebilir:
`/api/tags` içindeki embedding `digest` değerini dört config'in `embedding_digest`
alanına sabitle. Aynı tag altında farklı dosyalar varsa aggregator reddeder.
İlk başlangıçta digest boş bırakılabilir; gerçek digest otomatik okunur ve DB şemasına
kaydedilir. Daha sonra model değiştirmek için yeni collection kullanılır.

Varsayılan `keep_alive: 0` modelleri çağrı sonrası boşaltır: 8 GB bellek için temkinli
başlangıçtır, yükleme süresi embedding/generation süresine dahildir. Bu yüzden ilk
hız rakamları sürekli bellekte model tutan sistemlerle doğrudan karşılaştırılmaz.

### Qdrant: her mini'de ayrı Linux ARM64 container

Qdrant image sürümü `v1.13.3` olarak sabit. Python adaptörü REST query API kullanır.
Resmî kurulum/ARM64 desteği: https://qdrant.tech/documentation/installation/

Docker Desktop zaten varsa kullan. Yoksa hafif bir başlangıç seçeneği:

```bash
brew install colima docker docker-compose
colima start --cpu 2 --memory 2 --disk 20
```

2 GB VM, 8 GB mini için başlangıç bütçesidir; indeks boyutu büyüyünce ölçerek ayarla.
Docker Desktop ve Colima'yı aynı anda çalıştırma. Kullanılan Docker context'ini
`docker context show` ile doğrula. Aşağıda Homebrew `docker-compose` komutu kullanılır;
Docker Desktop'ta karşılığı `docker compose` olabilir.

### Depo ve servis

Uzak depo henüz atanmadı. Yayınlandıktan sonra seçilen URL'den clone edip proje
kökünde çalış. Her mini aynı Git commit'ini kullanmalı.

```bash
uv sync --frozen --no-dev --python /opt/homebrew/bin/python3.12
# Cihaza göre mini-1 / mini-2 / mini-3 / mini-4 seç:
cp config/mini-1.json config/local.json
docker-compose up -d
curl --fail http://127.0.0.1:6333/collections
.venv/bin/python -m belleq_lab
```

Son komut ilk doğrulama için ön planda çalışır. Startup embedding modelini,
vektör boyutunu ve Qdrant collection şemasını kontrol eder. Henüz model indirilmemişse
veya Qdrant yoksa başlamaz; yanlış indeksle sessizce arama yapmaz.
Ana API yalnızca config'teki Ethernet IP'sine bağlanır. Qdrant sadece localhost'a açıktır.
Ayrılmış lab ağı için API anahtarı varsayılan boş. Gerekirse bütün servisler ve
istemcilerde aynı `BELLEQ_API_KEY` ortam değişkenini ayarla; HTTP'de `X-API-Key` gönder.
TLS bu pakette yoktur, internet üzerinde açık yayın için tasarlanmamıştır.

## SSH kapanınca çalışmaya devam etme

Ön plandaki servisi Ctrl-C ile kapatıp:

```bash
.venv/bin/python scripts/service.py install
.venv/bin/python scripts/service.py status
curl --fail http://192.168.50.11:8000/health/ready
```

Her mini'de kendi IP'sini kullan. User LaunchAgent SSH oturumuna bağlı değildir;
yerel kullanıcı oturumu açıkken çalışır. Yeniden başlatma sonrası kullanıcı girişini,
Colima/Docker ve Ollama'nın açıldığını doğrula. Kullanıcı hiç giriş yapmadan boot'ta
çalışma bu paketin garantisi değildir. Bağımlılıklar geç açılırsa başarısız uygulama
30 saniyelik yeniden başlatma aralığıyla tekrar dener.

```bash
.venv/bin/python scripts/service.py stop
.venv/bin/python scripts/service.py start
# Config veya kod değişikliği: stop, ardından start.
tail -f logs/service.err.log
# Servis kaydını kaldırır; Qdrant verilerine dokunmaz:
.venv/bin/python scripts/service.py uninstall
```

Kalıcı veri Docker named volume'lerinde `qdrant_data` ve `qdrant_snapshots` bulunur.
`docker-compose stop` veri silmez. **`down -v` veriyi siler; normal durdurmada kullanma.**
Colima VM'sini silmek de içindeki volume'leri kaybettirir. Uzun deney öncesi snapshot
ve yedek planla. Loglar `logs/` altında büyür; deneyler arasında arşivle.

## MacBook'tan API kullanımı

```bash
# mini-2'ye bir belge:
curl --fail http://192.168.50.12:8000/v1/documents/upload \
  -F 'file=@/ABSOLUTE/PATH/example.pdf'

# JSON ile küçük belge:
curl --fail http://192.168.50.12:8000/v1/documents/text \
  -H 'Content-Type: application/json' \
  -d '{"text":"Belleq ilgili belge parçalarını getirir.","title":"Örnek","source":"example.txt"}'

# Yalnızca mini-2'de arama:
curl --fail http://192.168.50.12:8000/query \
  -H 'Content-Type: application/json' -d '{"query":"Belleq ne yapar?","top_k":5}'

# Bütün yapılandırılmış worker'larda arama:
curl --fail http://192.168.50.11:8000/v1/retrieve/aggregate \
  -H 'Content-Type: application/json' -d '{"query":"Belleq ne yapar?","top_k":5}'

# Sonucu prompt'a ekle ve Qwen'den cevap al:
curl --fail http://192.168.50.11:8000/v1/answer \
  -H 'Content-Type: application/json' -d '{"query":"Belleq ne yapar?","top_k":5}'
```

Node sonuçları `id`, `doc_id`, `text`, `score`, kaynak metadata'sı içerir. Aggregate
`locations` ile aynı parçanın diğer kaynaklarını korur. Metni birebir aynı olan
parçalar tekilleştirilir, yüksek skor korunur. `per_node_k` varsayılan `top_k`;
tekrarlar yüzünden sonuç sayısı az kalırsa açıkça daha yüksek `per_node_k` ver.
Embedding modeli/digest/boyut/mesafe/prefix/chunking uyuşmazlığı hata sayılır.

Worker başarısızsa varsayılan HTTP 503: `detail` içinde düğüm durumları ve alınabilen
sonuçlar bulunur. Açıkça `allow_partial:true` ile HTTP 200 kısmi sonuç alınabilir;
`partial:true` ve `failed_nodes` alanları kaybolmaz. Bütün düğümler başarısızsa
her durumda 503. Cevap üretimi hatası 502 döner ve retrieval sonucu korunur.

Prompt yalnızca seçilmiş metinleri içerir; numaralı kaynaklar `context_chunks` ile
birebir eşleşir. Bütçe karakter temellidir, kesin tokenizer hesabı değildir.
Çok uzun/özel token yoğun içerik için `context_chars` azaltılmalı. Qwen çıktısındaki
atıfların doğruluğunu bir değerlendirme kümesiyle ayrıca ölç.

## Aynı veriyle 1, 2, 3 worker deneyi

MacBook'ta da Python ortamını `uv sync --frozen --no-dev` ile kur. Her koşul için
**yeni collection** kullan; eski verinin koşullar arasında birikmesine izin verme.
Örnek bir-worker koşulu:

```bash
.venv/bin/python scripts/experiment.py --workers 1 --run trial01 --output data/n1
.venv/bin/python scripts/partition.py /ABSOLUTE/PATH/corpus \
  --nodes mini-2 --output data/manifest-n1.json
```

`data/n1/mini-N.json` dosyalarını ilgili mini'ye `config/local.json` olarak kopyala,
servisleri yeniden başlat. Örnek: `scp data/n1/mini-2.json USER@192.168.50.12:PATH/TO/REPO/config/local.json`.
Sonra:

```bash
.venv/bin/python scripts/ingest_manifest.py /ABSOLUTE/PATH/corpus data/manifest-n1.json \
  --config-dir data/n1 > data/ingestion-n1.jsonl
.venv/bin/python scripts/benchmark.py \
  --url http://192.168.50.11:8000/v1/retrieve/aggregate \
  --queries data/questions.txt --repeat 3 --concurrency 1 --output data/results-n1.jsonl
```

İki worker için `--workers 2`, `--nodes mini-2 mini-3`; üç için `--workers 3`,
`--nodes mini-2 mini-3 mini-4`. Her koşula ayrı çıktı klasörü/manifest ver.
Corpus SHA aynı kalmalı. Dağıtım belge bazında, SHA sıralı round-robin;
**belge sayısını dengeler, chunk sayısını garanti etmez.** Yükleme çıktılarındaki
chunk sayılarıyla dengesizliği raporla. Birebir aynı dosyalar bir kez alınır.
Düzenlenmiş belge yeni içerik kimliği alır; eski sürümü otomatik silmez. Bu yüzden
her deney koşulunda yeni collection kullanmak şarttır.

Qdrant indekslerinin hazır olmasını bekle; yükleme sırasında benchmark çalıştırma.
Aynı soruları, top-k'yi, modeli, prefix'leri ve concurrency'yi koru. İlk turu
ısınma olarak ayrı raporla. p50/p95 süreleri yanında hata oranı ve arama kalitesini
(recall@k / kaynak doğruluğu) raporla. ANN ve düğüm sınırları sonucu etkileyebilir;
eşit hız tek başına yeterli değildir. Ground-truth kalite değerlendirmesi henüz eklenmedi.

Belleq yaşam döngüsü, kayıt yakalama ve uygulama retrieval cache'i yok. Qdrant/OS
cache'leri vardır; bu sonuçları 'tamamen cold cache' diye etiketleme.

## Ölçümler ve offline çalışma

- Worker: readiness, embedding, vector search ve toplam süre.
- Aggregator: her worker'ın round-trip süresi, fan-out, merge ve toplam süre.
- Answer: generation ve end-to-end süre.
- Trafik: worker HTTP istek/yanıt gövdelerinin UTF-8 byte miktarı. Başarısız çağrıda
  request bytes hazırlanan gövde boyutudur, teslim edildiğinin kanıtı değildir.
  HTTP header/TCP/Ethernet overhead ve worker↔Ollama/Qdrant trafiği dahil değildir.
- Query ID bütün worker çağrılarına yayılır; JSON ölçümleri loglara yazılır.

Gerçek ağ trafiği için ilgili Ethernet arayüzünde ayrıca packet capture / arayüz
sayaçları kullan. SSH ve indirme trafiğini ayrı tut. MacBook adaptörünün 100 Mbps
olduğu önceki kurulumda görüldü; mini-mini link hızlarını ayrıca kaydet.

Offline kullanımdan önce her mini'de `uv sync`, Docker image pull, embedding pull;
mini-1'de generation pull tamamlanmalı. `uv.lock` ve hash'li `requirements.lock.txt`
tüm Python bağımlılıklarını sabitler. Hazır `.venv`, Docker volume ve Ollama
modellerini koruyarak çalışma sırasında download yapılmaz. Cold offline yeniden
kurulum için ayrıca wheelhouse, image export ve model dosyası yedeği gerekir;
bu paket büyük model dosyalarını içermez.

## Kaynak ve testler

`PROVENANCE.md` yeniden kullanılan kaynakları; `VALIDATION.md` gerçek doğrulama
kapsamını içerir. Test çalıştırmak için:

```bash
uv sync --frozen
uv run --frozen pytest -q
```

Bu ilk teslim çalışan mini kümesi üzerinde doğrulanmış bir performans sonucu değildir.

## Deney ölçümleri

Kategorik yerleşimde sorgu ve mini bazlı kalite/süre CSV'leri, paket kaydı ve
Wireshark/TShark trafik analizi için [EVALUATION.md](EVALUATION.md).
Dokuz soruluk set yalnızca etiketleri gözden geçirilecek bir pilot settir.
