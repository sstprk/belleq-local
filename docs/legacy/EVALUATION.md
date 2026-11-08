# Dağıtık retrieval deneyi — başlangıç: kategorik yerleşim

## Ölçüm sözleşmesi

Bu paket **retrieval** ölçer; cevap üretim modelini çalıştırmaz. Ağda LLM üretim
trafiği ve üretim süresi bu deneyin parçası değildir. Aynı sorgu kümesi, korpus,
embedding fingerprint, chunking, `top_k`, `per_node_k`, eşik ve tekrar sayısı
senaryolar boyunca korunmalı. Her bağımsız tekrar grubunu ayrı klasöre kaydet.

| Deney | Yerleşim | Arama |
|---|---|---|
| categorical / semantic_sequential | mini-2 Frankenstein, mini-3 Hound, mini-4 Persuasion | Sırayla, erken durma |
| categorical / broadcast | Aynı kitaplar ve yerleşim | Üçüne paralel; yönlendirme kontrolü |
| random_chunks / broadcast | Aynı **parçalar** üç mini'ye sabit seed ile dağıtılacak | Üçüne paralel |
| single_db / broadcast | Aynı parçaların tamamı tek worker mini'de | Koordinatörden tek worker'a |

İkinci/üçüncü yerleşim bu değişiklikle oluşturulmadı; `--scenario` yalnızca etikettir,
verileri taşımaz. Eski `partition.py` dosya bazlı dağıtır, **rastgele parça dağıtımı değildir**.
Parçaları yeniden birleştirip tekrar chunk etmek yerine aynı metin/hash'leri korumak gerekir.
Tek DB'yi worker üzerinde tutmak koordinatör–worker ağ yolunu korur. DB'yi koordinatörle
aynı makineye koyarsan bunu ayrı yerel senaryo say: loopback Ethernet'te görünmez.

## Doğruluk

`evaluation/pilot/queries.jsonl`: üç kitaptan toplam 9 soru ve cevap kanıtı hash'leri.
`evidence-review.json`: bu hash'lerin tam parça metinleri; `corpus.json`: yüklenen
kitapların byte hash'leri, doc_id'leri ve 1278 / 1098 / 1388 parça sayıları.

Bu **taslak/pilot** bir settir. Kaynakta seçilen kanıt pasajları otomatik eşleştirildi;
alternatif geçerli pasajlar eksik olabilir. Metinleri incele, diğer geçerli kanıt
hash'lerini ekle, sonra ilgili soruda `reviewed: true` yap. Soru metinleri node
kataloguna eklenmemeli. Etiketleri sistemin getirdiği ilk sonuca göre seçmeyin.
Yayımlanacak deney için daha fazla ve dengeli soru gerekir; 9 soru tesisat kontrolüdür.
Model yanıtı veya cosine skoru gold label değildir.

- `hit_at_k`: seçilen ilk k parçada en az bir etiketlenmiş kanıt varsa 1.
- `miss_at_k`: başarılı tam retrieval'da hit yoksa 1; oranı sorular üzerinden hesaplanır.
- `precision_at_k`: farklı ilgili parça sayısı / k (eksik sonuç slotları sıfır).
- `judged_recall_at_k`: bulunan farklı etiketli parçalar / tüm etiketli parçalar.
- `reciprocal_rank_at_k`: ilk ilgili parçanın sırasının tersi; ortalaması MRR@k.
- `judged_ndcg_at_k`: binary relevance ile sıralama; etiketler eksikse nihai NDCG değildir.

Hata/partial, içerik miss'i olarak maskelenmez. Özet hem başarılı tam sorgulardaki
kaliteyi hem `all_attempt_hit_rate` (hata ve partial girişimleri sıfır başarı)
sonucunu verir. Skipped node kalite paydasına girmez. Node kalitesi global kanıt
kümesine göre **çağrılan mini'nin eşikten geçen adaylarının ilk k'sidir**; o mini'de
cevap zaten yoksa hit=0 olması node arızası anlamına gelmez. Rastgele dağılımda
node-yerel recall hesaplamak için ayrıca parça yerleşim manifesti gerekir.

## API değişikliği

Koordinatör, zaten aldığı worker sonuçlarının hash/id/score bilgilerini
`nodes[].candidates` içinde döndürür. Böylece node adaylarını ölçmek için ek API
isteği gönderilmez ve worker'a giden/gelen gövde değişmez. Koordinatörün istemciye
verdiği yanıt biraz büyür; bütün senaryolar aynı sürümle ölçülmeli.
Eski koordinatörde bu alan yoksa node kalite metrikleri boş bırakılır, uydurulmaz.
Worker kodu ve veritabanı değişmedi. Güncel kodu koordinatöre çekip API'yi yeniden başlat.

## Kategorik pilotu çalıştırma

Önce koordinatörde repo içinde API'nin başka terminalde çalıştığından emin ol.
Deney sürücüsünü **mini-1 üzerinde** çalıştır: paket kaydıyla aynı saat kullanılır.
Sunucu kayıtlarından/readiness'ten dört node yapılandırmasını, koleksiyon adlarını,
model fingerprint'ini ve kitap sayımlarını ayrıca deney klasöründe sakla.

Mini-1'de ayrı SSH terminalinde Ethernet arayüzünü öğren:

```bash
route -n get 192.168.50.12
```

`interface:` karşısındaki değeri kullan; `en0` olduğunu varsayma.
Aşağıdaki `ETHERNET_INTERFACE` yerine bu değeri yaz. Qdrant ve Ollama localhost
trafiği hariç yalnızca deney API'sinin Ethernet trafiğini yakalıyoruz.

```bash
mkdir -p results/captures
sudo tcpdump -i ETHERNET_INTERFACE -n -s 0 -B 4096 \
  -w results/captures/categorical-routed.pcap \
  'tcp port 8000 and net 192.168.50.0/24'
```

Kaydı açık bırak. Mini-1'de diğer SSH terminalinde, repo içinde:

```bash
.venv/bin/python scripts/evaluate.py \
  --scenario categorical --mode semantic_sequential \
  --queries evaluation/pilot/queries.jsonl \
  --top-k 3 --per-node-k 5 --min-score 0.70 \
  --warmup 1 --repeat 5 --seed 42 --allow-draft \
  --output results/categorical-routed
```

54 istek: 9 ısınma + 45 ölçüm. İstemci eşzamanlılığı 1; sorgu sırası sabit seed ile
karıştırılır. Isınma katalog embedding'ini kurar; mevcut Ollama `keep_alive: 0`
politikası değişmez, modelin bellekte tutulduğu iddia edilmez. `--allow-draft`
yalnızca pilot içindir. 0.70'i tek soruyu başarılı göstermek için sonradan değiştirme;
eşik taraması yapılacaksa her eşiği ayrı, önceden belirlenmiş deney olarak kaydet.

Deney bitince tcpdump terminalinde `Ctrl+C`. Ekrandaki **packets dropped by kernel**
sayısını not et; sıfır değilse trafik sonuçlarını eksiksiz kabul etme.
Dosyayı silme: asıl ağ kanıtı PCAP'tir. Ayrı kayıtta aynı komutu
`--mode broadcast --output results/categorical-broadcast` ile tekrarla;
capture adına da `categorical-broadcast.pcap` ver. Tekrar gruplarında çalışma
sırasını dönüşümlü kullan (routed/broadcast, sonra broadcast/routed).

`queries.csv`: query_id, hit/miss, kalite, istemci/router/aggregate süreleri.
`nodes.csv`: query_id + node_id, visited/skipped/error, node kalite,
embedding/search/API round-trip, uygulama gövde byte'ları.
`raw.jsonl`: tam istek/yanıt, başlangıç/bitiş epoch; hatalar ve ısınma dahil.
`summary.json`: başarı/hata sayıları, ortalamalar, p50/p95 ve node özetleri.
`manifest.json`: senaryo etiketi, parametreler, seed ve soru-seti hash'i.
Çıktı klasörü varsa araç üzerine yazmaz. `results/` Git'e dahil edilmez.

## Ağ analizi

Normal switch portuna bağlı MacBook, mini'ler arası unicast trafiğin tamamını
göremez. Bu yıldız biçimindeki API akışında **mini-1 Ethernet kaydı** .12/.13/.14
ile bütün retrieval bağlantılarını kapsar. Her mini'de ayrıca capture alınabilir;
ama aynı paketler birden fazla dosyada görüneceğinden bu kayıtları toplayıp toplam
trafik hesaplama. Switch port-mirroring varsa alternatif gözlem noktası olabilir.

PCAP ve deney klasörünü MacBook'a al (kullanıcı/SSH erişimi mevcut):

```bash
scp ios-lab01@192.168.50.11:PATH_TO_REPO/results/captures/categorical-routed.pcap .
scp -r ios-lab01@192.168.50.11:PATH_TO_REPO/results/categorical-routed .
```

MacBook'taki repo içinde (PCAP ve run yollarını kopyaladığın konuma göre yaz):

```bash
.venv/bin/python scripts/network_report.py \
  --pcap categorical-routed.pcap --run categorical-routed \
  --output results/network-categorical-routed
```

MacBook'ta mevcut Wireshark TShark yolu varsayılandır;
farklı kurulum için `--tshark /path/to/tshark` ver. PCAP Wireshark GUI'de de açılır.

- `network.json`: mini-1..4 için TX/RX frame byte, paket sayısı, ölçüm penceresinde
  ortalama TX/RX Mbps, ACK RTT p50/p95, HTTP yanıt süresi ve retransmission işaretleri.
- `network_queries.csv`: aynı değerlerin query_id bazında pencere özetleri;
  `nodes.csv` ve `queries.csv` ile birleştirilebilir.
- `packets.tsv`: Wireshark alanlarının ham çıktısı, inceleme için.

TCP ACK RTT (`tcp.analysis.ack_rtt`) tek yön gecikme değildir; host ACK davranışını
ve yakalama noktasını içerir. HTTP süre (`http.time`) ve API round-trip embedding/DB
çalışmasını da içerir. `frame.len` fiziksel kablo yükünün birebir ölçümü değildir
(preamble/IFG/FCS ve offload etkileri); gövde byte'larıyla ayrı raporlanır.
Throughput bu deneyde gözlenen hızdır, ağın maksimum kapasitesi değildir.
Retransmission işaretleri paket kayıp oranının doğrudan ölçümü değildir.

Node TX+RX değerleri toplanınca aynı mini–mini paketi iki kere sayılır.
Toplam için tek capture'daki `unique_captured_bytes` kullan. Aranmayan node için
ölçüm penceresinde 0 byte olabilir; RTT örneği yoksa boş/null'dur, 0 ms değildir.
Sorgu pencereleri handshake/son ACK gibi dışarı taşan paketleri kaçırabilir;
trafik karşılaştırmasında **run toplamını** esas al. Saat eşleme problemini önlemek
üzere evaluator ve capture mini-1'de çalışır; eşzamanlı istemci/arka plan API
isteği açma. Ethernet'te hiç paket görünmezse capture/arayıüzü doğrulamadan bunu
“sıfır ağ maliyeti” diye sunma. Capture drop sayısı ve link hızı ayrıca kaydedilmeli.

Kaynaklar: [TShark kullanım belgesi](https://www.wireshark.org/docs/man-pages/tshark.html),
[TCP alanları](https://www.wireshark.org/docs/dfref/t/tcp.html).
