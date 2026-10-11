# ADR-0006 — Küçük Ayak İzli PostgreSQL

- **Durum:** Kabul edildi
- **Tarih:** 2026-09-30

## Bağlam

Platformun kalıcı veriye ihtiyacı var: kullanıcılar, roller, taslaklar, çalıştırma
geçmişi, denetim kayıtları ve depo indeksi.

Kurumsal kısıt: **büyük bir veritabanı instance'ı tahsis edilemiyor.**

Ayrıca Rancher tarafında PVC `ReadWriteOnce` modunda ve boyutu sınırlı.

Seçenekler:

1. Büyük PostgreSQL + tüm build log'larını sakla.
2. **Küçük PostgreSQL + log'ları Azure DevOps'ta bırak.**
3. SQLite (PVC üzerinde dosya).
4. Veritabanı yok, her şey dosya sisteminde.

## Karar

**PostgreSQL 16 kullanılır ve toplam boyut 1 GB altında tutulur.**

Boyutu sınırlayan kurallar:

1. **Build log'larının tamamı veritabanına yazılmaz.** Ham log Azure DevOps'ta kalır;
   yalnızca ayrıştırılmış task×host durumları ve özet saklanır. `ado_build_id` ile
   ham log'a köprü kurulur.
2. **Yalnızca son 4 depo snapshot'ı tutulur** (aktif + 3 geçmiş); eskiler silinir.
3. **`draft_revision` taslak başına en fazla 50 revizyon** tutar.
4. **`run_task_result` çalıştırma başına üst sınırla** kısıtlanır; aşımda özetlenir.
5. Taslaklar yayınlandıktan 30 gün sonra, iptal edilenler 7 gün sonra silinir.

Veri sınıflandırması:

| Kategori | Örnek | Kaybedilirse |
|---|---|---|
| **Türetilmiş** | İndeks tabloları, rol şemaları | Yeniden üretilir — sorun yok |
| **Kalıcı** | Kullanıcılar, taslaklar, çalıştırma geçmişi, denetim | Yedekten geri yüklenir |

Yedekleme yalnızca kalıcı verileri kapsar.

## Gerekçe

| Kriter | Büyük PG | **Küçük PG** | SQLite | Dosya sistemi |
|---|---|---|---|---|
| Kurumsal kısıta uygunluk | ✗ | ✓ | ✓ | ✓ |
| Eşzamanlı yazma | ✓ | ✓ | ✗ (PVC RWO ile sorunlu) | ✗ |
| Sorgu gücü (arama, filtre) | ✓ | ✓ | Sınırlı | ✗ |
| JSONB (IR parçacıkları) | ✓ | ✓ | Sınırlı | — |
| Göç yönetimi | ✓ | ✓ | ✓ | ✗ |
| Yedekleme/kurtarma | ✓ | ✓ | PVC'ye bağımlı | PVC'ye bağımlı |
| Kurumsal standart | ✓ | ✓ | ✗ | ✗ |

SQLite reddedildi: PVC `ReadWriteOnce` ve birden fazla pod (api + worker) aynı dosyaya
yazacak — kilitlenme ve bozulma riski yüksek.

Dosya sistemi reddedildi: arama, filtreleme ve denetim sorguları için yetersiz.

Boyut hedefi zaten gerçekçi:

| Veri | Tahmin |
|---|---|
| İndeks (~900 dosya, ~3000 node) | < 50 MB |
| Taslaklar | < 50 MB |
| Çalıştırma kayıtları (yıllık) | < 200 MB |
| Denetim kayıtları (yıllık) | < 100 MB |
| **Toplam** | **< 1 GB** |

Ham log'lar saklansaydı bu rakam yılda onlarca GB'a çıkardı — çünkü `-v` ile çalışan
bir kurulum playbook'u tek koşumda megabaytlarca çıktı üretiyor.

## Sonuçlar

**Olumlu**
- Kurumsal kısıta uyar; küçük bir instance yeterli.
- Kurtarma hızlı: indeks yeniden üretilebilir, yalnızca kalıcı veri geri yüklenir.
- Azure DevOps log'ların tek sahibi kalır — veri çoğaltması yok.
- Yedekleme boyutu küçük.

**Olumsuz**
- Ham log görmek için Azure DevOps'a gidilmesi gerekir (arayüzde köprü verilir).
- ADO'da log saklama süresi dolarsa geçmiş log erişilemez olur (durum özeti kalır).
- Saklama politikalarının düzenli çalışması gerekir (worker görevi).

**Azaltımlar**
- Arayüzde her çalıştırma için «Azure DevOps'ta aç» bağlantısı bulunur.
- Ayrıştırılmış task×host matrisi ve hata mesajları DB'de kalır — sorun gidermek için
  genellikle yeterlidir.
- Saklama politikası görevi izlenir; başarısız olursa uyarı üretir.

## Uygulama

- [docs/03-domain-model.md](../03-domain-model.md) bölüm 5 — boyut bütçesi ve yaşam döngüsü.
- [docs/11-deployment-rancher.md](../11-deployment-rancher.md) bölüm 10 — yedekleme.
- Saklama politikası worker görevi olarak günlük çalışır.
