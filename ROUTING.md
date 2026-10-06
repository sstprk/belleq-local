# Semantic sıralama ve erken durma — 6 Ekim 2026

İstenen davranış: soruya göre kitapların sırasını belirle, ilk worker'ı ara;
eşik üstünde toplam 3 farklı metin parçası bulunduğunda dur. Yetmezse ikinciye,
gerekirse üçüncüye geç. Router için Qwen/LLM çağrısı yoktur.

## Çalışma

- Koordinatör her node'un `description` alanını document prefix ile embed eder.
  Bu katalog vektörleri ilk semantic istekte bir kez üretilir, süreç belleğinde tutulur.
- Soru, aynı embedding modeli ve query prefix ile embed edilir.
- Cosine benzerliği ile node sırası belirlenir. Router skoru parça skoru değildir.
- Sırayla mevcut `/v1/retrieve/local` endpoint'i çağrılır.
- `min_score` altındaki veya boş parçalar elenir; birebir aynı metinler tekilleştirilir.
- Birden fazla node'dan gelen parçalar birikir. Toplam `top_k` farklı parça varsa
  kalan node'lara HTTP isteği gönderilmez. Örneğin 2 + 1 parça yeterlidir.
- Kalan bütün node'lar da bittiğinde 3'ten az parça varsa bulunanlar döner;
  `target_reached:false` açıkça raporlanır. Bu tek başına transport hatası değildir.
- Yanıt vermeyen/uyumsuz node atlanıp sıradaki denenir. `allow_partial:false` ise
  visited node hataları sonuçta 503 kalır. Atlanan (hiç sorulmayan) node hata değildir.
- Worker protokolü değişmedi; bu özellik için yalnızca koordinatör güncellenebilir.
  Worker hâlâ kendi query embedding'ini üretir. Router ek embedding maliyeti getirir;
  vektörü bir kere üretip worker'lara iletme optimizasyonu bu değişiklikte yoktur.

`relevance_threshold:0.70` **kalibre edilmemiş başlangıç değeridir**. Cosine skoru
cevap doğruluğu veya olasılık değildir. Önceki canlı örnekte ilgisiz parçalar 0.77,
cevap içeren bazı parçalar 0.69 civarındaydı. Dolayısıyla sistem istenen durma
mekanizmasını uygular; semantik olarak üç doğru kanıtı garanti etmez. Ayrı bir
kalibrasyon kümesiyle eşiği seç, test sorularını/eşiği sonuca göre sürekli değiştirme.
Katalog açıklamaları genel kitap bilgisi içerir; önceki baston sorusuna özel anahtar
ifadeler eklenmedi. Kitaplar farklı node'lara taşınırsa açıklamaları da güncelle.

## Mevcut koordinatörde etkinleştirme

Önce değişikliği Git'e gönder ve mini-1'de `git pull --ff-only` yap.
Açık API sürecini Ctrl-C ile durdur; proje klasöründe:

```bash
.venv/bin/python scripts/enable_routing.py
.venv/bin/python -m belleq_lab
```

Script yalnızca node açıklamalarını, retrieval modunu ve eşiği günceller; IP,
collection ve model ayarlarını korur. `config/local.json.before-routing` yedeği
oluşturur. Yedek zaten varsa tekrar yazmaz. LaunchAgent kullanıyorsan stop/start
komutlarını kullan. Yeni Python bağımlılığı, yeni vektör koleksiyonu veya kitapları
yeniden embed etme gerekmiyor.

Varsayılan hedef 3. Önce Qwen olmadan arama testi:

```bash
curl --fail-with-body http://192.168.50.11:8000/v1/retrieve/aggregate \
  -H 'Content-Type: application/json' \
  -d '{"query":"What does Holmes learn about the Baskerville family?","mode":"semantic_sequential","top_k":3,"per_node_k":5,"min_score":0.70}'
```

Cevap için aynı body'yi `/v1/answer` endpoint'ine gönder. Karşılaştırmada yalnızca
modu `broadcast` yap ve min_score/top_k/per_node_k'yi aynı tut. Rastgele dağıtımda
kitap→node kataloğu geçersiz olacağı için broadcast seç.

## Yanıttaki yeni alanlar

- `routing.ranking`: bütün node'ların sırası ve routing skorları.
- `routing.visited_nodes`, `skipped_nodes`: sorgulanan ve hiç sorgulanmayan node'lar.
- `routing.min_score`, `target_chunks`, `target_reached`, `stop_reason`.
- `routing.catalogue_built`: bu istekte katalog ilk kez oluşturuldu mu?
- `nodes[].returned_chunks`, `accepted_chunks`: eşik filtresinin etkisi.
- `timings.router_ms`, `catalogue_embedding_ms`, `router_query_embedding_ms`.
- `aggregate_ms`: router süresi dahil. `fanout_ms`: worker sorgu aşaması
  (semantic modda sıralı çağrıların ve ara tekilleştirmenin toplamı).
- Trafik yalnızca gerçekten denenmiş worker çağrılarının HTTP body boyutlarıdır;
  koordinatörün localhost embedding trafiği Ethernet yüküne eklenmez.

İlk istek katalog maliyetini içerir; sıcak/soğuk ölçümleri ayır. Şu an kitap
kataloğu bellekte; servis restart sonrası yeniden hazırlanır. Sorgu sonucu cache'i yoktur.

## Test kapsamı

27 test: önceki 14 + semantic ilk-node erken durma, çok-node birikim ve dedup,
eşik altı reddetme, yetersiz kanıt, timeout/HTTP/schema hatalarında fallback ve
strict/partial davranışı, broadcast override, katalog cache'i, eksik metadata,
geçersiz cosine vektörleri. Bunlar kontrollü embedding'lerle uygulama testleridir;
gerçek kitap sıralaması, eşik başarısı ve hız mini'lerde henüz ölçülmedi.
