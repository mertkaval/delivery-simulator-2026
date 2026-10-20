# Yaşayan şehir uygulaması — 18 Eylül 2026

Bu sürüm, `LIVING_CITY_PLAN.md` ve önceki downtown planının uygulamasıdır. Yeni kaynaklar `world/living_city/` altında tutulur. Verilen otomobil fotoğrafları oran, cam, koltuk, far ve gövde ayrıntıları için referans olarak kullanıldı; marka logoları kopyalanmadı.

## Blender kaynakları ve modeller

30 düzenlenebilir `.blend` kaynak ve 90 GLB (her model için üç seviye) üretildi:

- Altı iskeletli yetişkin karakter; farklı ten/saç/kıyafet, yağmurluk, çanta ve reflektif iş kıyafeti. 14 kemik ve Idle, Walk, Brisk, Wait, Talk, Sit, Carry, Cycle klipleri. Sürekli kol/bacak yüzeylerinde ağırlıklarla deformasyon kullanılır.
- Kompakt hatchback, uzun sedan, crossover, panelvan, pickup, taksi, polis, ambulans, itfaiye ve okul otobüsü. Tekerlek pivotları, cam, kabin, koltuklar, ayna, far/stop, plaka, kapı çizgileri ve araç türüne özel ekipman bulunur. Ağır araçlar ayrı ticari kabinlere, büyütülmüş tekerleklere ve kesilmiş çamurluk açıklıklarına sahiptir.
- Hastane, üç açık araç bölmeli itfaiye istasyonu, okul ve spor salonu; giriş holleri, pencere doğramaları, çatı tesisatı, kanopiler ve tabelalar.
- Çiçekli yağmur bahçesi, çim yüzeyi, altı trafik/yön levhası, bisiklet şeridi, yer işareti ve esnek ayırıcı.

Üretim betikleri `build_characters.py`, `build_vehicles.py`, `build_civic.py`; kaynaklar `assets/source/`, envanterler aynı klasördeki `*_manifest.json` dosyalarıdır. Ölçek metredir; Godot'ta +Y yukarı, araçların önü -Z'dir. Bina cepheleri yerel +Z'ye bakar. Godot içe aktarmada teğetler, ek mesh LOD'ları ve gölge meshleri üretilir. Kaynak `.blend` dosyaları `.gdignore` ile oyun içe aktarmasından ayrılmıştır.

## Davranış ve şehir bağlantıları

Yaya ağı 280 nokta ve 415 kenardan oluşur. Kaldırımlar, kontrollü geçitler, avlular, bina girişleri ve üç kamu binası bağlantılıdır. A* yolu; saat, rol, mesafe ve önceki ziyaret üzerinden hedef seçimiyle birleştirilir. Sabah/öğleden sonra iş, öğlen kafe, akşam alışveriş ve ev hedefleri vardır. Varışta bekleme/konuşma, engelde koridor içinde kaçınma ve yeniden hedef seçme uygulanır. Amaç ve etkinlikler NPC metadata'sından denetlenebilir.

Downtown sinyal döngüsü 64 saniyedir. Yayalar 32–38 saniye aralığında geçide girer; kalan kırmızı süre yolu boşaltmak içindir. Görünür bir yaya hâlâ geçitteyse döngü kırmızıda tutulur. Bu davranış araçlara yeşil verilmeden önce kontrol edilir.

İki polis devriyesi, bir ambulans transfer rotası, bir itfaiye istasyon rotası, bir okul otobüsü ve iki taksi ayrıca çalışır. Hizmet araçları yuvarlatılmış dönüş yolları, öndeki engeli kontrol eden üç prob, hızlanma/frenleme ve planlı duraklar kullanır. Ambulans, itfaiye ve okul otobüsünün hizmet alanına giren güzergâhları vardır. Okul otobüsü 07–10 ve 14–17 saatlerinde çalışır, mesai dışında durağında bekler. Uzak aktörler görünürlük ve çarpışma açısından uyutulur; bu, tüm şehir için kesintisiz arka plan simülasyonu değildir.

Kamu bölgesi doğuda x=520 yolu ve dört bağlantıyla downtown'a bağlanır. Hastane z=-328, itfaiye z=-468, okul z=-608 civarındadır. Bisiklet yolu x=473/475 boyunca iki yönde ilerler; girişler ve kavşaklar ayırıcılarla kapatılmaz. Yağmur bahçeleri, ağaçlı lineer park, banklar ve çiçekler sert zeminleri böler. Yerel harita yeni yolu ve kamu binalarını gösterir.

## Optimizasyon

Karakterler 18/45 metre eşiklerinde üç LOD kullanır, 105 metrenin ötesinde animasyon durur. Uzak animasyon örnekleme 4 Hz'e düşer. Yaya davranışı 115 m, hizmet trafiği 220 m etkinlik sınırı kullanır. Hizmet araçlarında 25/70 metre LOD eşikleri vardır. Statik parçalar 64 m hücrelerde MultiMesh ile gruplanır; cephelerin uzak temsilleri ve bina occluder'ları kullanılır. Aynı ad/renk/yüzey özelliklerindeki yeni materyaller çalışma zamanında ortaklaştırılır. Küçük peyzaj ayrıntıları gölge üretmez; büyük bina parçaları üretir.

## Doğrulama

`tests/living_city.gd`: karakter kemikleri/sekiz klip, LOD azaltımı, dört tekerlek pivotu, eski ten boyamasının kıyafetleri bozmaması, tüm yaya kenarlarının ve hizmet aracı yol parçalarının sabit engellerden geçmemesi, kamu binalarının erişilebilirliği, hedef metadata'sı ve geçit boşalma mantığı.

Tam regresyon turunda ekonomi, dispatch, 25 regresyon, 170 şehir, 71 yaşam/araç, 11 başlangıç evi, 99 downtown teslimat kontrolü ve 10 giriş/3 servis yolu erişimi geçti. Oyunu açan testler kaydı devre dışı bırakır veya bellek kayıt deposu kullanır. Bu geliştirme öncesi kaydedilen 75 özgün `.blend`/GLB dosyasının SHA-256 karşılaştırmasında değişiklik yoktur.

Yeni yaşayan şehir paketi 683 kontrol / 0 hata ile geçti. Son 14 downtown görüntüsünde 931–1.912 çizim çağrısı, en çok 1.245 milyon primitive ve 194,53 MiB doku belleği ölçüldü. Medyan kare süreleri 7,05–12,41 ms, yüzde 95 süreler 8,61–18,66 ms idi. Yedi kamu bölgesi görüntüsünde 100–1.675 çizim çağrısı, medyan 5,07–11,74 ms ve yüzde 95 8,72–15,05 ms ölçüldü. 2.000 draw call / 3 milyon primitive / 512 MiB doku bütçeleri karşılandı; son turdaki dört downtown görüşünde 16,7 ms yüzde 95 hedefi aşıldı. Önceki tur daha hızlıydı; rapor en iyi sonucu seçerek sabit 60 FPS iddia etmez.

Ortaklaştırmadan sonra sahnede bağlı materyal sayısı 703'ten 264'e indi; yüklenmiş fakat her an çizilmeyen materyal kaynakları dahil sayı 581'dir. Özgün rota sorgusu ortalama 0,017 ms, yeni kent rota sorgusu 0,034 ms ölçüldü. Sahne 2.071 statik fizik gövdesi ve 3.082 çarpışma şekli içerir; bunların büyük bölümü özgün mahalleden gelir.

Görseller: `tmp/review_citizen_lineup.png`, `tmp/review_fleet_lineup.png`, `tmp/living_city_*.png`, `tmp/downtown_after_*.png`, `tmp/downtown_phone_order.png`, `tmp/downtown_night.png`. Ölçümler: `tmp/downtown_after_metrics.json` ve `tmp/living_city_metrics.json`. Bunlar RTX 3070 Laptop GPU, Godot 4.7.2 Forward+, 1280×720, VSync kapalı, ısınmış sahne ölçümleridir; farklı makineler ve tam oyun oturumları için FPS garantisi değildir.

Kayıt yazmadan yeni bölgeyi gezmek için Godot'u `--path . --script res://tests/preview_living_city.gd` ile açın. Normal oyun `app/app_root.tscn` üzerinden başlatılır. Tab telefon, M yerel harita, E etkileşim/binme/inme, WASD hareket ve Space bisiklet freni olarak kalır.

## Kapsamın sınırları

Bu çalışma özgün, prosedürel ve düzenlenebilir bir oyun sanatı geliştirmesidir. Fotoğraflardaki araçların birebir veya fotogerçekçi üretim kalitesinde kopyası değildir; yüzler, saç, yüzey dokuları ve bazı kabin/cephe ayrıntıları hâlâ stilizedir. Animasyonlar elle tanımlanmış döngülerdir; motion capture, ayak IK'sı ve kalabalıklar için tam karşılıklı hız engeli çözücüsü yoktur. Polis/ambulans/itfaiye işlevi dolaşım ve hizmet rotasıdır; suç, yangın veya hasta kurtarma görev sistemi eklenmemiştir. Kamu binalarında sığ giriş/servis alanları vardır; bütün katlar oynanabilir değildir. Üst katlı otoparkın üst seviyeleri dekoratiftir.

Önceki geliştirmede gerçekleşen kayıt üzerine yazma olayı `PROJECT_STATE.md` içinde korunmuştur; bu rapor o olayı geri alınmış gibi sunmaz.
