# 10 — Arayüz ve Kullanıcı Deneyimi

## 1. Tasarım İlkeleri

1. **Şeffaflık** — Kullanıcı her an üretilecek YAML'ı görebilmeli. Arayüz bir "kara kutu"
   değil, bir "gözlük"tür. Her ekranda "YAML'ı göster" erişilebilir olmalıdır.
2. **Güvenli varsayılan** — Yıkıcı eylemler onay ister; geri alınabilir olanlar istemez.
3. **Erken uyarı** — Hata, çalıştırma anında değil **düzenleme anında** gösterilir.
4. **Aşamalı açığa çıkarma** — Sık kullanılan parametreler üstte, nadir olanlar
   "Gelişmiş" bölümünde.
5. **Dürüstlük** — Arayüz temsil edemediği şeyi gizlemez; "bu blok ham YAML olarak
   düzenlenebilir" der.

## 2. Bilgi Mimarisi

```
┌─ Üst çubuk ─────────────────────────────────────────────────────────┐
│ AnsibleUI   [Arama...]              senkron: 12sn önce    ● trahim  │
└─────────────────────────────────────────────────────────────────────┘
┌─ Kenar ──┬──────────────────────────────────────────────────────────┐
│ Panoya   │                                                          │
│ Katalog  │                                                          │
│ Envanter │                  İçerik alanı                            │
│ Düzenle  │                                                          │
│ Taslak 3 │                                                          │
│ Çalıştır │                                                          │
│ Yönetim  │                                                          │
└──────────┴──────────────────────────────────────────────────────────┘
```

| Bölüm | Amaç |
|---|---|
| **Pano** | Son çalıştırmalar, açık taslaklar, bekleyen onaylar, senkronizasyon durumu |
| **Katalog** | Rol ve playbook keşfi, arama |
| **Envanter** | Grup/host ağacı, hangi playbook nereyi hedefliyor |
| **Düzenleyici** | Görsel playbook düzenleme (canvas) |
| **Taslaklar** | Açık taslaklar, diff, yayınlama |
| **Çalıştırmalar** | Tetikleme, canlı log, geçmiş |
| **Yönetim** | Kullanıcılar, roller, şema geçersiz kılmaları, denetim |

## 3. Ekranlar

### 3.1 Rol Kataloğu

```
┌─ Roller ─────────────────────────────── [Ara: iis________] [Kaynak ▾] ─┐
│                                                                        │
│  iis_apppool                      roles/         89 kullanım   ✓ high  │
│  IIS uygulama havuzu olusturur veya kaldirir                           │
│  state · dotnetcore · pool_userName · pools                            │
│  ────────────────────────────────────────────────────────────────────  │
│  iis_binding_http                 roles/         31 kullanım   ✓ high  │
│  4 varyant: http · https · https_shell · absent                        │
│  ⚠ Ortulu bagimlilik: _root_ca_cert                                    │
│  ────────────────────────────────────────────────────────────────────  │
│  iis_bindings                     roles/          2 kullanım   ⚠ low   │
│  Sema dogrulanmamis                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

Rol detayında: varyant sekmeleri, parametre tablosu (tip/zorunluluk/varsayılan/örnek),
gerçek kullanım örnekleri (kopyalanabilir YAML), bu rolü kullanan playbook listesi,
`produces`/`consumes` değişkenleri.

### 3.2 Envanter Gezgini

```
┌─ Envanter ──────────────────────┬─ test_isube ─────────────────────────┐
│ ▾ altortam_all                  │                                      │
│    ▾ web                        │  Host'lar (2)                        │
│        dev_web                  │    stlisube1                         │
│        test_web                 │    stlisube2                         │
│        prep_web                 │                                      │
│    ▸ test_isube          ●      │  Etkin degiskenler                   │
│    ▸ test_msube                 │    ansible_connection  winrm         │
│    ▸ test_tsube                 │    ansible_port        5985          │
│ ▾ production                    │    ansible_user        {{ vault }}   │
│    ▸ tsube_prod                 │                                      │
│                                 │  Bu grubu hedefleyen playbook'lar    │
│                                 │    install_isube_test_freshserver.yml│
└─────────────────────────────────┴──────────────────────────────────────┘
```

Bir grup veya host, düzenleyicideki bir play'in `hosts:` alanına **sürüklenebilir**.

### 3.3 Görsel Düzenleyici ★

```
┌─ Palet ──────┬─ Canvas ─────────────────────────┬─ Özellikler ─────────┐
│ Ara: ____    │                                  │ create_dir           │
│              │  ┌─ PLAY ─────────────────────┐  │ ─────────────────    │
│ ▾ Dizin      │  │ install isube_test         │  │ paths *              │
│  create_dir  │  │ hosts: test_isube (2)      │  │ ┌──────────────────┐ │
│  create_dir_c│  └─────────────┬──────────────┘  │ │D:\WebSites\OBA...│ │
│ ▾ IIS        │                ▼                 │ │D:\WebSites\...\api│ │
│  iis_apppool │  ┌─ 1. create_dir ────────────┐  │ │+ Ekle            │ │
│  iis_binding │  │ 33 klasor                  │  │ └──────────────────┘ │
│ ▾ Sertifika  │  └─────────────┬──────────────┘  │                      │
│  importCert  │                ▼                 │ ⚠ Uyarilar           │
│ ▾ Paket      │  ┌─ 2. copyFile_Multiple ─────┐  │ V001: appNames       │
│  installUnin │  │ 6 dosya                    │  │ icindeki api\Profile │
│              │  └─────────────┬──────────────┘  │ icin klasor yok      │
│              │                ▼                 │                      │
│              │  ┌─ 8. importCertificate ─────┐  │ [YAML'i goster]      │
│              │  │ BOA-StandardYeni.pfx       │  │                      │
│              │  │ uretir: _root_ca_cert ─ ─ ┐│  │                      │
│              │  └─────────────┬─────────────││  │                      │
│              │                ▼             ││  │                      │
│              │  ┌─ 18. iis_binding_http ────┘│  │                      │
│              │  │ https_shell · 443          │  │                      │
│              │  │ ◄─ ─ kullanir: _root_ca... │  │                      │
│              │  └────────────────────────────┘  │                      │
└──────────────┴──────────────────────────────────┴──────────────────────┘
```

**Kenar türleri**
- Düz çizgi: çalışma sırası
- **Kesikli çizgi**: örtük veri bağımlılığı (register → tüketim) — turuncu renk
- Noktalı çizgi: `include_tasks` ile başka dosyaya geçiş (tıklanabilir)

**Node durumları**
| Görünüm | Anlam |
|---|---|
| Normal | Şema biliniyor, form düzenlenebilir |
| Kilit ikonu | `RAW` node — yalnızca metin düzenleme |
| Sarı kenarlık | Uyarı var |
| Kırmızı kenarlık | Bloklayıcı hata var |
| Soluk | `when:` koşuluna bağlı, koşullu çalışır |

**Etkileşimler**
- Palet → canvas sürükleme: yeni rol ekler, varsayılan parametrelerle
- Node sürükleme: sırayı değiştirir; **örtük bağımlılık bozulacaksa engellenir ve açıklanır**
- Node çift tıklama: `TASK_INCLUDE` ise alt grafa iner
- Sağ panel: seçili node'un dinamik formu
- `Ctrl+S`: taslağa kaydet · `Ctrl+Z`: geri al

### 3.4 Dinamik Form

Rol şemasından üretilir ([05-role-schema-inference.md](05-role-schema-inference.md)):

| Şema tipi | Kontrol |
|---|---|
| `str` | Metin kutusu; örnek değer placeholder'da |
| `str` + `enum` | Açılır liste |
| `bool` | Anahtar (switch) |
| `int` | Sayı kutusu |
| `list_str` | Eklenebilir/silinebilir/sıralanabilir liste |
| `list_obj` | Alt alanlı satır düzenleyici (ör. `name` + `pool`) |
| `any` / Jinja içerik | **Kilitli** metin alanı + «Bu değer bir ifade içeriyor» notu |

Dağıtıcı parametre (`state`) değiştiğinde form **tamamen yeniden üretilir**; kullanıcı
uyarılır: «`state` değişikliği parametre setini değiştirecek. Devam edilsin mi?»

### 3.5 Diff ve Yayınlama

```
┌─ Yayınla: "isube Profile klasoru" ──────────────────────────────────────┐
│                                                                          │
│  Degisen dosyalar (2)                                                    │
│  ● roles_custom/install_isube/.../install_isube_nonprod_freshserver.yml  │
│  ○ azure-pipelines/nonprod/azure-pipelines-playbook.yml                  │
│      Sebep: Yeni playbook pbList listesine eklendi                       │
│                                                                          │
│  ┌─ Onceki ──────────────────┬─ Sonraki ───────────────────────────┐    │
│  │   - D:\WebSites\...\api   │   - D:\WebSites\...\api             │    │
│  │                           │ + - D:\WebSites\...\api\Profile     │    │
│  └───────────────────────────┴─────────────────────────────────────┘    │
│                                                                          │
│  Dogrulama:  ✓ Bloklayici hata yok    ⚠ 1 uyari (V002)                  │
│                                                                          │
│  Baslik      [AnsibleUI: isube fresh server — Profile klasoru        ]   │
│  Aciklama    [otomatik uretildi, duzenlenebilir                      ]   │
│  Inceleyen   [+ Ekle]                                                    │
│                                                                          │
│                                     [Iptal]  [Branch ac ve PR olustur]   │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.6 Çalıştırma Konsolu

```
┌─ Calistir ───────────────────────────────────────────────────────────────┐
│ Playbook  [altortam/install_isube/install_isube_test.yml        ▾]       │
│ Ortam     [nonprod ▾]                                                    │
│                                                                          │
│ ┌─ On kontrol ─────────────────────────────────────────────────────────┐ │
│ │ ✓ Playbook main'de mevcut        Commit: 16522d0                     │ │
│ │ ✓ pbList listesinde kayitli                                          │ │
│ │ ✓ Calistirma yetkiniz var                                            │ │
│ │ ✓ Onay gerekmiyor (nonprod)                                          │ │
│ │                                                                      │ │
│ │ Hedef: test_isube → stlisube1, stlisube2       (2 sunucu)            │ │
│ │ Adim sayisi: 17                                                      │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│                                                     [Calistir]           │
└──────────────────────────────────────────────────────────────────────────┘

┌─ Calisiyor · 02:14 ──────────────────────────────────────────────────────┐
│                          stlisube1      stlisube2                        │
│ Gathering Facts             ok             ok                            │
│ create_dir                  changed        changed                       │
│ copyFile_Multiple           changed        ⚠ failed                      │
│ installUninstallPackage     ok             skipped                       │
│ features_for_iis            ⟳ calisiyor    skipped                       │
│                                                                          │
│ [Ham log ▾]  [Azure DevOps'ta ac ↗]                      [Iptal et]      │
└──────────────────────────────────────────────────────────────────────────┘
```

## 4. Görsel Dil

### Renk Anlamları

| Anlam | Kullanım |
|---|---|
| Nötr (gri) | Varsayılan yüzeyler, metin |
| Birincil (lacivert) | Eylem düğmeleri, seçili durum |
| Başarı (yeşil) | `ok`, doğrulama geçti |
| Değişti (mavi) | `changed` — Ansible'da bu bir bilgi, hata değil |
| Uyarı (amber) | Uyarı seviyesi doğrulama, örtük bağımlılık kenarları |
| Hata (kırmızı) | `failed`, bloklayıcı doğrulama |
| Atlandı (soluk gri) | `skipped` |

Renk **tek başına** anlam taşımaz; her durum ayrıca ikon ve metin etiketi ile gösterilir.

### Tipografi
- Arayüz: sistem font yığını
- Kod / YAML / log: `ui-monospace`, `Cascadia Code`, `Consolas`
- Taban boyut 14px; kod 13px

### Yoğunluk
Bu bir uzman aracıdır; bilgi yoğunluğu yüksek tutulur. Varsayılan tablo satır yüksekliği
kompakt, isteğe bağlı "rahat" mod sunulur.

## 5. Durumlar

Her veri gösteren bileşen dört durumu ele almalıdır:

| Durum | Gereksinim |
|---|---|
| Yükleniyor | İskelet (skeleton) gösterimi — boş ekran değil |
| Boş | Ne olduğu + ne yapılabileceği + eylem düğmesi |
| Hata | Anlaşılır Türkçe mesaj + "Tekrar dene" + `request_id` |
| Dolu | Asıl içerik |

## 6. Erişilebilirlik

- WCAG 2.1 AA kontrast oranları.
- Tam klavye gezinimi; canvas node'ları ok tuşlarıyla seçilebilir ve taşınabilir.
- Görünür odak halkası; `:focus-visible` kullanılır.
- Anlamlı ARIA etiketleri (özellikle canvas ve log görünümünde).
- Dinamik içerik değişiklikleri (çalıştırma durumu) `aria-live` ile duyurulur.
- `prefers-reduced-motion` desteklenir.

## 7. Performans Bütçesi

| Ölçüt | Hedef |
|---|---|
| İlk anlamlı boyama | < 1.5 sn |
| p95 sayfa geçişi | < 2 sn |
| Rol arama yanıtı | < 300 ms |
| Canvas etkileşim gecikmesi (100 node) | < 16 ms/kare |
| İlk JS paketi | < 300 KB (gzip) |

Monaco ve React Flow **tembel yüklenir** (lazy) — yalnızca düzenleyici açıldığında.

## 8. Türkçe Dil Rehberi

Tutarlı terminoloji, kullanıcı güveninin temelidir.

| İngilizce | Türkçe | Not |
|---|---|---|
| playbook | playbook | Çevrilmez — Ansible terimi |
| role | rol | |
| task | görev | |
| play | oynatma | Yalnızca gerektiğinde; çoğu yerde "playbook bölümü" |
| inventory | envanter | |
| host | sunucu | Teknik bağlamda "host" da kabul edilir |
| group | grup | |
| variable | değişken | |
| draft | taslak | |
| publish | yayınla | |
| pull request | pull request | Çevrilmez — Azure DevOps terimi |
| branch | branch | Çevrilmez |
| commit | commit | Çevrilmez |
| run | çalıştırma | |
| trigger | tetikle | |
| approve | onayla | |
| validation | doğrulama | |
| schema | şema | |
| node | node | Canvas bağlamında çevrilmez |
| changed | değişti | Ansible durumu |
| skipped | atlandı | |
| unreachable | ulaşılamadı | |

**Ton:** Doğrudan, suçlayıcı olmayan, eylem öneren.

| Kötü | İyi |
|---|---|
| «Hata oluştu.» | «Playbook kaydedilemedi: Azure DevOps'a ulaşılamıyor. Tekrar deneyin.» |
| «Geçersiz giriş.» | «`physical_path` değeri `\` ile bitmeli. Örnek: `D:\WebSites\`» |
| «İşlem başarısız.» | «Bu node taşınamaz: `iis_binding_http` sertifikayı `importCertificate`'ten alıyor.» |

## 9. Bileşen Kuralları

- `features/*` klasörleri birbirini **import etmez**; paylaşım `components/` veya `lib/` ile.
- Sunum bileşenleri veri çekmez; veri, kapsayıcı (container) bileşende TanStack Query ile alınır.
- Her etkileşimli bileşenin klavye erişilebilirliği testi olmalıdır.
- Canvas performansı için node bileşenleri `React.memo` ile sarılır.
