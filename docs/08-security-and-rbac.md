# 08 — Güvenlik ve Yetkilendirme

## 1. Tehdit Modeli

### Korunan Varlıklar

| Varlık | Neden kritik |
|---|---|
| Üretim sunucularının yapılandırması | Yanlış değişiklik bankacılık uygulamalarını durdurabilir |
| Azure DevOps deposu | Kaynak kodun bütünlüğü |
| Vault secret'ları | Sertifika parolaları, servis hesabı kimlikleri |
| ADO PAT | Depoya yazma ve build tetikleme yetkisi |
| Denetim izi | Olay sonrası inceleme için bütünlüğü şart |

### Tehdit Aktörleri

| Aktör | Yetenek | Ana risk |
|---|---|---|
| Kötü niyetli olmayan kullanıcı | Arayüze erişim | Yanlışlıkla prod'u bozmak |
| Yetkisiz iç kullanıcı | Ağ erişimi | Yetki yükseltme, izinsiz çalıştırma |
| Ele geçirilmiş hesap | Geçerli oturum | Zararlı playbook merge/çalıştırma |
| Ele geçirilmiş pod | Kod çalıştırma | PAT ve DB kimliklerini sızdırmak |

### Temel Savunma Hatları

1. **Platform doğrudan hiçbir sunucuya dokunamaz.** Tüm değişiklikler insan onaylı PR'dan
   ve mevcut pipeline'dan geçer.
2. **Platform vault değerlerini hiç görmez.** Parola secure file olarak yalnızca agent'ta.
3. **Platform merge edemez.** PAT'e merge yetkisi verilmez.
4. **`main`'e yazma yapısal olarak imkânsız.** Branch adı doğrulaması + çalışma zamanı
   kontrolü + test.

## 2. OWASP Top 10 Karşılıkları

### A01 — Broken Access Control

- Yetki kontrolü **servis katmanında** yapılır, router'da değil. Router'ı atlayan bir
  çağrı bile yetkisiz iş yapamaz.
- Her yetki kararı `(kullanıcı, eylem, ortam)` üçlüsü üzerinden verilir.
- Varsayılan **ret**: açıkça izin verilmemiş her şey yasaktır.
- Nesne düzeyinde kontrol: kullanıcı yalnızca kendi taslaklarını düzenleyebilir
  (admin hariç).

```python
# DOGRU - servis katmaninda
async def trigger_run(self, user: User, playbook: str, env: Environment) -> Run:
    self._authz.require(user, Action.RUN, env)
    ...

# YANLIS - yalnizca router'da dekorator
@router.post("/runs", dependencies=[Depends(require_role("editor"))])
```

### A02 — Cryptographic Failures

- Parolalar **argon2id** ile özetlenir (passlib varsayılan parametreleri).
- JWT en az 32 baytlık bir sır ile imzalanır; üretimde kısa sır uygulamayı başlatmaz.
- Token `httpOnly` + `Secure` + `SameSite=Strict` çerezde tutulur — `localStorage`'da değil.
- TLS doğrulaması **asla kapatılmaz**. İç CA için bundle mount edilir.

### A03 — Injection

| Tür | Önlem |
|---|---|
| SQL | Yalnızca SQLAlchemy parametreli sorgular; string birleştirme yok |
| Komut | Git işlemleri GitPython API'si; `subprocess` + shell yok |
| Path traversal | `app/core/paths.py` doğrulayıcısı; `..` reddedilir, allowlist zorunlu |
| YAML | `ruamel.yaml(typ="rt")` — `yaml.load` ile keyfi nesne oluşturma yok |
| Jinja | Kullanıcı şablonu **render edilmez**, yalnızca AST'e ayrıştırılır (çalıştırma yok) |
| Log injection | Log'a yazılan kullanıcı verisinde satır sonu karakterleri kaçırılır |

```python
ALLOWED_ROOTS = (
    "playbooks", "roles", "roles_custom", "inventory",
    "group_vars", "templates", "azure-pipelines",
)

def validate_repo_path(raw: str) -> PurePosixPath:
    """Depo ici gorece yolu dogrular; traversal ve allowlist disini reddeder."""
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise UnsafePathError(raw)
    if not path.parts or path.parts[0] not in ALLOWED_ROOTS:
        raise UnsafePathError(raw)
    return path
```

### A04 — Insecure Design

- Değişiklik yolu tasarım gereği asenkron ve onaylıdır: taslak → diff → PR → insan merge.
- Prod çalıştırma ikinci bir kişinin onayını gerektirir (dört göz ilkesi).
- Doğrulayıcılar yanlış yapılandırmayı **çalıştırmadan önce** yakalar.

### A05 — Security Misconfiguration

- Tüm yapılandırma ortam değişkenlerinden; kodda sabit URL/parola yok.
- Üretimde başlangıç kontrolleri: zayıf JWT sırrı, boş PAT, `debug` açık → uygulama başlamaz.
- Container non-root kullanıcı ile çalışır, salt-okunur kök dosya sistemi hedeflenir.
- CORS yalnızca bilinen kaynaklara açıktır; `*` kullanılmaz.
- Hata yanıtları yığın izi (stack trace) içermez; `request_id` ile log'a bağlanır.

### A06 — Vulnerable Components

- `pip-audit` ve `npm audit --audit-level=high` CI'da **bloklayıcıdır**.
- Bağımlılıklar üst sınırla sabitlenir; major yükseltmeler ayrı PR'da.

### A07 — Authentication Failures

- Giriş denemelerine hız sınırı (IP + kullanıcı bazlı).
- Genel hata mesajı: «Kullanıcı adı veya parola hatalı» — hangisinin yanlış olduğu sızdırılmaz.
- Oturum süresi kısa + yenileme (refresh); çıkışta token geçersiz kılınır.
- Yerel parolalar için minimum uzunluk ve karmaşıklık; LDAP'a geçişte bu katman devre dışı kalır.

### A08 — Software and Data Integrity Failures

- Commit'ler servis hesabıyla atılır; gerçek kullanıcı trailer ve denetim kaydında.
- `main`'e doğrudan yazma imkânsız; tüm değişiklikler PR'dan geçer.
- Konteyner imajları sabitlenmiş digest ile; Harbor'da imzalanır.
- Yapay zekâ çıktısı doğrudan uygulanmaz — doğrulayıcıdan ve insan onayından geçer.

### A09 — Logging and Monitoring Failures

- `audit_log` tablosu **yalnızca eklenir** (append-only); güncelleme/silme uygulama
  katmanında engellenir.
- Kaydedilen eylemler: giriş/çıkış, başarısız giriş, taslak yayınlama, PR açma,
  çalıştırma tetikleme, onay verme, RBAC değişikliği, şema geçersiz kılma, ayar değişikliği.
- Her kayıt: zaman, aktör, eylem, hedef, ortam, `request_id`, IP.
- Log'lar JSON olarak `stdout`'a; maskeleme filtresi tüm işlemcilere bağlı.

### A10 — Server-Side Request Forgery

- Giden HTTP isteklerinin base URL'i **yalnızca** ayarlardan gelir.
- Kullanıcı girdisinden URL oluşturulmaz; yalnızca yol parçaları eklenir ve bunlar da
  desen doğrulamasından geçer.
- Yönlendirmeler (redirect) takip edilmez (`follow_redirects=False`).
- Giden bağlantılar için ağ politikası (NetworkPolicy) ile hedef kısıtı önerilir.

## 3. Rol Modeli

Dört rol, **ortam kapsamlı** olarak atanır. Bir kullanıcı farklı ortamlarda farklı
rollere sahip olabilir (ör. nonprod'da Editor, prod'da Viewer).

| Rol | Görüntüleme | Taslak düzenleme | PR açma | nonprod çalıştırma | prod çalıştırma | Onay verme | Yönetim |
|---|---|---|---|---|---|---|---|
| **Viewer** | ✓ | — | — | — | — | — | — |
| **Editor** | ✓ | ✓ | ✓ | ✓ | — | — | — |
| **Approver** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| **Admin** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**Yönetim** kapsamı: kullanıcı ve rol atamaları, rol şeması geçersiz kılmaları,
uygulama ayarları, denetim kaydı görüntüleme.

### Ortam Kapsamı

```
user_role_binding: (user_id, role, environment)

trahim → editor   @ nonprod
trahim → editor   @ dmz_nonprod
trahim → viewer   @ prod
mehmet → approver @ *          # tum ortamlar
```

`*` kapsamı yalnızca Admin tarafından atanabilir.

### Dört Göz İlkesi

`prod` ve `dmz_prod` ortamlarında çalıştırma için:
- Tetikleyen kullanıcı ile onaylayan kullanıcı **farklı kişiler olmalıdır**.
- Onay kaydı `run.approved_by` alanında ve denetim izinde tutulur.
- Veritabanı kısıtı: `environment IN ('prod','dmz_prod') → approved_by IS NOT NULL`.

## 4. Kimlik Doğrulama

### MVP: Yerel Kullanıcılar

- Parola argon2id ile özetlenir.
- İlk yönetici hesabı ilk açılışta ortam değişkeninden oluşturulur ve **ilk girişte
  parola değiştirme** zorunludur.
- JWT: `httpOnly` + `Secure` + `SameSite=Strict` çerez, 60 dakika, yenileme mekanizmalı.

### Faz 8: LDAP

`AuthProvider` arayüzü baştan tasarlanmıştır; LDAP eklendiğinde çağıran kod değişmez:

```python
class AuthProvider(Protocol):
    async def authenticate(self, username: str, password: SecretStr) -> AuthResult: ...
    async def get_user_info(self, username: str) -> UserInfo | None: ...
```

LDAP grupları, rol atamalarına eşlenecektir. Geçişte mevcut yerel hesaplar korunur.

## 5. Secret Yönetimi

| Secret | Nerede | Kural |
|---|---|---|
| ADO PAT | Kubernetes Secret → ortam değişkeni | Log'da maskelenir, API yanıtında asla dönmez |
| DB parolası | Kubernetes Secret | Aynı |
| JWT sırrı | Kubernetes Secret | Üretimde ≥32 bayt zorunlu |
| Webhook HMAC sırrı | Kubernetes Secret | Sabit zamanlı karşılaştırma |
| LLM API anahtarı | Kubernetes Secret | Faz 7 |
| **Ansible vault parolası** | **Platformda YOK** | Yalnızca ADO secure file → agent |

### Vault Değişkenleri

Platform vault **değerlerini** hiçbir koşulda okumaz. `/etc/ansible/vault/**` yolunu
açmak kod düzeyinde yasaktır ve bir testle denetlenir.

Arayüzde yalnızca **değişken adları** gösterilir; bunlar playbook'lardaki `{{ }}`
referanslarından türetilir:

```
uat_boa_standardyeni_cert_password      (3 playbook'ta kullanılıyor)
boa_standart_yeni_cert_pass             (5 playbook'ta kullanılıyor)
```

Bu, "hangi vault değişkenini yazmalıyım?" sorusunu, değeri hiç görmeden cevaplar.

### Secret Maskeleme

`structlog` işlemcisi, log'a yazılan tüm sözlüklerde riskli anahtarları maskeler:

```python
SENSITIVE_KEYS = frozenset({
    "password", "passwd", "pwd", "secret", "token", "pat",
    "authorization", "api_key", "apikey", "jwt", "cert_password",
})
```

Ayrıca metin gövdelerinde `Bearer ...`, `Basic ...` ve bağlantı dizesi desenleri maskelenir.

## 6. Frontend Güvenliği

| Konu | Kural |
|---|---|
| XSS | React varsayılan kaçırma. `dangerouslySetInnerHTML` **ESLint ile yasak** |
| Log gösterimi | ANSI→HTML dönüşümü sanitize edilerek yapılır (izinli etiket listesi) |
| Token saklama | `httpOnly` çerez; JavaScript token'a erişemez |
| CSRF | `SameSite=Strict` + durum değiştiren isteklerde özel başlık kontrolü |
| CSP | `default-src 'self'`; Monaco için gereken istisnalar açıkça listelenir |
| Bağımlılık | `npm audit` CI'da bloklayıcı |

## 7. Container ve Ağ

- Non-root kullanıcı (UID 10001), `allowPrivilegeEscalation: false`.
- Salt-okunur kök dosya sistemi; yazılabilir yalnızca PVC ve `/tmp`.
- Tüm `capabilities` düşürülür.
- Kaynak limitleri tanımlı (CPU/bellek).
- NetworkPolicy: giden trafik yalnızca ADO, LLM ve PostgreSQL'e.
- Secret'lar imaja gömülmez; yalnızca çalışma zamanında bağlanır.

## 8. Güvenlik Testleri

| Test | Doğruladığı |
|---|---|
| `test_git_safety.py` | `main`'e push girişimi istisna fırlatır |
| `test_paths.py` | Traversal ve allowlist dışı yollar reddedilir |
| `test_authz_matrix.py` | Rol × eylem × ortam matrisinin tamamı |
| `test_no_vault_read.py` | Kod tabanında vault yolu okuma girişimi yok |
| `test_logging_mask.py` | Riskli anahtarlar log'da maskelenir |
| `test_no_tls_bypass.py` | Kod tabanında `verify=False` deseni yok |
| `test_four_eyes.py` | prod çalıştırma onaysız başlatılamaz |
| `test_layering.py` | Katman bağımlılık yönü ihlal edilmemiş |

## 9. Olay Müdahale

Bir güvenlik olayı şüphesinde:

1. **İzole et** — Deployment'ı 0 replikaya indir. Pipeline'lar etkilenmez, çalışmaya devam eder.
2. **PAT'i iptal et** — Azure DevOps'ta token'ı geçersiz kıl; platformun yazma yeteneği biter.
3. **İncele** — `audit_log` tablosu ve JSON log'lar üzerinden `request_id` ile izle.
4. **Değerlendir** — `ansibleui/*` branch'lerini ve açık PR'ları gözden geçir.
5. **Kurtar** — İndeks türetilmiş veridir, yeniden üretilebilir. Kalıcı veriler için
   PostgreSQL yedeği kullanılır.

Platformun ele geçirilmesi **doğrudan sunucu erişimi sağlamaz**; en kötü durumda
kötü niyetli bir PR açılabilir, o da insan incelemesinden geçmek zorundadır.
