# Yöntem kaydı — v0.1

## Araştırma kapsamı

M2 8 GB Mac mini tabanlı, uygulama katmanında dağıtık RAG retrieval. Koordinatör ayrı; 3 bağımsız arama düğümü ve tek arama düğümlü bütün veri karşılaştırması. Qdrant native cluster, dağıtık model eğitimi veya model sharding yoktur.

12 roman, 16.421 canonical parça ve 500 aynı sentetik soru kullanıldı. Dağıtık yerleşim kategoriktir. `random_sequential`, kategorik yerleşimde rastgele ziyaret sırası demektir; rastgele veri yerleşimi deneyi değildir. Tek DB, birebir kopyalanmış canonical vektörleri içerir. Ayrıntı ve kopyalama doğrulaması `data/raw/oct14/consolidation.json` içindedir.

## Veri seçimi ve ayrım

Ana veri: .70 eşikte 4 yöntem × 500 soru = 2.000 deneme. İki HTTP 503 kaydı korunur; başarılı süre modeli bu iki kayıttan eğitilmez. Ampirik havuz bunların gözlenen başarısızlık davranışını korur; yeni failure/timeout dağılımı öğrenildiği iddia edilmez. Başarısızlıkların model havuzundaki sayısı split'e bağlıdır. .80 koşularındaki 1.000 deneme ana karşılaştırmadan ayrı yardımcı kaynak olarak saklanır.

Seed 20261020 ile alfabetik case_id listesinin karıştırılması: 300 eğitim, 100 doğrulama, 100 son test sorusu. Her sorunun bütün yöntem kayıtları ve türetilmiş sıra örnekleri aynı taraftadır. Ridge hiperparametresi ve baseline seçimi ilk 300/100 ayrımıyla yapılır. Seçilen model 400 soruyla yeniden kalibre edilir; son 100 soru kullanıma açılan modelin havuzuna girmez. Son testin 400 yöntem gözlemi tamamlanmıştır; iki hata ilk 400 soruluk gruptadır.

Bu soru genellemesi testidir. Yeni oturum, kitap, donanım veya düğüm sayısına genelleme testi değildir. Oturum ile yöntem kısmen karışıktır; aynı yöntem için bağımsız tekrar koşuları yoktur.

## Eğitilen modeller

Standartlaştırılmış girdilerle Ridge, NumPy normal denklemi kullanılarak uygulandı:

`argmin ||y - Xw - b||² + alpha ||w||²`

Sabit terim cezalandırılmaz. Standartlaştırma eğitim verisinden öğrenilir. Alpha adayları: .1, 1, 10, 100, 1000. Seçim doğrulama MAE'sine göre yapılır. Baseline, yöntem başına eğitim ortalamasıdır. Model JSON olarak saklanır; pickle kullanılmaz.

Girdiler: dört yöntem göstergesi, soru UTF-8 bayt sayısı ve kelime sayısı. Gerçekleşmiş ziyaret sayısı, skor, hit, cevap uzunluğu ve sonuç boyutu kullanılmaz. Bunları doğrudan girdi yapmak senaryo tahmininde gelecekte bilinmeyen bilgiyi sızdırırdı.

Hedefler: aggregate retrieval ms, koordinatörde yakalanan sorgu penceresi frame baytları, client uçtan uca ms. Düğüm sayısı/veri büyüklüğü/ağ kapasitesi farklı yöntemlerden bağımsız değişmediği için bu değişkenlerin katsayısı öğrenilmez. Ana süre ve trafik motoru ampirik Monte Carlo'dur; Ridge karşılaştırması başarısız olsa da raporda tutulur.

## Monte Carlo

Kalibrasyon havuzundan bir sorunun yöntem kaydı bütün olarak seçilir. Trafik, ziyaret sayısı, retrieval, üretim ve etiket aynı örnekte kalır. 10.000 çekilişle dağılım özeti üretilir. Bu yeni gerçek gözlem veya yeni sistem bilgisi üretmez.

Ortalama, medyan, p05 ve p95 raporlanır. Bunlar sorgu değişkenliğini gösterir. Ayrı olarak 2.000 soru-bootstrap tekrarıyla ortalama için %95 percentile CI kaydedilir. Bu aralık oturumlar arası değişkenliği veya ölçülmemiş sistem varsayımlarını kapsamaz.

Son test değerlendirmesi, simüle dağılımın ortalama ve p95 değerlerini 100 ayrılmış sorunun gerçek ölçümleriyle karşılaştırır. Ortalama hatasının küçük olması her bir sorunun gecikmesinin doğru tahmin edildiği anlamına gelmez. Yöntemleri birlikte hesaplanan R², yöntemler arası farktan yükseldiği için yöntem bazındaki metrikler ayrıca verilir.

## Replay ve augmentation

Her başarılı orijinal kayıttaki aday listesi, skor >= eşik, canonical content hash ile tekrar eleme, skor azalan / parça kimliği artan sıralama ve global top-k kurallarıyla yeniden oynatılır. Sıralı yöntemler k benzersiz parça bulunduğunda durur. Bu bir yazılım doğrulamasıdır; modelin dış veri başarısı değildir.

Paralel koşunun her soru için üç düğümden gelen adayları vardır. Altı olası ziyaret sırası hesaplanır: 500 × 6 = 3.000 türetilmiş sıra. Her satır kaynak case_id, split ve sentetik etiket taşır. Test sorusundan türetilen satır kalibrasyona girmez. Ridge, sentetik gecikme hedeflerine eğitilmez. Artırılmış satırlar 3.000 bağımsız deney olarak raporlanamaz.

Eşik/top-k replay'i kaydedilmiş ilk beş adayla sınırlıdır. Yeni ANN araması, daha geniş aday havuzu, rastgele parçalı veri yerleşimi veya yeniden üretilmiş cevap doğruluğu vermez. Maliyet için eski paralel koşunun düğüm round-trip değerleri kullanılır; sonraki oturumdaki hız değişimi aktarılmaz. Frame tahmini, aynı yöntem/soru için kalibre edilmiş query frame/body oranıyla yapılır; paket düzeyinde yeniden oluşturma değildir.

## Düğüm sayısı varsayımları

Varsayım motoru tek kaynak sahibi + N−1 dikkat dağıtıcı sanal düğüm profili kullanır. Her profil aynı kaydın ölçülen süre, skor ve mesaj boyutlarını taşır. Sanal düğüm kimlikleri ve içerik hash'leri ayrı ad alanına alınır. Böylece kopya profil kullanmak yanlışlıkla tek aynı fiziksel içerikmiş gibi tekrar eleme yaratmaz; ancak gerçek veri çoğaltma/bölüştürme modeli de değildir.

Sıralı süre router + ziyaret edilen düğüm süreleri toplamıdır; paralel süre en büyük düğüm süresidir. Varsayımsal ortak link aktarım ek maliyeti toplam frame baytları üzerinden bir kez eklenir. Yeni CPU, veri büyüklüğü, arama karmaşıklığı, sorgu kuyruğu, QPS kapasitesi veya WAN tıkanması öğrenilmez. Semantik kaynak sahibini ilk seçme olasılığı kullanıcı varsayımıdır. Bu mod kalite/hit oranı döndürmez.

## Ağ ve kalite tanımları

Frame baytları yalnızca mini-1 Ethernet üzerindeki worker HTTP 8000/8001 trafiğidir. Sorgu pencereleri cevap üretim zamanını da kapsar; başka sorgulara ait geç ACK/health trafiği içerebilir. Pencere dışındaki bağlantı paketleri dışarıda kalabilir. Fiziksel overhead dahil değildir. Diğer düğümlerin TX+RX toplamı aynı paketi iki kez sayacağı için ana metrikte kullanılmaz. HTTP body baytları ayrı tutulur.

Koordinatör PCAP/request saatleri aynı hosta aittir. Takvim saatleri senkron değildir; zaman farkları ve monotonic süreler kullanılır. Eski PCAP'ın son eksik kaydı düzeltilmiş; kernel drop bilgisi bilinmiyor. Yeniden başlatılan .70 yakalamasında sıfır kernel drop ve bütün 1.672 worker istek/yanıt eşleşmesi doğrulanmıştır.

Hit@3, sentetik sorunun işaretlenen referans parçasının ilk üçte bulunmasıdır. Referanslar eksiksiz değildir; insan değerlendirmesi yoktur. Modelin doğru cevap verdiğini veya bütün alakalı parçaların geri çağrıldığını göstermez. Token-F1 gibi eski CSV alanları ana bilimsel kalite hedefi olarak kullanılmaz.

## Kaynaklar ve tekrar üretim

`data/source_manifest.json` veri kaynağı zincirini; `references/sources.json` resmî yöntem URL'lerini ve kopya hash'lerini; `requirements.lock` paketleri; `research/journal.jsonl` işlem adımlarını tutar. Grafiklerin yanındaki açıklamalar ve sonuç tabloları, şekillerin yeniden üretilmesini sağlar. Proje arşivi ve kontrol toplamları son sürümde oluşturulur.

Ana kaynaklar:

- [Ridge objective — scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)
- [GroupShuffleSplit — scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html)
- [Bootstrap resampling — SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
- [Using models beyond the data domain — NIST](https://www.itl.nist.gov/div898/handbook/pri/section5/pri5998.htm)

Bu belgeler yöntem referansıdır. Çalışan Ridge, split ve bootstrap uygulaması bu projenin NumPy kodudur; scikit-learn/SciPy runtime bağımlılığı değildir.
