# ADR-0002 — YAML İşlemede ruamel.yaml Round-Trip Modu

- **Durum:** Kabul edildi — kapsamı [ADR-0007](ADR-0007-surgical-text-patching.md) ile **daraltıldı**
- **Tarih:** 2026-09-30
- **İlgili:** [ADR-0001](ADR-0001-yaml-source-of-truth.md) ·
  [ADR-0007](ADR-0007-surgical-text-patching.md)

> **Güncelleme (2026-09-30):** Bu ADR'nin "tam yeniden üretim byte-identical olur"
> varsayımı ölçümle çürütüldü (477 dosyanın %0-1'i). `ruamel.yaml` kullanımı devam
> ediyor ancak yalnızca **okuma, konum tespiti ve değer üretimi** için. Dosyanın
> tamamını `yaml.dump` ile yeniden yazmak artık yasaktır; yerine cerrahi metin
> yaması kullanılır. Ayrıntı: [ADR-0007](ADR-0007-surgical-text-patching.md).

## Bağlam

[ADR-0001](ADR-0001-yaml-source-of-truth.md) gereği, bir YAML dosyası okunup geri
yazıldığında **byte düzeyinde** aynı kalmalıdır.

Python'da üç seçenek değerlendirildi:

| Kütüphane | Yorumlar | Tırnak stili | Anahtar sırası | Boş satırlar |
|---|---|---|---|---|
| **PyYAML** | ✗ Kaybeder | ✗ Kaybeder | ✗ Kaybeder (varsayılan sıralar) | ✗ Kaybeder |
| **ruamel.yaml** (`typ="safe"`) | ✗ Kaybeder | ✗ Kaybeder | ✓ Korur | ✗ Kaybeder |
| **ruamel.yaml** (`typ="rt"`) | ✓ Korur | ✓ Korur | ✓ Korur | ✓ Korur |

Referans depodaki gerçek bir örnek:

```yaml
# Update machine.config - processModel satiri
- name: Role in role - changeLineinFile
  include_role:
    name: changeLineinFile
  vars:
    state: 'present'        # tirnakli — bilincli
    dotnetcore: true        # tirnaksiz
```

PyYAML ile okunup yazıldığında: yorum kaybolur, `'present'` → `present` olur,
anahtarlar alfabetik sıralanır. Sonuç: her kaydetmede anlamsız ve devasa bir diff.

## Karar

**`ruamel.yaml` round-trip modu (`YAML(typ="rt")`) tek YAML işleme yöntemidir.**

Yasaklananlar:
- `yaml.safe_dump` / `yaml.dump` (PyYAML)
- `ruamel.yaml` `typ="safe"` veya `typ="unsafe"` modları
- `json.dumps` ile YAML üretimi
- Elle string birleştirerek YAML oluşturma

Zorunlu yapılandırma:

```python
yaml = YAML(typ="rt")
yaml.preserve_quotes = True   # tirnak stilini korur
yaml.width = 4096             # otomatik satir sarmayi engeller
yaml.indent(mapping=..., sequence=..., offset=...)   # kaynaktan tespit edilir
```

## Gerekçe

Bu bir tercih değil, **gerekliliktir**. Round-trip sözleşmesi olmadan proje temel
vaadini karşılayamaz; ve `ruamel.yaml` bu yeteneği sunan tek olgun Python kütüphanesidir.

Girinti ayarlarının kaynak dosyadan tespit edilmesi gerekir çünkü depoda tek tip
girinti yoktur (liste tireleri bazı dosyalarda hizalı, bazılarında değil).

## Sonuçlar

**Olumlu**
- Byte düzeyinde koruma mümkün olur.
- Diff'ler minimal ve incelenebilir kalır.
- Yorumlar korunur — bunlar genellikle kritik operasyonel bilgi taşır.

**Olumsuz**
- `ruamel.yaml` PyYAML'dan yavaştır (~3 kat). Kabul edilebilir: indeksleme arka planda
  ve artımlı çalışır.
- API'si daha karmaşık (`CommentedMap`, `CommentedSeq`).
- Tip ipuçları zayıf; `mypy --strict` altında yardımcı tip tanımları gerekir.

**Riskler**
- Kütüphanenin bakım durumu. Azaltım: YAML işlemleri `app/ansible/parser.py` ve
  `serializer.py` içinde kapsüllenir; değişim gerekirse tek noktada yapılır.

## Uygulama

- Statik kontrol: `yaml.dump`, `safe_dump` kullanımını yakalayan ruff kuralı ve
  `tests/unit/test_no_unsafe_yaml.py`.
- Serializer, yazma sonrası üretilen metni tekrar parse eder ve anlamsal eşitliği
  doğrular; eşit değilse yazma iptal edilir.
- Ayrıntı: [docs/04-ansible-ir-spec.md](../04-ansible-ir-spec.md) bölüm 8.
