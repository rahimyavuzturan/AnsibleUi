# 06 — Git Senkronizasyonu ve Azure DevOps

## 1. Hedef Sistem

Bu **on-prem Azure DevOps Server (TFS)**'tir, `dev.azure.com` değildir. Fark önemlidir:
API sürümleri sınırlıdır, kimlik doğrulama farklıdır, sertifika iç CA'dandır.

| Bileşen | Değer |
|---|---|
| Ana bilgisayar | `ktdevops` (iç ad, HTTPS) |
| Sanal dizin | `/tfs` |
| Koleksiyon | `KT` |
| Proje | `KT.ITAutomation` |
| Depo | `Ansible.appAdminConfig` |
| Git URL | `https://ktdevops/tfs/KT/KT.ITAutomation/_git/Ansible.appAdminConfig` |
| REST kökü | `https://ktdevops/tfs/KT/KT.ITAutomation/_apis` |
| `api-version` | **6.0** (varsayılan; başlangıçta tespit edilir) |

Tüm bu değerler ortam değişkenlerinden gelir (`ANSIBLEUI_ADO_*`); kodda sabit yazılmaz.

### Sürüm Tespiti

Uygulama açılışında bir kez:

```
GET /_apis/?api-version=6.0
```

Yanıttaki desteklenen sürüm aralığı okunur ve istemci buna göre yapılandırılır.
Başarısız olursa `6.0` ile devam edilir ve uyarı log'lanır.

### Kimlik Doğrulama

Personal Access Token (PAT), `Basic` şemasıyla:

```
Authorization: Basic base64(":" + PAT)
```

PAT, Kubernetes Secret'tan gelir. Gerekli kapsamlar: **Code (Read & Write)**,
**Pull Request (Read & Write)**, **Build (Read & Execute)**.

### TLS

İç CA sertifikası `ANSIBLEUI_CA_BUNDLE_PATH` ile mount edilir ve httpx'e `verify` olarak
verilir. **`verify=False` hiçbir koşulda kullanılmaz.**

## 2. Okuma Yolu (ADO → Arayüz)

```
┌── worker döngüsü (varsayılan 60 sn) ────────────────────────┐
│                                                              │
│  git fetch origin main                                       │
│       │                                                      │
│  origin/main SHA'sı aktif snapshot'tan farklı mı?            │
│       ├─ Hayır → bekle                                       │
│       └─ Evet ↓                                              │
│  git diff --name-status <eski> <yeni>                        │
│       │                                                      │
│  Değişen dosyaları sınıflandır (playbook/rol/envanter/...)   │
│       │                                                      │
│  SADECE değişenleri parse et  ← artımlı                      │
│  Etkilenen rol şemalarını tazele                             │
│       │                                                      │
│  Yeni repo_snapshot oluştur, is_active=true yap              │
│  Eski snapshot'ları temizle (son 3 hariç)                    │
│       │                                                      │
│  WebSocket: {"type": "repo_updated", "commit": "<sha>"}      │
└──────────────────────────────────────────────────────────────┘
```

### Webhook (tercih edilen)

ADO service hook yapılandırılabiliyorsa gecikme saniyelere iner:

```
POST /api/webhooks/ado
X-AnsibleUI-Signature: sha256=<hmac>
```

- İmza, paylaşılan bir sır ile HMAC-SHA256 olarak **sabit zamanlı** karşılaştırılır.
- İmza geçersizse `401` döner ve denetim kaydı yazılır.
- Webhook yalnızca "hemen fetch et" sinyalidir; gövdedeki veriye güvenilmez.

Yoklama (polling) her hâlükârda yedek olarak çalışmaya devam eder.

## 3. Yazma Yolu (Arayüz → ADO)

### 3.1 Aşamalar

```
1. TASLAK       Kullanıcı düzenler → DB'ye yazılır (base_commit_sha ile)
                Hiçbir şey push edilmez. Taslak günlerce durabilir.

2. ÖNİZLEME     POST /api/publish/preview
                → Her dosya için: mevcut içerik, üretilecek içerik, unified diff
                → Doğrulayıcı sonuçları (BLOCKER varsa yayınlama engellenir)
                → pbList güncellemesi gerekiyorsa o da diff'te gösterilir

3. YAYINLAMA    POST /api/publish  (worker işi olarak kuyruğa alınır)
                a. base_commit_sha güncel mi? → değilse çakışma
                b. Branch adı üret ve doğrula
                c. git checkout -b <branch> origin/main
                d. Dosyaları yaz (ruamel round-trip)
                e. Gerekiyorsa pbList güncelle
                f. Commit (trailer'larla)
                g. git push origin <branch>
                h. ADO REST ile PR aç
                i. PR URL'ini kaydet, denetim kaydı yaz

4. ONAY         İnsan, Azure DevOps'ta inceler ve merge eder.
                Platform merge YAPMAZ.
```

### 3.2 Branch Adlandırma

```
ansibleui/<kullanici>/<wp-veya-slug>
örnek: ansibleui/trahim/isube-yeni-klasor
```

Kurallar (kodla zorlanır):
- Önek `ansibleui/` sabittir ve değiştirilemez.
- Yalnızca `[a-z0-9._/-]` karakterleri; diğerleri normalize edilir.
- `main`, `master`, `HEAD` adları reddedilir.
- Çakışma varsa sonuna `-2`, `-3` eklenir.

```python
FORBIDDEN_BRANCHES = {"main", "master", "HEAD"}

def build_branch_name(username: str, slug: str, prefix: str) -> str:
    """Guvenli bir branch adi uretir; main'e yazmayi yapisal olarak imkansiz kilar."""
    name = f"{prefix}/{slugify(username)}/{slugify(slug)}"
    if name in FORBIDDEN_BRANCHES or not name.startswith(f"{prefix}/"):
        raise UnsafeBranchError(name)
    return name
```

`gitops` katmanındaki push fonksiyonu ayrıca **çalışma zamanında** kontrol eder:

```python
def push(self, branch: str) -> None:
    if branch in FORBIDDEN_BRANCHES:
        raise UnsafeBranchError(branch)   # test ile kanitlanir
    ...
```

### 3.3 Commit Mesajı

```
feat(isube): D:\WebSites\...\api\Profile klasoru eklendi

AnsibleUI ile olusturuldu.

Degisen dosyalar:
- roles_custom/install_isube/tasks/install_isube_nonprod_freshserver.yml

AnsibleUI-User: trahim
AnsibleUI-Draft-Id: 41f2c8e0-...
AnsibleUI-Base-Commit: 16522d0
```

Commit'i atan git kimliği bir **servis hesabıdır**; gerçek kullanıcı trailer'da ve
denetim kaydında tutulur. Bu, PAT'in tek bir hesaba ait olmasının doğal sonucudur.

### 3.4 Pull Request

```http
POST {repoApiRoot}/git/repositories/{repositoryId}/pullrequests?api-version=6.0
```

```json
{
  "sourceRefName": "refs/heads/ansibleui/trahim/isube-yeni-klasor",
  "targetRefName": "refs/heads/main",
  "title": "AnsibleUI: isube fresh server — yeni klasör",
  "description": "...otomatik üretilen özet...",
  "reviewers": []
}
```

PR açıklaması otomatik üretilir ve şunları içerir:
- Değişen dosyalar ve değişiklik özeti (insan diliyle)
- Etkilenen rol ve parametreler
- **Etkilenen host grupları** (envanter analizinden) — inceleyene en çok bunu söyler
- Doğrulayıcı sonuçları
- Taslağı oluşturan kullanıcı ve zaman

### 3.5 Çakışma Yönetimi

Yayınlama anında `base_commit_sha` ile `origin/main` karşılaştırılır:

| Durum | Davranış |
|---|---|
| SHA aynı | Sorunsuz devam |
| SHA farklı, taslağın dokunduğu dosyalar değişmemiş | Sessizce yeni tabana geçilir, devam |
| SHA farklı, **aynı dosyalar** değişmiş | Çakışma ekranı açılır |

Çakışma ekranında üç seçenek sunulur:
1. **Yeniden temelle** — güncel içerik üzerine değişiklik tekrar uygulanır, diff yeniden gösterilir.
2. **Yine de branch aç** — merge çatışması Azure DevOps'ta çözülür.
3. **İptal et** — taslak korunur, hiçbir şey push edilmez.

## 4. `pbList` Problemi ve Çözümü

### Problem

Çalıştırma pipeline'ı, playbook yolunu elle yazılmış bir açılır listeden alır:

```yaml
parameters:
- name: pbList
  displayName: Yml Path Name
  type: string
  default: ""
  values:
  - altortam_arch/add_user_to_administration.yml
  - ...                                    # ~120 satır
```

Bu listede olmayan bir playbook **çalıştırılamaz**. Yani yeni playbook oluşturan
her değişiklik, pipeline dosyasına da dokunmak zorundadır.

### Çözüm (MVP)

Playbook oluşturan veya yeniden adlandıran her yayınlama, **aynı PR içinde** ilgili
ortamın pipeline dosyasını da günceller:

```
azure-pipelines/nonprod/azure-pipelines-playbook.yml
azure-pipelines/prod/azure-pipelines-playbook.yml
azure-pipelines/dmz_nonprod/azure-pipelines-playbook.yml
azure-pipelines/dmz_prod/azure-pipelines-playbook.yml
```

Kurallar:
- Yeni yol, `values` listesine **alfabetik sırada** eklenir.
- Ekleme `ruamel` round-trip ile yapılır; dosyanın geri kalanı byte düzeyinde korunur.
- Hangi ortam dosyasının güncelleneceği, playbook'un `hosts:` değerinin hangi envanter
  ortamına ait olduğundan çıkarılır.
- Bu değişiklik yayınlama diff'inde **ayrı bir dosya olarak** gösterilir; kullanıcı görür.
- Playbook silinirse ilgili satır listeden çıkarılır.

Doğrulayıcı `V009`, `pbList` listesinde olmayan bir playbook'u çalıştırma denemesini
önceden yakalar.

### Uzun Vadeli Alternatif (Faz 8)

`pbList` tipini serbest `string`'e çevirip allowlist'i platform tarafında tutmak
mümkündür. Bu, pipeline dosyalarına hiç dokunmamayı sağlar fakat pipeline'ın
değiştirilmesini gerektirir. MVP'de kapsam dışı; WP-81 altında değerlendirilecek.

## 5. Güvenlik Kuralları

| Kural | Uygulama |
|---|---|
| `main`'e push yasak | Branch adı doğrulaması + push fonksiyonunda çalışma zamanı kontrolü + test |
| Komut enjeksiyonu yok | Tüm git işlemleri GitPython API'si; shell string'i kurulmaz |
| Path traversal yok | Yazılacak yollar `app/core/paths.py` doğrulayıcısından geçer; `..` reddedilir |
| Yazma allowlist'i | Yalnızca `playbooks/`, `roles/`, `roles_custom/`, `inventory/`, `group_vars/`, `templates/`, `azure-pipelines/` altına yazılabilir |
| SSRF yok | ADO base URL yalnızca ayarlardan; kullanıcı girdisinden URL kurulmaz |
| PAT sızıntısı yok | Secret olarak tutulur, log'da maskelenir, API yanıtında asla dönmez |
| Merge yetkisi yok | Platform PR açar, **merge etmez**; PAT'e merge yetkisi verilmez |

## 6. Hata Yönetimi

| Hata | Davranış |
|---|---|
| Ağ hatası / zaman aşımı | 3 denemeye kadar üstel geri çekilme (exponential backoff); sonra taslak `failed` işaretlenir, kullanıcı tekrar deneyebilir |
| PAT geçersiz/süresi dolmuş | Tüm yazma işlemleri durur, yöneticiye görünür uyarı, denetim kaydı |
| Push reddedildi (branch koruma) | Kullanıcıya anlaşılır mesaj; taslak korunur |
| PR zaten açık (aynı branch) | Mevcut PR'a yönlendirilir, yenisi açılmaz |
| Sertifika doğrulama hatası | İşlem durur; **TLS asla atlanmaz**; CA bundle yapılandırması kontrol edilmeli |
| `git fetch` başarısız | Son başarılı snapshot kullanılmaya devam eder, arayüzde "senkronizasyon gecikti" göstergesi |

## 7. Kullanılan ADO API Uçları

| Amaç | Uç nokta |
|---|---|
| Sürüm tespiti | `GET /_apis/?api-version=6.0` |
| Depo bilgisi | `GET /git/repositories/{repo}` |
| PR oluşturma | `POST /git/repositories/{repoId}/pullrequests` |
| PR durumu | `GET /git/repositories/{repoId}/pullrequests/{prId}` |
| Build tetikleme | `POST /build/builds` |
| Build durumu | `GET /build/builds/{buildId}` |
| Build zaman çizelgesi | `GET /build/builds/{buildId}/timeline` |
| Build log'u | `GET /build/builds/{buildId}/logs/{logId}` |

Tümü `httpx.AsyncClient` üzerinden, ortak timeout ve retry politikasıyla çağrılır.
İstemci sözleşmeleri sahte bir ADO sunucusuna karşı test edilir; **testlerde gerçek ağ
çağrısı yapılmaz**.
