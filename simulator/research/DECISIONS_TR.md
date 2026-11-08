# Karar ve kapsam günlüğü

1. Kullanıcı önce backend/model istedi; arayüz sonraki aşamaya bırakıldı. Tek proje klasörü ve paylaşılabilir tek ZIP oluşturulur.
2. Ana veri .70 eşikli 2.000 satırdır. .80 koşuları başarısız fiziksel deney sayılmadı; eşik etkisi için yardımcı ham kaynak olarak saklandı.
3. 2.000 satırın 2.000 bağımsız kurulum olmadığı kabul edildi. PC sayısı, corpus ve sorgu yükü için öğrenilmiş katsayı iddia edilmedi.
4. Eğitilecek temel hipotez, düşük boyutlu Ridge'in yöntem ortalamasını geçip geçemediğidir. Alpha ve model seçimi testten önce doğrulama grubunda yapılır.
5. Eğitim/test ayrımı soru düzeyindedir. Tek sorunun farklı yöntemlerdeki ölçümleri veya augment edilmiş sıraları birbirine sızdırılmaz.
6. İlk işleme sırasında iki HTTP 503 kaydının node payload'ı taşımadığı görüldü. İşleyici bu kayıtları koruyacak şekilde düzeltildi; gerçek ölçümler değiştirilmedi.
7. Ridge retrieval/traffic hedeflerinde baseline'ı geçmedi. Bu negatif sonuç korunarak ampirik Monte Carlo ana dağılım motoru yapıldı. Client Ridge'in düşük R² sonucu açıkça raporlandı.
8. Replay motoru başarılı 1.998 ölçümün sonuçlarını birebir yeniden üretti. Sıra augmentation'ı yalnızca kaynak aday listelerinden türetildi; bağımsız deney sayısı artırılmış gibi sunulmadı.
9. Sanal düğüm sayısı değiştirildiğinde bütün N değerlerinde aynı 'bir sahip + dikkat dağıtıcılar' varsayımı kullanıldı. Gerçek 3-düğüm trace modu bu varsayımsal eğriden ayrı tutuldu. Varsayım modunda kalite çıktısı kapatıldı.
10. Kullanıcı tarafından seçilen service-time çarpanı, örneklenmiş round-trip/router sürelerini ölçekler; CPU/GPU donanım etkisi öğrenilmiş gibi adlandırılmadı. Bant genişliği referansı da kullanıcı varsayımıdır.
11. Grafikler sayısal tablolarla birlikte üretildi ve görsel olarak kontrol edildi. Ölçeklenme eğrileri görünür biçimde varsayımsal olarak etiketlendi.
12. Ham PCAP'lardan 2.000 sorgunun byte metrikleri yeniden hesaplandı ve tamamı eşleşti. Sorgu pencerelerinin fiziksel Ethernet kullanımının tümünü kapsamadığı korundu.
13. Asıl kullanım için internet gerekmiyor. NumPy/matplotlib ve bağımlılıklarının Apple Silicon/Python 3.12 wheel kopyaları çevrimdışı kurulum için saklandı.

Makale için bir sonraki yeni sürüm; bağımsız tekrar oturumları, düğüm sayısı ve corpus büyüklüğünü ayrı değiştiren deneyler ve eşzamanlı yük ölçümleriyle hazırlanmalıdır. Mevcut sürümün frozen-test sonuçları yeni sürümün hiperparametre seçimi için tekrar tekrar kullanılmamalıdır.
