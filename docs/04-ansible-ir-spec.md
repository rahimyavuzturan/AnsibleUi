# 04 — Ansible IR Şartnamesi

> Bu doküman projenin **teknik çekirdeğidir**. `backend/app/ansible/` altında çalışan her
> agent bu dosyayı okumadan kod yazmamalıdır.

## 1. Sözleşme

**Kayıpsız gidiş-dönüş (lossless round-trip):**

> Bir YAML dosyası okunup, hiçbir değişiklik yapılmadan geri yazıldığında,
> sonuç **byte düzeyinde özdeş** olmalıdır.

Korunması zorunlu olanlar:

| Öğe | Örnek |
|---|---|
| Yorumlar | `# Update machine.config` — satır içi ve blok |
| Tırnak stili | `'true'` ≠ `"true"` ≠ `true` |
| Anahtar sırası | `name` → `hosts` → `vars_files` → `roles` |
| Girinti genişliği | 2 boşluk, liste girintisi dahil |
| Boş satırlar | Görevler arası ayırıcı satırlar |
| Blok skaler stili | `\|`, `>`, `\|-`, `>-` |
| Belge işaretleri | Baştaki `---`, sondaki `...` |
| Satır sonu | CRLF / LF (dosyada ne varsa) |
| Bayraklar (anchors/aliases) | `&ad` / `*ad` |

Bu sözleşme `backend/tests/golden/test_roundtrip_golden.py` ile sürekli doğrulanır.
**Bu test kırmızıysa hiçbir şey merge edilmez.**

## 2. Neden Bu Kadar Katı?

Referans depoda görselleştirilemeyen çok sayıda yapı var. Bunları "anlamaya" çalışıp
yeniden üretmek, sessiz bozulmaya yol açar. Bunun yerine: **anlamadığını olduğu gibi bırak.**

Gerçek örnekler:

```yaml
# 1. Jinja kontrol akışı, modül değerinin içinde
processModel.identityType:
  "{% filter trim %}
    {% if item == 'DefaultWebSite' %}ApplicationPoolIdentity
    {% else %}
      {% if pool_userName is undefined %}ApplicationPoolIdentity
      {% elif pool_userName == 'NetworkService' %}NetworkService
      {% else %}SpecificUser{% endif %}
    {% endif %}
  {% endfilter %}"
```

```yaml
# 2. Gömülü PowerShell + Jinja interpolasyonu
win_shell: |
  $binding = Get-WebBinding -Name "{{ websiteName }}" -Protocol https
  if ($binding) { $binding.AddSslCertificate("{{ _thumbprint }}", "My") }
```

```yaml
# 3. Host adına göre dallanan set_fact
- set_fact:
    tsube_binding_hostname: >-
      {%- if inventory_hostname is search('sdl') -%}tsubedev.kuveytturk.com.tr
      {%- elif inventory_hostname is search('stl') -%}tsubetest.kuveytturk.com.tr
      {%- endif -%}
```

Bu **değerlerin** hiçbiri forma dönüştürülemez; üçü de kilitli metin alanı olarak
gösterilir ve dokunulmadan korunur.

Dikkat: kilitlenen **parametredir, node değil**. Yukarıdaki 2. ve 3. örnek yine de
`MODULE` node'u olur; yalnızca `win_shell` / `set_fact` değeri kilitlenir, görevin
`name`, `when`, `tags` gibi alanları düzenlenebilir kalır. Node'un tamamının `RAW`
olması son çaredir (bkz. §4).

## 3. Mimari: Gölge Ağaç

> **Güncelleme (2026-09-30, WP-10):** Bu bölüm ölçüm sonucuna göre revize edildi.
> Gerekçe ve veriler: [ADR-0007](adr/ADR-0007-surgical-text-patching.md).

Parser **üç katman** tutar:

```
┌─────────────────────────────────────────────────────────────┐
│  Katman 0 — Orijinal metin  (GERÇEĞİN KAYNAĞI)             │
│  Dosyanın diskteki hâli. Asla yeniden üretilmez;            │
│  yalnızca hedefli karakter aralıkları değiştirilir.         │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ karakter aralığı (span)
                          │
┌─────────────────────────────────────────────────────────────┐
│  Katman 1 — ruamel.yaml düğüm ağacı  (YAPI + KONUM)        │
│  compose() ile üretilir. Her düğüm için start/end indeksi.  │
│  Ayrıca load() ile CommentedMap/CommentedSeq veri görünümü. │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ referans (kopya değil)
                          │
┌─────────────────────────────────────────────────────────────┐
│  Katman 2 — IR node'ları  (GÖRÜNÜM)                         │
│  Tipli, salt-okunur görünüm. Arayüze bu gönderilir.         │
└─────────────────────────────────────────────────────────────┘
```

**Altın kural:** Dosya **asla yeniden üretilmez**. Düzenleme, orijinal metin üzerinde
bir `TextEdit(start, end, replacement)` olarak uygulanır. Dokunulmayan hiçbir bayt
işlenmez bile — dolayısıyla korunması garantidir.

```python
# DOĞRU — hedefli metin yaması
document = parse_document(text)
span = document.span("/0/vars/paths/0")
edit = TextEdit(span.start, span.end, render_scalar(r"D:\WebSites\Yeni"))
new_text = serialize_document(document, [edit])   # yalnızca o aralık değişti

# YANLIŞ — yeniden üretim (ölçüldü: dosyaların %0-1'i birebir kalıyor)
data = document.data
yaml.dump(data, f)
```

### Neden yeniden üretim değil

477 dosyalık referans depoda `parse → dump` ölçümü:

| Girinti ayarı | Birebir aynı |
|---|---|
| `mapping=2, sequence=4, offset=2` | 0 / 477 |
| `mapping=2, sequence=2, offset=0` | 5 / 477 |

Başlıca neden: `ruamel.yaml` girintiyi belge genelinde tek ayarla uygular, oysa
depodaki dosyalarda **aynı dosya içinde** karma girinti vardır. Ayrıca `---` belge
işareti düşer ve kök seviyesindeki diziler içeri girer.

Konum bilgisi yaklaşımının ölçümü: 474/477 dosya ayrıştırıldı, **18.981 düğüm**,
**0 geçersiz aralık**. Ayrıştırılamayan 3 dosya referans deponun kendi bozuk
dosyalarıdır.

## 4. Node Tipleri

Tek bir `Node` sınıfı ve bir `type` alanı kullanılır (ayrı sınıflar değil): node tipleri
ortak alanların çok büyük kısmını paylaşır ve tip, ağacın üstünde gezerken (`walk()`)
sıkça sınıflandırma yerine karşılaştırma konusudur.

| `NodeType` | Ne zaman üretilir | Arayüz davranışı | Düzenlenebilir alanlar |
|---|---|---|---|
| `PLAY` | Playbook'taki bir oynatma | Başlık kartı; çocukları `roles:` + `tasks:`/`pre_tasks:`/`post_tasks:` | `name`, `hosts`, `vars_files`, `become` |
| `ROLE` | `include_role`/`import_role` **veya** `roles:` girdisi | Form + canvas node | Rol parametreleri |
| `TASK_INCLUDE` | `include_tasks` / `import_tasks` | Alt grafa inilebilir (drill-down) | `include_target`, `when`, `vars` |
| `MODULE` | Tek bir modül anahtarı olan görev (`win_shell`, `debug`, `uri`…) | Genel form; şema Faz 8'de zenginleşir | Modül argümanları |
| `BLOCK` | `block` / `rescue` / `always` | İç içe kapsayıcı | `when`, `become`; çocukları kendi node'ları |
| `RAW` | Yukarıdakilerin hiçbiri — **veya girdi geçersiz** | Kilitli "ham YAML" kartı, Monaco ile metin düzenleme | Ham metnin tamamı |

> **Ölçüm (2026-09-30):** Referans depodaki 474 ayrıştırılabilir dosyada yalnızca **2 node**
> `RAW` oldu ve ikisi de depodaki gerçek bir hatadan kaynaklandı. `RAW`, tasarımda bir
> kaçış kapısı değil, **teşhis aracıdır**: her `RAW` node kendi `lock_reason` alanında
> neden anlaşılamadığını kullanıcıya açıklamak zorundadır.

### Ortak Alanlar

```python
@dataclass(frozen=True)
class Node:
    type: NodeType
    pointer: str               # YAML pointer, ör. "/0/roles/1"
    span: NodeSpan             # Katman 0'daki karakter aralığı (kaynağın tek doğrusu)
    name: str                  # görevin 'name' alanı
    role_name: str | None
    tasks_from: str | None
    include_target: str | None
    module: str | None
    params: dict[str, ParamRef]   # düzenlenebilir parametreler
    keywords: dict[str, Any]      # when / loop / tags / become …
    children: tuple[Node, ...]
    lock_reason: str              # boş değilse node forma dönüştürülemez
    register: str | None          # örtük bağımlılık grafı için (WP-14)
```

Satır numarası **saklanmaz**, `span` üzerinden hesaplanır. Sebep: tek doğru kaynak
Katman 0'daki metindir; satır numarasını ayrıca tutmak ikinci bir gerçeklik yaratır
ve yama sonrası bayatlar.

### Node Kimliği

Biçim: `<depo içi dosya yolu>#<yaml pointer>`

```
playbooks/tsube/install_tsube.yml#/0/roles/1
roles_custom/install_isube/tasks/install_isube_nonprod.yml#/3
roles_custom/install_isube/tasks/install_isube_nonprod.yml#/3/block/0
```

Özellikler:
- **Deterministik** — aynı dosya, aynı kimlikler.
- **Konum tabanlı** — sıra değişirse kimlik değişir. Bu bilinçlidir: taşınan bir node
  farklı bir çalıştırma anlamı taşır (bkz. örtük bağımlılıklar).
- Taslaklar node kimliğine değil **dosya yoluna** bağlanır; yeniden sıralama taslağı bozmaz.

## 5. Node Tipi Kararı

```
Bir görev sözlüğü (task dict) geldiğinde:

1. 'block'/'rescue'/'always' var mı?          → BLOCK (çocukları özüyinelemeli)
2. 'include_role'/'import_role' var mı?      → ROLE
                                               parametreler kardeş 'vars:' altında
3. 'include_tasks'/'import_tasks' var mı?    → TASK_INCLUDE
                                               hedef çözülemezse → RAW
4. Tam olarak BİR modül anahtarı var mı?     → MODULE
5. Diğer her şey (sıfır veya çok modül)      → RAW (sebebiyle birlikte)
```

`roles:` listesindeki girdiler ayrı ele alınır: düz metin (`- pingpong`) veya `role:`
anahtarlı eşleme olabilir. İkinci durumda **parametreler `role:` ile kardeştir**,
`include_role`'deki gibi ayrı bir `vars:` bloğu altında değil. Bu iki farklı konum
karıştırılırsa parametre işaretçileri yanlış yere çıkar ve yama dosyayı bozar.

> **Şema bilinmemesi RAW sebebi DEĞİLDİR.** İlk indeksleme anında hiçbir rolde şema
> yoktur; şema bilinmeyince RAW üretmek tüm depoyu kilitli gösterirdi. Şema (WP-13)
> yalnızca forma *zenginlik* katar — alan tipleri, açılır listeler, zorunluluk. Şema
> yokken node yine `ROLE`'dür ve parametreleri düz metin alanı olarak düzenlenebilir.

### Kısmi Kilitleme

Bir `ROLE` node'unun bazı parametreleri forma uygun, bazıları değilse node yine de
`ROLE` kalır; yalnızca sorunlu parametre **kilitli metin alanı** olarak gösterilir.

Kilitleme ölçütü dar tutulur — yalnızca iki durum:

| Durum | Neden kilitli | Depodaki sayı |
|---|---|---|
| Jinja **ifadesi** (`{% if %}`, `{% for %}`) | Kontrol akışı forma sığmaz | 9 |
| **Çok satırlı** değer (gömülü PowerShell vb.) | Metin editörü gerekir | 59 |

Basit Jinja **değişken ikamesi** (`{{ x }}`) kilitlenmez; yalnızca `is_templated`
olarak işaretlenir ve arayüzde rozetle gösterilir. Bunlar depoda çok yaygındır ve
kilitlemek formları pratikte kullanılmaz hale getirirdi.

```yaml
- include_role:
    name: iis_apppool
  vars:
    state: present                      # ✓ form: açılır liste
    pool_userName: "NetworkService"     # ✓ form: metin
    pools: "{{ dinamik_liste }}"        # ✓ form: metin + "şablon" rozeti
    script: |                           # 🔒 kilitli — çok satırlı
      $x = 1
```

Bu, "ya hep ya hiç" davranışından çok daha kullanışlıdır: 24 parametrelik bir rolde
tek bir çok satırlı değer yüzünden tüm form kaybedilmez.

## 6. Bağımlılık Grafı

### 6.1 Sıra Kenarları (düz çizgi)
Ardışık görevler arasında. Ansible'ın yukarıdan aşağı çalışma sırasını gösterir.

### 6.2 Örtük Veri Kenarları (kesikli çizgi) ★

Referans depodaki en tehlikeli desen:

```yaml
# roles/importCertificate/tasks/importCertificate.yml
  register: _root_ca_cert                              # ← ÜRETİCİ

# roles/iis_binding_http/tasks/iis_binding_https_shell.yml
  _thumbprint: "{{ ... (_root_ca_cert.thumbprints | last) }}"   # ← TÜKETİCİ
```

Binding görevinin sertifika **parametresi yoktur**. Sadece "en son çalışan
`importCertificate`"in bıraktığı değişkeni okur. Node sırası değişirse **yanlış sertifika
bağlanır ve hiçbir hata oluşmaz.**

`graph.py` bunu şöyle ele alır:

1. Her node için `produces: set[str]` (register adları) ve `consumes: set[str]`
   (Jinja AST'inden çıkarılan değişken referansları) hesaplanır.
2. Bir tüketici için, **kendisinden önceki en yakın üretici** bulunur → kesikli kenar.
3. Arayüzde bu kenar "örtük bağımlılık" olarak ve açıklama baloncuğuyla gösterilir.
4. Kullanıcı araya başka bir üretici taşımaya kalkarsa **bloklayıcı uyarı** verilir:

> «Bu taşıma, `iis_binding_http` görevinin farklı bir sertifikayı kullanmasına yol açar.
> `_root_ca_cert` değişkeni şu an `importCertificate (BOA-StandardYeni)` tarafından
> üretiliyor; taşıma sonrası `importCertificate (star_kuveytturk)` üretecek.»

Bu tek özellik, mevcut sistemdeki en pahalı hata sınıfını ortadan kaldırır.

### 6.3 Dosya Kenarları (noktalı çizgi)
`include_tasks` çağrıları. Arayüzde alt grafa inilebilir.

## 7. Doğrulayıcılar

`validators.py` içindeki kurallar. Her biri `BLOCKER` / `WARNING` / `INFO` seviyesi üretir.

| Kural | Seviye | Açıklama |
|---|---|---|
| `V001` dizin-uygulama tutarlılığı | BLOCKER | `createWebSiteApp.appNames` içindeki her girdi için `create_dir.paths` içinde karşılık gelen klasör olmalı. **En sık üretim hatası.** |
| `V002` sertifika-binding zinciri | WARNING | `iis_binding_http` (https/https_shell) öncesinde bir `importCertificate` olmalı |
| `V003` havuz-uygulama tutarlılığı | BLOCKER | `appNames[].pool` içindeki her havuz `iis_apppool.pools` içinde tanımlı olmalı |
| `V004` eksiksiz olmayan dallanma | WARNING | Host adına göre dallanan `set_fact` bloğunda `else` yoksa (tanınmayan host boş değer alır) |
| `V005` şema uyumu | WARNING | `vars` içinde rol şemasında bulunmayan bir anahtar |
| `V006` zorunlu parametre | BLOCKER | Şemada zorunlu işaretli parametre eksik |
| `V007` path birleştirme tuzağı | BLOCKER | `state: started` ile `physical_path` `\` ile bitmiyor (yol birleştirme bozulur) |
| `V008` envanter grubu var mı | BLOCKER | `hosts:` değeri envanterde tanımlı bir grup/host değil |
| `V009` pbList kaydı | WARNING | Playbook ilgili ortamın `pbList` listesinde yok — çalıştırılamaz |
| `V010` vault değişkeni tanımlı mı | WARNING | Referans verilen vault değişkeni, ortamın vault dosyasında bilinen adlar arasında yok |

`V001` ve `V003`, üç `sube` rolünde tekrar tekrar yaşanan somut üretim hatalarını hedefler.

## 8. Serializer Kuralları

> Uygulama: [backend/app/ansible/roundtrip.py](../backend/app/ansible/roundtrip.py)

1. **Asla** tüm dosya yeniden üretilmez. `yaml.dump` yalnızca **tek bir değer**
   üretmek için kullanılır (`render_scalar`), dosya için değil.
2. Değişiklik yoksa `serialize_document` girdinin **birebir aynısını** döndürür.
3. Yamalar konuma göre **tersten** uygulanır; çakışan yamalar reddedilir.
4. Yazma sonrası **doğrulama**: üretilen metin tekrar ayrıştırılır; geçerli YAML
   değilse yazma **iptal edilir** ve `RoundTripError` fırlatılır.
5. Satır sonu stili (CRLF / LF) ve UTF-8 BOM, dosyanın orijinal hâline göre geri yazılır.
6. Ayrıştırılamayan bir dosya **salt-okunurdur**; üzerine yama yazılamaz.

```python
document = parse_document(original_text)

if not document.is_parsed:
    # Bozuk dosya: goster, ama duzenlemeye izin verme
    return ReadOnlyView(document.original_text, document.parse_error)

span = document.span("/0/vars/paths/0")
new_text = serialize_document(
    document,
    [TextEdit(span.start, span.end, render_scalar(new_value, style=span.style))],
)
```

### Düğüm adresleme

Aralıklar RFC 6901 benzeri bir pointer ile adreslenir: `/0/vars/paths/3`.
`/` ve `~` içeren anahtarlar `~1` ve `~0` olarak kaçırılır. Pointer'lar
deterministiktir: aynı dosya iki kez ayrıştırıldığında aynı adresler üretilir.

## 9. Bilinen Sınırlar

| Sınır | Etki | Çözüm |
|---|---|---|
| Çok belgeli YAML (`---` ile ayrılmış) | Depoda yok | Tespit edilirse tüm dosya salt-okunur |
| Anchor/alias (`&`/`*`) | Depoda nadir | ruamel korur; ilgili node `RAW` olur |
| Aşırı uzun satırlar (>4096) | Sarma davranışı | `width` yüksek ayarlanarak önlenir |
| Sekme karakteri girintisi | YAML'da geçersiz | Parse hatası olarak raporlanır, dosya salt-okunur |
| Dosya sonu boşlukları | Fark oluşturabilir | Orijinal bayt dizisi karşılaştırmasıyla yakalanır |

## 10. Test Yükümlülükleri

`app/ansible/` üzerinde çalışan her agent şunları sağlamalıdır:

1. **Golden test yeşil** — referans depodaki tüm `.yml` byte-identical round-trip.
2. **Node kapsamı** — `install_isube_nonprod_freshserver.yml` içindeki 17 üst düzey
   görevin tamamı bir node'a eşlenmeli; hiçbiri kaybolmamalı.
3. **Örtük kenar testi** — `importCertificate → iis_binding_http` kenarı tespit edilmeli.
4. **Doğrulayıcı testi** — `appNames` içinde olup `create_dir` içinde olmayan bir klasör
   `V001` BLOCKER üretmeli.
5. **Yama testi** — bir parametre değiştirildiğinde, dosyanın geri kalanının
   byte-identical kaldığı doğrulanmalı.

Ayrıntı: [14-testing-strategy.md](14-testing-strategy.md)
