---
description: "Use when writing or updating project documentation, ADRs, the WBS roadmap or the glossary under docs/. Covers document structure, tone, link format and which docs must change together."
applyTo: "docs/**,*.md"
---

# Dokümantasyon Kuralları

## Dil ve Ton

- Türkçe yazılır. Teknik terimler (playbook, role, commit, pull request) çevrilmez.
- Doğrudan ve iddiasız: "Bu yaklaşım şu nedenle seçildi" — "devrim niteliğinde" değil.
- Emoji yok (durum tabloları hariç: ✅ 🔄 ⬜).
- Süre tahmini yazma ("2 gün sürer" gibi).

## Kanıt Zorunluluğu

Referans depo hakkındaki her iddia doğrulanabilir olmalıdır.

```markdown
Pipeline `trigger: none` kullanır, yani otomatik tetikleme yoktur.
(Kaynak: azure-pipelines/nonprod/azure-pipelines-playbook.yml)
```

Doğrulanmamış bilgi "varsayım" olarak açıkça etiketlenir ve WP-04 doğrulama
listesine eklenir.

## Bağlantı Biçimi

- Depo içi göreli yol: `[docs/04-ansible-ir-spec.md](04-ansible-ir-spec.md)`
- Bağlantı metni hedefle aynı olmalı (satır numarası yoksa)
- Var olmayan dosyaya bağlantı verilmez

## Birlikte Güncellenecek Dokümanlar

| Değişiklik | Güncellenecek |
|---|---|
| Yeni/değişen endpoint | [09-api-contract.md](09-api-contract.md) |
| Yeni tablo veya kolon | [03-domain-model.md](03-domain-model.md) |
| Parser/IR davranışı | [04-ansible-ir-spec.md](04-ansible-ir-spec.md) |
| Yeni ayar değişkeni | [11-deployment-rancher.md](11-deployment-rancher.md) + `.env.example` |
| WP tamamlandı | [13-roadmap-wbs.md](13-roadmap-wbs.md) durum sütunu |
| Yeni terim | [15-glossary.md](15-glossary.md) |
| Mimari karar | Yeni ADR |

## ADR Kuralları

Yeni ADR şu durumlarda yazılır: kütüphane değişimi, katman sınırı değişikliği,
veri modeli yaklaşımı değişikliği, güvenlik ödünleşimi.

Dosya adı: `docs/adr/ADR-NNNN-kisa-baslik.md` (sıra numarası atlanmaz).

Zorunlu bölümler:
```markdown
# ADR-NNNN: Başlık
- **Durum:** Kabul edildi | Önerildi | Değiştirildi (ADR-XXXX tarafından)
- **Tarih:** YYYY-MM-DD

## Bağlam
## Değerlendirilen Seçenekler   (en az 2, tablo halinde)
## Karar
## Gerekçe
## Sonuçlar                     (olumlu ve olumsuz)
```

Kabul edilmiş bir ADR **düzenlenmez**; yerine yeni ADR yazılır ve eskisinin
durumu "Değiştirildi" yapılır.

## WBS Bakımı

[13-roadmap-wbs.md](13-roadmap-wbs.md) canlı bir belgedir. Bir WP bitince
durum işareti aynı PR içinde güncellenir. Kapsam dışı bırakılan fikirler
silinmez, "Not Düşülenler" bölümüne taşınır.

## Kod Örnekleri

- Dil etiketi her zaman belirtilir.
- Doğru/yanlış çiftleri `# DOGRU` / `# YANLIS` yorumlarıyla işaretlenir.
- Örnekler gerçek koddan alınır; uydurma API kullanılmaz.

## Bitti Tanımı

- [ ] Tüm bağlantılar var olan dosyalara gidiyor
- [ ] Terimler [15-glossary.md](15-glossary.md) ile tutarlı
- [ ] İddiaların kaynağı belirtilmiş veya "varsayım" etiketli
- [ ] Bağlı dokümanlar (yukarıdaki tablo) güncellendi
