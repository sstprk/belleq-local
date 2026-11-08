# GitHub ve Vercel'e gönderilecek klasör

GitHub'a bu klasörün **içeriğini** gönder. Repo ana dizininde doğrudan `vercel.json`, `requirements.txt`, `.python-version`, `public/`, `api/`, `src/`, `artifacts/` bulunmalı.

1. GitHub'da örneğin `search-simulator` adında yeni bir repo oluştur. Private olabilir.
2. Bu klasörün içeriğini repoya koy. Tüm araştırma projesini veya büyük ZIP arşivini yükleme.
3. Vercel → **Add New → Project → Import Git Repository** yolundan repoyu seç.
4. **Framework Preset: Other**. **Root Directory: ./**. Build Command boş. Output Directory, `vercel.json` tarafından `public` olarak ayarlanır.
5. Environment Variable eklemek gerekmiyor. **Deploy** düğmesine bas.
6. Verilen bağlantıyı aç. `/health` adresi `status: ok` döndürmeli. Varsayılan hesaplama yaklaşık 339 ms ve 18.6 kB/sorgu göstermeli.
7. Hoca için Production bağlantısını kullan. Bağlantı Vercel girişi istiyorsa paylaşım/Deployment Protection ayarlarını kendi hesabında kontrol et; GitHub reponun public olması gerekmez.

Bu paket yalnızca simülasyon yapar; laboratuvardaki Mac mini'lere erişmez. Barındırılan demo sunucuda kalıcı koşu kaydı tutmaz. Sonuçları CSV veya JSON olarak indir. Tam araştırma verisi ve yerel otomatik kayıt mekanizması orijinal projede durur.

Build sırasında NumPy paketini Vercel kendi ortamına kurar. `.venv`, `wheelhouse`, kitaplar, PCAP dosyaları, `experiments`, `results`, tam veri seti CSV'si veya araştırma ZIP'leri bu repoya eklenmemeli.

Hazırlık sırasında gerçek Vercel yayını yapılmadı. Yerel adaptör kontrolleri `tests/local_checks.json` içinde; yayın sonrası yukarıdaki sağlık ve hesaplama adımları ayrıca kontrol edilmelidir.
