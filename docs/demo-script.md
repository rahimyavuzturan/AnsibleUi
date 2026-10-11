# Demo Senaryosu

**Süre hedefi:** 5 dakika (başarı kriteri K3)
**Kitle:** Otomasyon ekibi, uygulama ekipleri, yönetim

## Anlatı

> «Bugün bir sunucuya yeni bir klasör eklemek için bir YAML dosyası bulup, doğru satırı
> bulup, elle düzenleyip, commit atıp, PR açıp, pipeline listesini de güncellemeyi
> hatırlamak gerekiyor. Bir adımı atlarsanız, hata playbook'un **son** adımında,
> yarım saat sonra ortaya çıkıyor. Şimdi aynı işi yapalım.»

---

## Hazırlık (demo öncesi)

- [ ] Platform çalışıyor, indeksleme tamamlanmış (`/api/status` yeşil)
- [ ] `trahim` kullanıcısı: nonprod'da Editor, prod'da Viewer
- [ ] `mehmet` kullanıcısı: Approver (dört göz gösterimi için)
- [ ] Önceki demo taslakları temizlenmiş
- [ ] Sahte/test ADO projesi hazır (gerçek depoya PR açılmayacaksa)
- [ ] Tarayıcı yakınlaştırma %100, gereksiz sekmeler kapalı

---

## Adım 1 — Keşfedilebilirlik (45 sn)

**Ekran:** Katalog

1. Arama kutusuna `createWebSiteApp` yaz.
2. Rol detayını aç.

**Gösterilecek:**
- Rolün **3 varyantı** (`started` / `recursive` / `absent`) sekmeler hâlinde.
- `@recursive` varyantında `appNames` alanının `list[{name, pool}]` olduğu.
- **14 gerçek kullanım örneği** — kopyalanabilir YAML.
- Bu rolü kullanan playbook listesi.

**Söylenecek:**
> «Bu bilgi bugün hiçbir yerde yazmıyor. Rolün ne aldığını öğrenmek için dört ayrı
> dosyayı okumak gerekiyordu. Bu şema koddan otomatik çıkarıldı — kod değişince
> kendiliğinden güncelleniyor.»

---

## Adım 2 — Envanter (30 sn)

**Ekran:** Envanter gezgini

1. `test_isube` grubunu aç.

**Gösterilecek:**
- 2 sunucu: `stlisube1`, `stlisube2`.
- Etkin değişkenler (`ansible_connection: winrm` vb.) ve nereden miras alındığı.
- Bu grubu hedefleyen playbook'lar.

**Söylenecek:**
> «'Bu playbook hangi sunuculara gidecek?' sorusu artık tek tıkla cevaplanıyor.»

---

## Adım 3 — Görsel Düzenleyici (90 sn) ★

**Ekran:** Düzenleyici — `install_isube_nonprod_freshserver.yml`

1. Dosyayı aç.

**Gösterilecek:**
- **17 adımın tamamı** canvas'ta sırayla.
- `importCertificate` (8. adım) ile `iis_binding_http` (18. adım) arasındaki
  **turuncu kesikli ok**.

2. Kesikli okun üzerine gel.

> «Bu bağımlılık YAML'da **hiçbir yerde yazmıyor.** Binding görevinin sertifika
> parametresi yok — sadece en son çalışan `importCertificate`'in bıraktığı değişkeni
> okuyor. Bir adımı yanlış yere taşırsanız yanlış sertifika bağlanır ve
> **hiçbir hata almazsınız**. Platform bunu görünür kılıyor.»

3. `importCertificate` node'unu `iis_binding_http`'nin altına sürüklemeye çalış.

**Gösterilecek:** Bloklayıcı uyarı — hangi değişkenin hangi node'dan geleceği açıklanıyor.

4. Değişikliği geri al.

---

## Adım 4 — Düzenleme ve Doğrulama (60 sn)

1. `create_dir` node'unu seç.
2. Sağ panelde `paths` listesine yeni bir klasör ekle:
   `D:\WebSites\OBA.Web.InternetBanking\api\Profile`

**Gösterilecek:** Dinamik form — şemadan üretildi, gerçek örnekler placeholder'da.

3. «YAML'ı göster» düğmesine bas.

> «Her an ne üretildiğini görebiliyorsunuz. Arayüz bir kara kutu değil.»

4. Şimdi tersini yap: `createWebSiteApp` node'una `create_dir`'de karşılığı olmayan
   bir `appName` ekle.

**Gösterilecek:** `V001` bloklayıcı hatası anında beliriyor:
> «`appNames` içindeki `api\Reports` için `create_dir` listesinde klasör yok.»

**Söylenecek:**
> «Bugün bu hata playbook'un **son adımında**, 16 adım çalıştıktan sonra ortaya çıkıyor:
> *specified folder must already exist*. Sunucu yarı yapılandırılmış kalıyor.
> Burada yazarken yakalanıyor.»

5. Hatayı düzelt.

---

## Adım 5 — Diff ve Yayınlama (60 sn)

1. «Yayınla» düğmesine bas.

**Gösterilecek:**
- İki dosyanın diff'i: görev dosyası **ve** `azure-pipelines/nonprod/...yml`.
- İkincisinin sebebi: «Yeni playbook pbList listesine eklendi.»

**Söylenecek:**
> «Pipeline'daki playbook listesini güncellemeyi unutmak sık yapılan bir hata —
> playbook çalıştırılamaz hâle geliyor. Platform bunu aynı PR'a otomatik ekliyor.»

2. Diff'i incele: **yalnızca eklenen satırlar** var, dosyanın geri kalanı dokunulmamış.

> «Yorumlar, tırnak stili, girinti — hepsi aynen korunuyor. YAML doğruluk kaynağı;
> arayüz sadece bir görünüm.»

3. PR başlığını gir ve «Branch aç ve PR oluştur»a bas.
4. Açılan Azure DevOps sekmesinde gerçek PR'ı göster.

**Gösterilecek:** PR açıklamasında değişiklik özeti, etkilenen roller ve
**etkilenen host grupları**.

---

## Adım 6 — Çalıştırma (60 sn)

> «PR merge edildi diyelim.»

**Ekran:** Çalıştırma

1. Playbook ve `nonprod` ortamını seç.

**Gösterilecek — ön kontrol özeti:**
```
✓ Playbook main'de mevcut          Commit: 16522d0
✓ pbList listesinde kayitli
✓ Calistirma yetkiniz var
✓ Onay gerekmiyor (nonprod)

Hedef: test_isube → stlisube1, stlisube2   (2 sunucu)
Adim sayisi: 17
```

2. «Çalıştır»a bas.

**Gösterilecek:** Canlı task × host matrisi dolmaya başlıyor.

**Söylenecek:**
> «Ansible yine mevcut Azure Pipeline'da, mevcut agent'ta çalışıyor. Platform vault
> parolasını hiç görmüyor, hedef sunuculara hiç bağlanmıyor. Sadece tetikliyor ve
> sonucu okunabilir hâle getiriyor.»

---

## Adım 7 — Güvenlik (30 sn)

1. `prod` ortamını seç.

**Gösterilecek:** «prod ortamında çalıştırma yetkiniz yok.»

2. Approver hesabına geç, prod'u seç.

**Gösterilecek:** «Bu ortam için Approver onayı gerekiyor» — tetikleyen ile onaylayanın
farklı kişi olması şartı.

3. Yönetim → Denetim kayıtları.

**Gösterilecek:** Demo boyunca yapılan her işlem kayıtlı: kim, ne zaman, ne yaptı.

---

## Kapanış (15 sn)

> «Özetle: hiçbir şey değişmedi — aynı depo, aynı pipeline, aynı agent'lar,
> aynı güvenlik modeli. Değişen tek şey, bunlara **20 kişinin** erişebilmesi.
>
> Ve şunlar artık imkânsız: `main`'e doğrudan yazmak, onaysız prod çalıştırmak,
> görünmez bir sertifika bağımlılığını fark etmeden bozmak, pipeline listesini
> güncellemeyi unutmak.»

---

## Sık Gelen Sorular

| Soru | Cevap |
|---|---|
| «Elle YAML yazmaya devam edebilir miyiz?» | Evet. Platform sahiplik iddia etmiyor; elle yapılan değişiklikler anında arayüzde görünüyor. |
| «Karmaşık PowerShell blokları ne oluyor?» | Ham YAML kartı olarak korunuyor, metin olarak düzenlenebiliyor. Asla yeniden üretilmiyor. |
| «Platform çökerse?» | Depo ve pipeline'lar etkilenmez. Sadece arayüz erişilemez olur. |
| «Vault parolalarını görüyor mu?» | Hayır. Sadece değişken **adlarını** listeliyor. Parola secure file olarak yalnızca agent'ta. |
| «Yanlışlıkla prod'u bozabilir miyiz?» | `main`'e doğrudan yazma imkânsız, prod çalıştırma ikinci onay istiyor, her şey PR'dan geçiyor. |
| «Yapay zekâ ne zaman?» | Faz 7. Mimari hazır; AI çıktısı da aynı doğrulama ve onay zincirinden geçecek. |
| «Yeni bir rol eklersek?» | İndeksleme otomatik yakalıyor, şemasını çıkarıyor, katalogda beliriyor. |

## Demo Sonrası Kontrol

- [ ] Demo taslakları temizlendi
- [ ] Test PR'ı kapatıldı
- [ ] Demo çalıştırması geçmişte doğru görünüyor
- [ ] Geri bildirimler [13-roadmap-wbs.md](13-roadmap-wbs.md) «Not Düşülenler» bölümüne eklendi
