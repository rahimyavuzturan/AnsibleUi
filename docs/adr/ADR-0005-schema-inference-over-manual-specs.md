# ADR-0005 — Elle Şema Yerine Otomatik Çıkarım

- **Durum:** Kabul edildi
- **Tarih:** 2026-09-30

## Bağlam

Arayüzün rol parametreleri için form üretebilmesi bir şemaya ihtiyaç duyar:
her parametrenin adı, tipi, zorunlu olup olmadığı, varsayılanı, geçerli değerleri.

Referans depodaki 65 rolün **hiçbirinde** böyle bir tanım yok:

```
roles/createWebSiteApp/
├── tasks/
│   ├── main.yml
│   ├── createWebSiteApp.yml
│   ├── createWebSiteAppRecursive.yml
│   └── removeWebSiteApp.yml
└── (defaults/ yok · meta/ yok · README yok)
```

Değişkenler yalnızca görev dosyalarının içinde `{{ physical_path }}` gibi kullanılıyor.

Seçenekler:

1. **Elle yazmak** — Her role `meta/argument_specs.yml` eklemek (Ansible standardı).
2. **Otomatik çıkarım** — Kod ve kullanımlardan şemayı türetmek.
3. **Hibrit** — Otomatik taslak üret, gözden geçir, depoya commit et.

## Karar

**Otomatik çıkarım** kullanılır. Şema iki kaynaktan türetilir:

- **Tanım tarafı** — `roles/<ad>/tasks/**.yml` içindeki Jinja ifadeleri AST olarak
  ayrıştırılır; hangi değişkenler okunuyor, varsayılanı var mı, dağıtıcı deseni var mı.
- **Kullanım tarafı** — 120 playbook ve 18 composite roldeki tüm `include_role`
  çağrılarının `vars` blokları toplanır; tip, enum adayları ve kullanım sıklığı çıkarılır.

Her şema bir **güven skoru** taşır (`high`/`medium`/`low`). Düşük güvenli şemalar
arayüzde işaretlenir ve yönetici elle düzeltebilir (`role_schema_override`).

## Gerekçe

| Kriter | Elle | **Otomatik** | Hibrit |
|---|---|---|---|
| Başlangıç maliyeti | Yüksek (65 rol × ~8 parametre) | Düşük (bir kez kod) | Orta |
| Referans depoyu değiştirir mi | **Evet — yasak** | Hayır | Evet |
| Kodla senkron kalır mı | Hayır, elle güncellenmeli | **Evet, otomatik** | Kısmen |
| Doğruluk | Yüksek (insan yazdı) | Orta-yüksek | Yüksek |
| Gerçek kullanım örnekleri | Yok | **Var (bedava)** | Var |
| Kullanım istatistiği | Yok | **Var** | Var |
| MVP'ye uygunluk | Hayır | Evet | Hayır |

İki belirleyici etken:

1. **Referans depo salt-okunurdur** (AGENTS.md kural 1). Elle şema yazmak, depoya
   65 yeni dosya eklemeyi gerektirirdi — bu, projenin temel kısıtını ihlal eder.

2. **Senkronizasyon**. Elle yazılan şema, rol kodu değiştiğinde güncellenmeyi unutulur
   ve sessizce yanlışa döner. Otomatik çıkarım kodla birlikte yaşar.

Ayrıca otomatik çıkarım, elle yazımın veremeyeceği iki şeyi bedavaya verir:
gerçek kullanım örnekleri (forma placeholder olarak konur) ve kullanım sıklığı
(sık kullanılan parametreler formun üstünde gösterilir).

Hibrit yaklaşım (seçenek 3) değerlendirildi ve **Faz 8'e ertelendi** (WP-82):
otomatik çıkarım ve yönetici düzeltmeleri olgunlaştıktan sonra, sonuç
`meta/argument_specs.yml` olarak referans depoya ayrı bir PR ile kazandırılabilir.
Bu, bilginin Ansible'ın kendi standardına da geçmesini sağlar — ama önce çıkarımın
doğru çalıştığından emin olmak gerekir.

## Sonuçlar

**Olumlu**
- 65 rolün tamamı MVP'de kapsanır; elle yazım darboğazı yok.
- Rol kodu değiştiğinde şema otomatik güncellenir.
- Gerçek kullanım örnekleri ve istatistikler bedava gelir.
- Referans depoya dokunulmaz.
- Dağıtıcı tespiti sayesinde varyantlar doğru modellenir
  (`createWebSiteApp@started` vs `@recursive` — farklı `appNames` tipleri).

**Olumsuz**
- Çıkarım yanılabilir; hedef %100 değil **≥%80** (K2).
- Açıklama metinleri üretilemez — yalnızca yönetici geçersiz kılmasıyla eklenir.
- Hiç kullanılmamış roller için tip bilgisi zayıf kalır.
- Çıkarım algoritması bakım gerektiren bir kod parçasıdır.

**Azaltımlar**
- Güven skoru ile şeffaflık: kullanıcı şemanın ne kadar güvenilir olduğunu görür.
- Yönetici geçersiz kılma ekranı: insan emeği kaybolmaz, snapshot'lar arasında yaşar.
- 10 referans rol için snapshot testleri çıkarımın gerilemesini engeller.
- Düşük güvenli şemalarda kullanıcı her zaman ham YAML'a geçebilir.

## Uygulama

- [docs/05-role-schema-inference.md](../05-role-schema-inference.md) — algoritma ayrıntısı.
- WP-13 — uygulama; kabul kriteri: 65 rolün ≥%80'i için şema üretimi.
- `tests/unit/test_schema_infer.py` — 10 referans rol için snapshot testleri.
