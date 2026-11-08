# Sonuç kaydı — Belleq Simulator v0.1

Bu rapor kaydedilen değerlendirme tablolarından üretilmiştir. v0.3 arayüzü İngilizce, markasız ve yeni kullanıcılar için açıklamalıdır; CSV/JSON indirmeleri hazırdır. v0.1 model ve aşağıdaki eğitim/test sonuçları değişmedi. CLI ve localhost HTTP API de hazırdır.

## Gerçek veri

Ana veri 500 soru × 4 yöntem = 2.000 gerçek deneme; 1.998 tamamlandı. 12 kitap / 16.421 parça. .80 koşuları ek kaynak olarak saklanır; ana kalibrasyon .70 eşiklidir. Rastgele senaryo veri yerleşimini değil ziyaret sırasını değiştirir.

| Yöntem | Tamamlanan | Referans hit | Ortalama retrieval ms | Ortalama frame bayt/sorgu |
|---|---:|---:|---:|---:|
| semantic_sequential | 498/500 | 204/500 | 952.4 | 12346.1 |
| broadcast | 500/500 | 214/500 | 338.6 | 18560.1 |
| random_sequential | 500/500 | 207/500 | 727.9 | 14474.8 |
| single_db | 500/500 | 213/500 | 310.4 | 6147.4 |

## Ayrılmış sorularda dağılım doğrulaması

300 soru eğitim, 100 doğrulama, 100 son test. Kullanımdaki modeller ilk 400 sorudan kalibre edildi. Son 100 soru bütün türetilmiş örnekleriyle dışarıda tutuldu. Aşağıdaki sonuçlar 10.000 Monte Carlo çekilişinin ortalamasını gerçek test ortalamasıyla karşılaştırır.

| Yöntem | Hedef | Simülasyon ortalaması | Test ortalaması | Ortalama farkı % | p95 farkı % |
|---|---|---:|---:|---:|---:|
| semantic_sequential | aggregate_ms | 948.20 | 979.38 | -3.18 | -0.09 |
| semantic_sequential | network_frame_bytes | 12226.47 | 12941.76 | -5.53 | -0.57 |
| semantic_sequential | client_ms | 2866.94 | 3130.28 | -8.41 | -8.67 |
| broadcast | aggregate_ms | 338.78 | 338.13 | +0.19 | +0.44 |
| broadcast | network_frame_bytes | 18566.47 | 18539.31 | +0.15 | +0.79 |
| broadcast | client_ms | 2250.34 | 2502.01 | -10.06 | -6.01 |
| random_sequential | aggregate_ms | 720.97 | 750.92 | -3.99 | -0.09 |
| random_sequential | network_frame_bytes | 14266.54 | 14974.37 | -4.73 | -1.61 |
| random_sequential | client_ms | 2544.35 | 2777.70 | -8.40 | -2.28 |
| single_db | aggregate_ms | 310.58 | 310.04 | +0.18 | +0.03 |
| single_db | network_frame_bytes | 6138.99 | 6178.79 | -0.64 | -0.51 |
| single_db | client_ms | 2188.26 | 2409.08 | -9.17 | -4.42 |

Retrieval ortalaması ve trafik ortalaması mevcut koşullarda makul biçimde yeniden üretilmiştir. Bu dağılım başarısı, tek bir sorgunun doğru süreyle tahmin edildiği veya yeni düğüm sayısının doğrulandığı anlamına gelmez. Uçtan uca ortalamalarda hata daha büyüktür; üretim süresi ve soru iş yükü dağılımı önemlidir.

## Regresyon karşılaştırması

| Hedef | Doğrulamada seçilen model | Test baseline MAE | Test Ridge MAE | Seçilen model test R² |
|---|---|---:|---:|---:|
| aggregate_ms | method_mean | 132.88 | 141.71 | 0.665 |
| network_frame_bytes | method_mean | 2567.26 | 2693.64 | 0.589 |
| client_ms | ridge | 801.29 | 793.51 | 0.025 |

Retrieval ve trafik için Ridge yöntem ortalamasını geçmedi. Bu iki hedefte nokta tahmini yönteme göre ortalama; dağılım tahmini ampirik Monte Carlo kullanır. Client süresinde Ridge küçük farkla seçildi, fakat test R² çok düşüktür; güçlü soru bazlı üretim süresi tahmini iddia edilemez. Yöntem bazında R² değerleri de çoğunlukla negatiftir; toplu R² esas olarak yöntemler arasındaki farkı yansıtır. Bütün başarısız/olumsuz karşılaştırmalar korunmuştur.

## Replay ve augmentation

- 1.998 başarılı orijinal kayıtta ziyaret sırası ve dönen hash listesi birebir yeniden üretildi. Bu algoritma doğrulamasıdır.
- 500 soru × 6 ziyaret sırası = 3.000 türetilmiş sıra kaydı oluşturuldu; split ve kaynak case_id saklanıyor.
- Kalibrasyonda yalnızca ilk 400 sorunun izleri var. 100 test sorusunun türevleri kullanım havuzuna girmez.
- Bu 3.000 satır bağımsız fiziksel deney değildir; sentetik süreler Ridge için gerçek eğitim hedefi yapılmadı.
- .65/.70/.75/.80 eşikleri ilk beş aday üzerinde karşı olgusal olarak yeniden oynatıldı; yeni cevap üretilmedi.

## Düğüm sayısı ve ağ varsayımları

1, 2, 3, 4, 6, 8, 12, 16 sanal arama düğümü için üç yöntemin eğrileri kaydedildi. Bunların tümü varsayım modudur. Bir sahip + N−1 dikkat dağıtıcı profil, sabit örneklenmiş düğüm maliyetleri ve semantik owner-first=.57 varsayımı kullanılır. Gerçek veri bölüşümü, veri büyüklüğü veya sabit corpus ölçeklenmesi öğrenilmiş değildir.

Yeni düğüm sayıları için hit oranı verilmez. Kuyruk, kapasite, yoğun sorgu yükü ve WAN tıkanması modellenmez. Daha hızlı ağdan kazanç çıkarılmaz; seçilen daha yavaş link için yalnızca varsayımsal ek aktarım süresi eklenir.

## Doğrulama ve dosyalar

- 13 sayısal/akış/veri ayrımı testi geçti; 8 gerçek localhost API kontrolü geçti.
- 132 ham girdi dosyasının SHA-256 değeri tekrar doğrulandı.
- İki arşiv PCAP dosyasından 2.000 sorgunun frame baytları bağımsız olarak yeniden hesaplandı; bütün CSV satırları eşleşti (`results/pcap_audit.json`).
- Beş şekil PNG ve PDF olarak kaydedildi; her birinin açıklaması ve sayısal kaynak tablosu var.
- Resmî Ridge, grouped split, bootstrap ve extrapolation kaynakları URL ve HTML kopyalarıyla arşivlendi.
- Kilitli paketler yeni, geçici bir Python ortamına yalnızca yerel wheel dosyalarından kuruldu; model yükleme ve simülasyon başarılı oldu (`results/offline_installation.json`).
- Ağ kapsamı koordinatörün yakalanan frame baytlarıdır; toplam fiziksel Ethernet yükü değildir.
- Eski yakalamada kernel drop bilgisi bilinmiyor; son yakalamada 0 drop ve bütün istek/yanıt eşleşmesi var.
- Saat/oturum etkisi, sentetik ve eksik referanslar, tek tekrar ve concurrency=1 sonuçların sınırlarıdır.

## Makalede kullanılabilecek ifade

> Mevcut donanım ve iş yükünde, soru düzeyinde ayrılmış bir test üzerinde kalibre edilmiş ampirik simülatör, yöntemlerin ortalama retrieval gecikmesini ve sorgu başına yakalanan ağ trafiğini yakın biçimde yeniden üretmiştir. Ölçülmemiş düğüm sayıları için sunulan sonuçlar açık varsayımlara dayalı senaryo analizidir; fiziksel ölçeklenme doğrulaması yapılmamıştır.

## Sonraki deneyler

Öncelik daha fazla aynı-tip soru yerine kontrollü kurulum çeşitliliğidir: aynı corpus üzerinde 1/2/3 ve daha fazla gerçek arama düğümü; ayrı olarak düğüm başına veri sabit büyüme; artan eşzamanlı yük; yöntem sırası değiştirilmiş bağımsız tekrar oturumları. Yeni verilerle düğüm sayısı, veri büyüklüğü ve yük etkileri birbirinden ayrılmalıdır.
