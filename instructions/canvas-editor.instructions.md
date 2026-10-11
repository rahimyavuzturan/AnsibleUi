---
description: "Use when building the drag-and-drop visual playbook editor: React Flow canvas, node and edge rendering, locked RAW nodes, implicit dependency edges, dynamic forms and YAML preview."
applyTo: "frontend/src/features/editor/**"
---

# Görsel Editör (Canvas) Kuralları

> Node/edge modelinin anlamı: [docs/04-ansible-ir-spec.md](../../docs/04-ansible-ir-spec.md) ·
> Ekran tasarımı: [docs/10-ui-ux-spec.md](../../docs/10-ui-ux-spec.md)

## Temel İlke

Canvas **YAML'ın görünümüdür, kaynağı değildir.** Kullanıcı canvas'ta bir şey
değiştirdiğinde istemci YAML üretmez; backend'e **yama işlemi** gönderir ve
dönen yeni IR ile canvas yeniden çizilir.

```
kullanici hareketi  →  patch istegi  →  backend ruamel ile yazar  →  yeni IR  →  canvas
```

İstemcide YAML **serileştirme kodu yazılmaz**.

## Node Kuralları

Node tipleri backend'deki `NodeType` enum'undan gelir (`app/ansible/ir.py`).
Arayüzde aynı adlar kullanılır; yeni bir tip **uydurulmaz**.

| `NodeType` | Görünüm | Düzenlenebilir mi |
|---|---|---|
| `PLAY` | Grup başlığı | Hosts / isim alanları |
| `ROLE` | Şema tabanlı form (şema yoksa düz metin alanları) | Evet |
| `TASK_INCLUDE` | Bağlantı kutusu | Hedef ve koşul |
| `MODULE` | Modül formu (şema Faz 8'de zenginleşir) | Evet |
| `BLOCK` | Kapsayıcı | Sınırlı |
| `RAW` | **Kilitli**, salt okunur YAML | Hayır |

### Kilitli İçerik Görünür Olmalı

`RAW` node'lar ve kısmen kilitli parametreler gizlenmez. Kilit ikonu + `lock_reason`
metni gösterilir (örn. "Bu değer Jinja koşulu içeriyor, form ile düzenlenemez").
Bu metin backend'den gelir; arayüzde yeniden yazılmaz.
Kullanıcı içeriği görebilir, değiştiremez.

Kilit ile şablon rozeti **ayrı şeylerdir**: `is_templated` (`{{ x }}`) düzenlenebilir
bir alandır, yalnızca rozetle işaretlenir. Onu kilitli gösterme.

### Sıra Anlamlıdır

Ansible görevleri sıralıdır. Node'ları sürükleyerek yeniden sıralamak dosyadaki
sırayı değiştirir. Serbest yerleşim (rastgele x/y) sıra anlamını **bozmamalıdır** —
düzen dikey akış tabanlıdır.

## Kenar (Edge) Türleri

| Tür | Çizim | Anlam |
|---|---|---|
| Sıra | Düz, gri | Çalışma sırası |
| Örtük veri | Kesikli, turuncu | `register` → sonraki kullanım (ör. sertifika parmak izi zinciri) |
| Dosya | Noktalı, mavi | `include_tasks` ile başka dosyaya geçiş |

**Örtük veri kenarları silinemez.** Kullanıcı böyle bir bağımlılığı bozacak bir
sıralama yaparsa engelleyici uyarı gösterilir ve yayınlama durdurulur:

> "Bu görev, kendisinden önce çalışması gereken sertifika içe aktarma adımının
> önüne alındı. Bağlama işlemi yanlış sertifikayı kullanabilir."

## Form Üretimi

- Form alanları backend'den gelen `RoleSchema`'dan **çalışma anında** üretilir;
  rol başına elle form yazılmaz.
- Güven düzeyi düşük parametrelerde "çıkarım kesin değil" rozeti gösterilir.
- Zod şeması da aynı `RoleSchema`'dan türetilir.
- Liste ve nesne listesi tipleri için tekrar eden satır editörü kullanılır.

## YAML Önizleme

- Monaco salt okunur; canvas ile yan yana.
- Seçili node'un satır aralığı vurgulanır.
- Yayınlama öncesi `DiffEditor` ile dosya bazlı fark gösterilir.

## Performans

- 200 node'a kadar akıcı olmalı. Node bileşenleri `memo` ile sarılır.
- Zustand seçicileri dar tutulur; tüm store'a abone olma.
- Sürükleme sırasında ağ isteği yapılmaz; bırakıldığında tek yama gönderilir.

## Bitti Tanımı

- [ ] `RAW` node düzenlenemiyor ve sebebi gösteriliyor
- [ ] Örtük bağımlılık kenarı silinemiyor, ihlali engelliyor
- [ ] Yama sonrası canvas backend IR'ından yeniden çiziliyor
- [ ] İstemcide YAML üretimi yok
- [ ] E2E senaryosu: rol ekle → parametre doldur → önizleme → fark doğru
