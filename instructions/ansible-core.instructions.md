---
description: "Use when working on the Ansible Intelligence Core: YAML parser, serializer, IR nodes, role schema inference, dependency graph, validators. Covers lossless round-trip contract, ruamel.yaml rules and golden tests."
applyTo: "backend/app/ansible/**"
---

# Ansible Intelligence Core Kuralları

> **Bu projenin en kritik alanıdır.** Kod yazmadan önce
> [docs/04-ansible-ir-spec.md](../../docs/04-ansible-ir-spec.md) dosyasını oku.

## Amaç ve Sınırlar

Bu paket YAML'ı **anlar**, **temsil eder** ve **kayıpsız geri yazar**.

| Yapar | Yapmaz |
|---|---|
| YAML parse ve serialize | Ağ çağrısı |
| IR node üretimi | Veritabanı erişimi |
| Rol şeması çıkarımı | Git komutu |
| Bağımlılık grafı analizi | Dosya yazma |
| Dosyalar arası doğrulama | Ansible çalıştırma |

**Saflık kuralı:** Bu paket yan etkisizdir. Dosya içeriği **çağıran tarafından**
metin olarak verilir. Bu sayede golden testler milisaniyeler içinde ve deterministik çalışır.

## Zorunlu Kurallar

### 1. Kayıpsız Gidiş-Dönüş Sözleşmesi

Bir YAML dosyası okunup değiştirilmeden geri yazıldığında **byte düzeyinde özdeş**
olmalıdır. Korunacaklar: yorumlar, tırnak stili, anahtar sırası, girinti, boş satırlar,
blok skaler stili, satır sonu karakteri.

### 2. Yeniden Üretim Değil, Cerrahi Metin Yaması ★

> Ölçüldü: tam yeniden üretim 477 dosyanın **%0-1**'inde birebir kalıyor.
> Ayrıntı: [ADR-0007](../../docs/adr/ADR-0007-surgical-text-patching.md)

```python
# DOGRU - orijinal metin uzerinde hedefli aralik degisimi
document = parse_document(text)
span = document.span("/0/vars/paths/0")
new_text = serialize_document(
    document, [TextEdit(span.start, span.end, render_scalar(value))]
)

# YANLIS - tum dosya yeniden uretilir, girinti ve --- kaybolur
yaml.dump(document.data, stream)
```

Orijinal metin gerçeğin kaynağıdır. `ruamel.yaml` yalnızca **okuma**, **konum
tespiti** ve **tek değer üretimi** için kullanılır.

### 3. Yalnızca ruamel.yaml Round-Trip

```python
# DOGRU
from ruamel.yaml import YAML
yaml = YAML(typ="rt")
yaml.preserve_quotes = True

# YANLIS - bu satirlarin hicbiri yazilmaz
import yaml as pyyaml
pyyaml.safe_dump(data)
YAML(typ="safe")
```

### 4. Ayrıştırılamayan Dosya İstisna Fırlatmaz

Referans depoda gerçekten bozuk dosyalar var (3 adet). `parse_document` bunlar için
`parse_error` dolu bir belge döndürür; platform çalışmaya devam eder, dosya
salt-okunur gösterilir. Yalnızca **yazma** girişimi hata verir.

### 4. Anlamadığını Bozma

Bir yapı forma dönüştürülemiyorsa `NodeType.RAW` olur ve aynen korunur.
"Yaklaşık olarak anlamak" ve yeniden üretmek **yasaktır**.

Node'un tamamının `RAW` olması **son çaredir**, ilk çare değil: görev bir modüle
çözümlenemiyorsa (sıfır veya birden çok modül anahtarı), `roles:` girdisi rol değilse,
`include_tasks` hedefi belirlenemiyorsa. Her `RAW` node `lock_reason` alanında
**neden** anlaşılamadığını kullanıcıya açıklamak zorundadır; boş sebep kabul edilmez.

### 5. Kısmi Kilitleme Tercih Edilir

Kilitlenen genellikle **parametredir, node değil**. Bir `ROLE` veya `MODULE` node'unun
bazı parametreleri forma uygun, bazıları değilse — node tipi değişmez; yalnızca
sorunlu parametre kilitlenir. 24 parametrelik bir formu tek bir değer yüzünden kaybetme.

Bir parametre yalnızca iki durumda kilitlenir:

| Durum | Sebep |
|---|---|
| Jinja **ifadesi** içeriyor (`{%`) | Kontrol akışı forma sığmaz |
| **Çok satırlı** değer (gömülü PowerShell vb.) | Metin editörü gerekir |

Basit değişken ikamesi (`{{ x }}`) **kilitlenmez** — yalnızca `is_templated` olarak
işaretlenir. Depoda çok yaygındır; kilitlemek formları kullanılmaz hale getirir.

### 6. Jinja Analizi AST ile, Regex ile Değil

```python
# DOGRU
from jinja2 import Environment, nodes
ast = Environment().parse(template_text)
variables = {n.name for n in ast.find_all(nodes.Name)}

# YANLIS - ic ice filtreler ve bloklarda sessizce yanilir
variables = re.findall(r"\{\{\s*(\w+)", template_text)
```

Dışlanacak adlar: `item`, `ansible_*`, `inventory_hostname`, `hostvars`, `groups`,
`omit`, `role_path`, ve `register` ile tanımlanmış yerel değişkenler.

### 7. Node Kimlikleri Deterministik

Biçim: `<depo içi yol>#<yaml pointer>` — örn. `playbooks/x.yml#/0/roles/1`.
Aynı dosya iki kez parse edildiğinde aynı kimlikler üretilmelidir.

### 8. Yazma Sonrası Doğrulama

Serializer, ürettiği metni tekrar parse eder ve anlamsal eşitliği kontrol eder.
Eşit değilse yazma **iptal edilir** ve hata fırlatılır.

## Bağımlılıklar

| İzinli | Yasak |
|---|---|
| `ruamel.yaml`, `jinja2`, `pydantic` | `httpx`, `sqlalchemy`, `git`, `fastapi` |
| `app.core.errors`, `app.core.paths` | `app.services.*`, `app.db.*`, `app.ado.*` |
| Standart kütüphane (saf kullanım) | Dosya **yazma** işlemleri |

## Bitti Tanımı

`app/ansible/` üzerinde bir değişiklik şu koşullarda tamamlanmıştır:

- [ ] `pytest tests/golden -v` yeşil **ve** `skipped` içermiyor
- [ ] `pytest tests/unit -k ansible` yeşil
- [ ] Kapsam ≥ %90
- [ ] `mypy --strict app/ansible` temiz
- [ ] Yeni node tipi eklendiyse: kapsam testi yazıldı
- [ ] Yeni doğrulayıcı eklendiyse: pozitif **ve** negatif durum testi yazıldı
- [ ] Parser davranışı değiştiyse: [docs/04](../../docs/04-ansible-ir-spec.md) güncellendi

## İlgili Dokümanlar

- [docs/04-ansible-ir-spec.md](../../docs/04-ansible-ir-spec.md) — IR şartnamesi ★
- [docs/05-role-schema-inference.md](../../docs/05-role-schema-inference.md) — şema çıkarımı
- [docs/14-testing-strategy.md](../../docs/14-testing-strategy.md) — altın testler
- [ADR-0001](../../docs/adr/ADR-0001-yaml-source-of-truth.md) · [ADR-0002](../../docs/adr/ADR-0002-ruamel-roundtrip.md) · [ADR-0005](../../docs/adr/ADR-0005-schema-inference-over-manual-specs.md)
