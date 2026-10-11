---
description: "Use when working on git synchronization or Azure DevOps integration: clone, fetch, branch, commit, pull request creation, pipeline triggering, webhooks and PAT handling."
applyTo: "backend/app/gitops/**,backend/app/ado/**"
---

# Git ve Azure DevOps Kuralları

> Ayrıntı: [docs/06-git-sync-and-ado.md](../../docs/06-git-sync-and-ado.md) ·
> [docs/07-execution-and-logs.md](../../docs/07-execution-and-logs.md) ·
> [ADR-0003](../../docs/adr/ADR-0003-pipeline-trigger-not-own-runner.md) ·
> [ADR-0004](../../docs/adr/ADR-0004-pr-based-write-path.md)

## Paket Ayrımı

| `app/gitops/` | `app/ado/` |
|---|---|
| Yerel çalışma kopyası | Uzak REST API |
| GitPython | httpx |
| clone, fetch, checkout, commit, push | PR oluşturma, pipeline tetikleme, log çekme |

Birbirini import etmez. Koordinasyon `app/services/` katmanındadır.

## İhlal Edilemez Kurallar

### 1. `main` Asla Hedef Değil

```python
FORBIDDEN_BRANCHES = frozenset({"main", "master", "ertan"})

def assert_writable_branch(branch: str) -> None:
    if branch in FORBIDDEN_BRANCHES or not branch.startswith("ansibleui/"):
        raise ForbiddenBranchError(branch)
```

Bu kontrol push yolundaki **tek geçiş noktasında** bulunur ve atlanamaz.
Birleştirme yalnızca insan onaylı PR ile, Azure DevOps üzerinde olur.

### 2. Referans Depo Salt Okunur

`Ansible.appAdminConfig` çalışma kopyası uygulamanın veri kaynağıdır.
Elle dosya düzenleme yalnızca taslak yayınlama akışında, geçici branch üzerinde yapılır.
İşlem sonunda çalışma kopyası temiz bırakılır (`git checkout main && git reset --hard`).

### 3. Tek Yazar

Çalışma kopyasına yalnızca worker süreci yazar. PVC `ReadWriteOnce`'tur.
Eşzamanlı git işlemleri için süreç içi kilit kullanılır.

### 4. Git İşlemleri API ile, Shell ile Değil

```python
# DOGRU
repo.index.commit(message, author=actor)

# YANLIS - komut enjeksiyonu riski
subprocess.run(f"git commit -m '{message}'", shell=True)
```

### 5. PAT Yalnızca Ayarlardan, Asla Log'a

```python
# DOGRU
auth = httpx.BasicAuth("", settings.ado_pat.get_secret_value())

# YANLIS
log.info("ADO istegi", url=url, headers=dict(request.headers))   # Authorization sizar
```

PAT `SecretStr`'dir. Hata mesajlarında URL'ler maskelenmiş hâlde loglanır.

### 6. TLS Doğrulaması Açık

İç sertifika için `verify=settings.ca_bundle_path`. `verify=False` yasaktır.

### 7. Webhook Doğrulanır

Gelen webhook isteği paylaşılan sır ile imza doğrulamasından geçer; doğrulanmayan
istek 401 alır ve tetikleme yapmaz. Webhook yalnızca "senkronizasyonu öne al"
anlamına gelir; periyodik yoklama yedek mekanizma olarak korunur.

## Commit Biçimi

```
feat(playbooks): install_isube icin yeni gorev eklendi

AnsibleUI-User: trahim
AnsibleUI-Draft: 0f3a9c21-...
AnsibleUI-Version: 0.4.0
```

Trailer'lar denetim izi içindir; kaldırılmaz.

## Pipeline Tetikleme

- Kendi Ansible koşucumuz **yoktur**; yalnızca mevcut pipeline tetiklenir.
- `pbList` parametresi kısıtlıdır: yeni playbook ekleyen PR, aynı PR içinde
  pipeline YAML'ındaki `values` listesini alfabetik sırada günceller.
- Ön kontroller (playbook `pbList` içinde mi, envanter grubu var mı, branch
  birleşti mi, kullanıcının o ortamda yetkisi var mı) geçmeden tetikleme yapılmaz.

## Hata Yönetimi

| Durum | Davranış |
|---|---|
| Ağ erişilemez | Üstel geri çekilme ile 3 deneme, sonra durumu `degraded` işaretle |
| 401/403 | Yeniden deneme **yok**, yöneticiye bildirim |
| Push reddedildi | Yeniden temellendirme denenmez; kullanıcıya çakışma seçenekleri sunulur |
| PR zaten var | Yeni PR açma, mevcut PR'a commit ekle |

## Bitti Tanımı

- [ ] Sahte ADO sunucusuna karşı entegrasyon testi (`respx`/`httpx.MockTransport`)
- [ ] `main`'e yazma denemesinin reddedildiğini doğrulayan test
- [ ] PAT'in log'a düşmediğini doğrulayan test
- [ ] Ağ hatası senaryosu için test
- [ ] [docs/06](../../docs/06-git-sync-and-ado.md) güncel
