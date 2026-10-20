# Higgsfield konut yenilemesi — 3 Ekim 2026

60 normal konut, Higgsfield 3D Jutsu'da hazırlanan yeni dış cephelerle değiştirildi. 36 teslimat adresi ve 24 yan sokak evi aynı parsellerde duruyor. İç mekân eklenmedi. Ayrı oynanabilir Cedar başlangıç evi, dinlenme işlevi, teslimat kimlikleri ve yollar korundu. Downtown klasöründeki 435 dosyanın SHA-256 karşılaştırmasında değişiklik yok.

## Mimari ve malzeme

12 birleşim dört aileye ayrılıyor: alçak ve geriye çekilmiş yan kanatlı bungalov, taş tabanlı cumbalı kır evi, uzun pencereli tuğla konut ve düşük yan kanadı teras olarak kullanılan çağdaş konut. Altı cephe/kapı paleti deterministik olarak dağıtılıyor. 27 parçalı ana modüler kütüphane kaynak dosyada korunuyor. Higgsfield projesine daha önce eklenmiş bağımsız Home_* örnekleri, bahçeler ve ek kütüphane parçaları silinmedi.

Tuğla ölçeği yaklaşık 25 × 7,7 cm, ahşap kaplama sırası yaklaşık 14,3 cm. Cephe albedoları 2048²; yardımcı malzemelerin albedoları ve normal haritaları 1024²; pürüzlülük haritaları 512². Bu dağılım ince görünen ayrıntıyı korurken gereksiz doku boyutunu sınırlıyor. Sıva, taş, ahşap, tuğla, çatı, metal ve trim yüzeyleri paylaşılan PBR haritaları kullanıyor.

Çatı kenarları, mahyalar, açık profilli oluklar, baca tabanları, çatı havalandırması, parapet kapakları, kapı eşikleri ve sundurma destekleri yeniden düzenlendi. Ev numaraları artık havada duran büyük yazılar yerine kapı yanındaki küçük plakada. Eski görünmez sundurma engelleri kaldırıldı; cumbalar ve girintili kanatların çarpışmaları yeni şekillere uyarlandı.

## Kaynak ve oyun entegrasyonu

- Higgsfield projesi: https://higgsfield.ai/3d-jutsu/40e06765-d85d-471a-9f4a-3cf2d6c9e567
- Oyuna aktarılan sürüm: **28**.
- GLB: `world/higgsfield/housing/modular_housing.glb`.
- Düzenlenebilir kaynak: `world/higgsfield/housing/source/modular_housing.blend`.
- Son üretim adımları: `quality_materials_remote.py`, `quality_architecture_remote.py`, `quality_details_remote.py`. Bunlar Higgsfield'da çalıştırılan işlerin kayıtlarıdır; yerel Blender ile üretilmedi.
- Godot bağlayıcısı: `world/higgsfield/housing/housing.gd`. Galeri zemini, kameralar ve ışıklar oyuna alınmaz.

Her ev tek statik mesh ve paylaşılan malzeme yüzeyleri kullanır; tek mesh, tek çizim çağrısı demek değildir. Ev başına 20.864–30.372 üçgen var; önceki sürüm yaklaşık 30.570–45.210 aralığındaydı. Godot otomatik mesh LOD, paylaşılan sahne önbelleği ve mesafe görünürlüğü aktif.

## Doğrulama

Son optimizasyon: 27 yeni PBR dokusunda yüksek kaliteli BPTC GPU sıkıştırması ve mipmap kullanılıyor. Çözünürlükler korunarak aynı oyun sahnesindeki toplam doku belleği 383,98 MiB'den 266,98 MiB'ye düştü (117 MiB tasarruf). Bu değer tüm sahne içindir. Önceki 256 MiB hedefi henüz sağlanmıyor.

1440 × 900, Forward+, RTX 3070 Laptop GPU üzerinde beş kısa kamera ölçümünde medyan kare süresi 5,95–8,22 ms, p95 7,29–14,70 ms; çizim çağrıları 1.626–2.097 aralığında. Bunlar kısa yerel ölçümlerdir, uzun oyun oturumu veya başka donanım için performans garantisi değildir. Son sıkıştırmadan sonra 273 konut kontrolü yeniden geçti. Ölçümler: `tmp/housing_metrics.json`.

- Konut: **273 kontrol, 0 hata**; 2K cepheler, normal/pürüzlülük haritaları, 60 yerleşim, 36 teslimat kapısı, kapalı dış cepheler ve girintili kanat çarpışmaları.
- Şehir: **170 kontrol, 0 hata**.
- Downtown oynanış: **99 kontrol, 0 hata**.
- Cedar başlangıç evi: **11 kontrol geçti**.
- Testler kayıt dosyasına yazmaz; bellekte çalışır veya kayıt devre dışıdır.
- Higgsfield Cycles ve Eevee renderları ile gerçek Godot sokak görüntüleri incelendi.

Bu çalışma detaylı prosedürel oyun sanatıdır; taranmış/fotogrametrik yüzey, tam fiziksel hava aşınması veya fotoğraf gerçekçiliği iddiası yoktur. Pencereler kapalı dış cephe elemanlarıdır. Global şehir ışığı, mevcut ağaçlar ve downtown sanat varlıkları bu konut işinde değiştirilmedi.
