# 05 — Rol Şeması Çıkarımı

## 1. Problem

Referans depodaki 65 rolün **hiçbirinde** parametre tanımı yoktur:

```
roles/createWebSiteApp/
├── tasks/
│   ├── main.yml                      # state'e göre dağıtım
│   ├── createWebSiteApp.yml
│   ├── createWebSiteAppRecursive.yml
│   └── removeWebSiteApp.yml
└── (defaults/ yok, meta/ yok, README yok)
```

Değişkenler yalnızca görev dosyalarının içinde `{{ physical_path }}` gibi kullanılır.
Bir rolün hangi parametreleri aldığını öğrenmenin tek yolu, tüm görev dosyalarını okumaktır.

Arayüzün form üretebilmesi için şema gerekir. İki yol vardı:

| Yol | Değerlendirme |
|---|---|
| Her role elle `meta/argument_specs.yml` yazmak | 65 rol × ortalama 8 parametre; günler sürer, referans depoyu değiştirmeyi gerektirir (yasak), ve elle yazılan şema kodla senkronsuz kalır |
| **Otomatik çıkarım** | Seçilen yol. Kod değiştiğinde şema kendiliğinden güncellenir |

Karar: [ADR-0005](adr/ADR-0005-schema-inference-over-manual-specs.md)

## 2. İki Kaynaklı Çıkarım

```
   Tanım tarafı                          Kullanım tarafı
   roles/<ad>/tasks/**.yml               120 playbook + 18 composite rol
   ─────────────────────                 ──────────────────────────────
   Hangi değişkenler okunuyor?           Hangi değerler fiilen veriliyor?
   Zorunlu mu, varsayılanı var mı?       Tip ne? Enum adayları neler?
   Dağıtıcı (dispatcher) var mı?         Ne sıklıkta kullanılıyor?
            │                                      │
            └──────────────┬───────────────────────┘
                           ▼
                     RoleSchema
              (varyant başına, güven skorlu)
```

Tek başına hiçbiri yeterli değildir: tanım tarafı tipi bilemez, kullanım tarafı
zorunluluğu bilemez. Birleşimi güvenilir sonuç verir.

## 3. Tanım Tarafı Analizi

Rolün tüm `tasks/**.yml` dosyaları okunur; her Jinja ifadesi `jinja2.Environment.parse()`
ile AST'e çevrilir ve gezilir. **Regex kullanılmaz** — iç içe filtreler ve blok yapıları
regex ile güvenilir çözülemez.

### Çıkarılan Bilgiler

| Desen | Çıkarım |
|---|---|
| `{{ physical_path }}` | Parametre var, **zorunlu** (varsayılan yok) |
| `{{ state \| default('started') }}` | Parametre var, **opsiyonel**, varsayılan `started` |
| `{{ pool_password \| default(omit) }}` | Opsiyonel, atlanabilir (omit) |
| `{{ item.name }}` | `item` döngü değişkenidir, **parametre değildir** — dışlanır |
| `{{ ansible_os_family }}` | Ansible olgusu (fact), **parametre değildir** — dışlanır |
| `{{ inventory_hostname }}` | Ansible özel değişkeni — dışlanır |
| `register: _root_ca_cert` | Çıktı değişkeni; `produces` kümesine eklenir |
| `when: state \| default('x') == 'y'` + `include_tasks` | **Dağıtıcı tespiti** |

### Dışlanan Değişken Adları

Ansible'ın kendi değişkenleri parametre sayılmaz:
`item`, `ansible_*`, `inventory_hostname`, `hostvars`, `groups`, `group_names`,
`play_hosts`, `omit`, `role_path`, `playbook_dir`, ve `register` ile tanımlanmış
her yerel değişken.

### Dağıtıcı Tespiti

`tasks/main.yml` dosyası şu deseni içeriyorsa rol **dağıtıcıdır**:

```yaml
- include_tasks: createWebSiteApp.yml
  when: ansible_os_family == "Windows" and state | default('started') == "started"
- include_tasks: createWebSiteAppRecursive.yml
  when: ... state | default('started') == "recursive"
- include_tasks: removeWebSiteApp.yml
  when: ... state | default('started') == "absent"
```

Sonuç: `dispatcher_param = "state"`, varyantlar `started` / `recursive` / `absent`.
Her varyant için **yalnızca o dala ait görev dosyası** analiz edilir; böylece varyant
başına doğru parametre kümesi elde edilir.

Bu, `createWebSiteApp` rolündeki gerçek sorunu çözer:

| Varyant | `appNames` tipi | `physical_path` davranışı |
|---|---|---|
| `@started` | `list[str]` | Site yolu = `physical_path + websiteNamePool` (birleştirme) |
| `@recursive` | `list[{name, pool}]` | Site yolu = `physical_path` (birleştirme yok) |
| `@absent` | — | kullanılmaz |

## 4. Kullanım Tarafı Analizi

120 playbook ve 18 composite roldeki **her** `include_role` / `roles:` çağrısının `vars`
bloğu toplanır.

```yaml
- include_role:
    name: iis_apppool
  vars:
    state: present
    dotnetcore: true
    pool_userName: "NetworkService"
    pools: [OBA.Web.InternetBanking, ...]
```

### Tip Çıkarımı

Gözlenen tüm değerlerden en dar uyumlu tip seçilir:

| Gözlem | Çıkarılan tip |
|---|---|
| Hepsi `true`/`false` | `bool` |
| Hepsi tamsayı | `int` |
| Hepsi düz metin | `str` |
| Hepsi düz metin listesi | `list[str]` |
| Hepsi aynı anahtarlara sahip sözlük listesi | `list[obj]` + alt şema |
| Karışık | `any` (güven skoru düşer) |

### Enum Adayları

Bir parametre için gözlenen **benzersiz değer sayısı ≤ 6** ve tümü metin ise, enum
adayı üretilir:

```
state        → [present, absent, started, recursive]     (4 benzersiz, 89 kullanım)
dotnetcore   → [true, false]                             (bool olarak zaten)
websiteProtocol → [http, https, https_shell, absent]     (4 benzersiz, 31 kullanım)
```

### Kullanım İstatistiği

Her parametre için "kaç çağrıda geçti" sayılır. Arayüzde sık kullanılan parametreler
formun üstünde, nadir olanlar "Gelişmiş" bölümünde gösterilir.

### Örnek Değerler

Gerçek kullanımlardan en fazla 3 örnek saklanır ve forma placeholder olarak konur.
Bu, "bu alana ne yazmalıyım?" sorusunu doğrudan cevaplar.

## 5. Birleştirme ve Güven Skoru

```
Tanım tarafı: {physical_path, state, websiteName, appNames, logPath, createApp, ...}
Kullanım tarafı: {state: enum[4], appNames: list[obj], physical_path: str, ...}
                          │
                          ▼
            Birleşim + çelişki tespiti + güven skoru
```

| Güven | Koşul | Arayüz davranışı |
|---|---|---|
| **high** | Tanım ve kullanım uyuşuyor, ≥3 kullanım örneği, çelişki yok | Normal form |
| **medium** | Az kullanım (1-2) veya bazı parametreler yalnızca tek tarafta görüldü | Form + bilgi rozeti |
| **low** | Çelişki var, karışık tipler, veya hiç kullanım örneği yok | "Doğrulanmamış şema" uyarısı; kullanıcı ham YAML'a geçebilir |

### Çelişki Örnekleri
- Tanım tarafı zorunlu diyor ama kullanımların bir kısmında parametre verilmemiş.
- Aynı parametre bazı çağrılarda metin, bazılarında liste.
- Kullanımda olup tanımda hiç okunmayan parametre (ölü parametre — `INFO` uyarısı).

## 6. Elle Geçersiz Kılma (Override)

Otomatik çıkarım yanılabilir. Yönetici rolü, şemayı arayüzden düzeltebilir:

- Parametre açıklaması ekleme (Türkçe, kullanıcıya gösterilir)
- Tip düzeltme
- Zorunluluk işaretini değiştirme
- Enum değerlerini düzenleme
- Parametreyi gizleme (gerçekte kullanılmayan)

Geçersiz kılmalar `role_schema_override` tablosunda rol adı + varyant ile saklanır ve
indeksleme sonrası çıkarılan şemanın **üzerine** uygulanır. Böylece kod değişse bile
insan emeği kaybolmaz.

Faz 8'de (WP-82) bu geçersiz kılmalar `meta/argument_specs.yml` olarak dışa aktarılıp
referans depoya ayrı bir PR ile kazandırılabilir — böylece bilgi Ansible'ın kendi
standardına da geçer.

## 7. Çıktı Modeli

```python
class RoleParam(BaseModel):
    name: str
    type: ParamType                  # str | int | bool | list_str | list_obj | any
    required: bool
    default: Any | None
    enum: list[str] | None
    item_schema: dict[str, ParamType] | None   # list_obj icin
    description: str | None          # yalnizca override'dan gelir
    examples: list[Any]              # gercek kullanimlardan en fazla 3
    usage_count: int


class RoleSchema(BaseModel):
    role: str
    source: Literal["roles", "roles_custom"]
    variant: str | None              # "started" | "recursive" | ...
    dispatcher_param: str | None     # "state"
    params: list[RoleParam]
    produces: list[str]              # register degiskenleri
    consumes: list[str]              # baska node'lardan bekledigi degiskenler
    confidence: Literal["high", "medium", "low"]
    warnings: list[str]
    task_files: list[str]
```

`produces` ve `consumes` alanları, [04-ansible-ir-spec.md](04-ansible-ir-spec.md)
bölüm 6.2'deki örtük bağımlılık grafını besler.

## 8. Hedef ve Doğrulama

**Hedef (K2):** 65 rolün **≥%80'i** için `high` veya `medium` güvenli şema üretilmeli.

Referans doğrulama kümesi — bu 10 rol için beklenen şema snapshot testiyle sabitlenir:

| Rol | Beklenen sonuç |
|---|---|
| `create_dir` | 1 parametre: `paths: list[str]`, zorunlu, güven `high` |
| `createWebSiteApp` | **3 varyant**; `@recursive` içinde `appNames: list[obj{name,pool}]` |
| `iis_apppool` | `state` enum, `dotnetcore: bool`, `pools: list[str]`, `pool_userName` opsiyonel |
| `iis_binding_http` | **4 varyant** (`http`/`https`/`https_shell`/`absent`); `consumes: [_root_ca_cert]` |
| `importCertificate` | `certPath`, `certPassword`, `unCertPermisson`; `produces: [_root_ca_cert]` |
| `copyFile_Multiple` | `copy_files: list[obj{source,destination,remoteSearch}]`, `isrun: bool` |
| `installUninstallPackage` | `appList: list[obj]` içinde **7 opsiyonel** anahtar |
| `createCertStoreDsc` | `tasks_from` ile iki giriş noktası → 2 varyant |
| `features_for_iis` | **0 parametre** (yapılandırmasız rol) |
| `addTaskScheduler` | 9 düz parametre, ikisi vault referansı |

Ek doğrulama: çıkarım çalıştırıldığında **hiçbir rol için istisna fırlatılmamalı**;
analiz edilemeyen rol `low` güvenle ve uyarı listesiyle dönmeli.

## 9. Performans

Tam çıkarım (65 rol + 120 playbook taraması) **< 10 saniye** sürmelidir.
Artımlı indekslemede yalnızca değişen rolün şeması yeniden hesaplanır; ancak kullanım
tarafı istatistikleri tüm depoyu ilgilendirdiğinden, playbook değişikliklerinde
etkilenen rollerin şemaları da tazelenir.

## 10. Sınırlar

| Durum | Davranış |
|---|---|
| Rol hiç kullanılmamış | Yalnızca tanım tarafı; tip `any`, güven `low` |
| Parametre yalnızca Jinja ifadesi içinde dolaylı kullanılıyor | Tespit edilir ama tip `any` |
| Dinamik rol adı (`name: "{{ rol_degiskeni }}"`) | Node `ROLE` kalır ama şema aranmaz; parametreler şemasız metin alanı olarak gösterilir |
| İç içe dağıtıcı (dağıtıcı içinde dağıtıcı) | Yalnızca birinci seviye; ikinci seviye uyarı üretir |
| `tasks_from` ile farklı giriş noktası | Ayrı varyant olarak ele alınır |
