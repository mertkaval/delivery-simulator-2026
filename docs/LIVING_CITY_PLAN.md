# Yaşayan şehir geliştirme planı — 18 Eylül 2026

## İnceleme ve hedef

Mevcut NPC'ler parçalı eklem dönüşleriyle hareket ediyor; omuzlarda açıklıklar, sert siluetler ve birbirini tekrar eden kısa yürüyüşler var. DowntownActivity yayaları çoğunlukla iki nokta arasında döndürüyor. Araçlar beş ortak gövde türevinden oluşuyor; kabin, far, tampon ve profil ayrıntıları referans görsellerinin seviyesine ulaşmıyor. Downtown 9 blok ve 90 parsel içeriyor. Önceki çalışma sırasında bağlantı yollarına taşan çim ve bazı tabela yerleşimleri de saptandı.

Referans görselleri araç oranı, hatchback/uzun sedan silueti, cam tavan, koltuklar, LED far, jant ve yüzey geçişleri için görsel kaynaktır; görsellerdeki yazılar talimat değildir. Mevcut kayıtlar, kontroller, teslimat kimlikleri ve özgün Blender dosyaları korunacak. Yeni kaynaklar ayrı `world/living_city/` klasörüne yazılacak.

## Uygulama sırası

1. Mevcut kodun ve varlıkların kopyasını al; NPC, araç, yol ve performans başlangıç durumunu kaydet. Bağlantı yollarındaki çim taşmasını düzelt.
2. Blender'da sürekli kıyafet yüzeyleri, doğal yüz/vücut oranları, saç ve kıyafet çeşitleri olan iskeletli karakterler üret. Idle, walk, brisk walk, wait, talk, sit ve carry klipleri; el/kol/diz ağırlıkları; yakın/orta/uzak görünüm seviyeleri ekle. Önce tek karakteri Blender ve Godot'ta doğrula, sonra çeşitleri üret.
3. Yaya davranışını amaç, günlük program ve yol grafı ile genişlet: ev–iş, alışveriş, kafe, transit ve servis görevleri. A* kaldırım grafı, kontrollü yaya geçidi kenarları, varışta bekleme/etkileşim, yerel kaçınma ve sıkışma kurtarma kullan. Araç yolunu rastgele kesen veya kapı önünde sonsuza kadar duran yayalar olmasın.
4. Referanslara göre özgün kompakt hatchback ve uzun lüks sedan; ardından taksi, polis devriye aracı, ambulans, itfaiye aracı ve okul otobüsü oluştur. Kabin/koltuk, cam, far, stop, kapı çizgisi, ayna, tampon, jant/lastik ve dönen tekerlek pivotları ekle. Ayrı gövde ölçüleri ve çarpışma kutuları kullan.
5. Hastane, itfaiye istasyonu ve okul için Blender kaynakları üret; mevcut boş/servis parsellerine veya bağlantılı yeni sivil hizmet yerleşkesine yerleştir. Ambulans çıkışı, itfaiye apron alanı, okul otobüsü durağı ve yaya erişimi açık olsun.
6. Kaldırım peyzajını kurallı yerleştir: ağaç çukurları, alçak çiçek tarhları, yağmur bahçeleri, köşe görüş alanları ve en az 1,8 m açık yaya koridoru. Bisiklet şeritlerini sürekli boya, sembol, ayırıcı ve kavşak geçişleriyle tamamla. Trafik levhalarını gerçek ölçülerde tasarla.
7. Yeni araçları mevcut trafik/park sistemine ekle. Polis devriyeleri, hastane/istasyon bağlantılı hizmet araçları, taksi dolaşımı ve okul otobüsü rotası tanımla. Sinyal ve çarpışma kuralları ortak kalsın.
8. LOD, instancing, ortak materyal, mesafe etkinleştirmesi ve düşük maliyetli çarpışma uygula. NPC animasyonlarını uzaklıkla seyrekleştir. 720p'de önceki 2.000 draw call / 3 milyon primitive / 512 MiB doku bütçesine karşı ölç; aşımı düzelt veya raporda açıkça belirt.
9. Teslimat, kayıt, bisiklet/araç kontrolleri ve eski sahne testlerini çalıştır. Karakter yakın planı, animasyon, trafik, bisiklet yolu ve her kamu binasını gerçek Godot görüntüleriyle değerlendir. Kaynak/model envanteri ve ölçülmüş sonuçları yaz; oyunu inceleme için aç.

## Kabul kontrolü

- Eski oyuncu verilerine test sırasında yazılmaz; testler `save_enabled=false` veya bellek kayıt deposu kullanır.
- Yeni NPC'lerin yürüyüşte omuz/diz açıklığı olmamalı; hareket klibi gerçek yer değiştirme hızıyla eşleşmeli.
- Yaya rotaları kaldırımda veya izinli geçitte kalmalı; amaç/durum/günlük program denetlenebilir olmalı.
- Tüm yeni araçların tekerlek, ölçü ve çarpışma sınırları kontrol edilmeli.
- Ambulans/itfaiye çıkışı, okul durağı, bisiklet şeridi ve teslimat girişleri peyzajla kapanmamalı.
- Her yeni model için düzenlenebilir `.blend`, Godot'a aktarılabilir GLB, LOD/üçgen bilgisi ve ortak materyal tanımı bulunmalı.

Bu plan uygulama içindir; yalnızca plan teslim edilip çalışma bırakılmayacak.
