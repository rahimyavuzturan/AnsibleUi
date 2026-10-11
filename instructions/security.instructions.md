---
description: "Tum dosyalarda gecerli, ihlal edilemez guvenlik kurallari. Secret yonetimi, TLS, path traversal, injection, git guvenligi ve vault erisim yasagi."
applyTo: "**"
---

# Güvenlik Kuralları

> Bu dosya bilinçli olarak `applyTo: "**"` kullanır. İçeriği kısadır ve her dosya için
> geçerlidir. Ayrıntılı tehdit modeli: [docs/08-security-and-rbac.md](../../docs/08-security-and-rbac.md)

## Asla Yapılmayacaklar

Bu maddelerden biri bir görevi tamamlamak için gerekiyorsa, **görevi yapma** ve durumu bildir.

1. **TLS doğrulaması kapatma.** `verify=False`, `ssl._create_unverified_context`,
   `NODE_TLS_REJECT_UNAUTHORIZED=0`, `rejectUnauthorized: false` — hiçbiri.
   İç sertifikalar için CA bundle kullanılır (`ANSIBLEUI_CA_BUNDLE_PATH`).

2. **Vault değeri okuma.** `/etc/ansible/vault/**` yolunu açan kod yazma.
   Yalnızca playbook'lardaki `{{ }}` referanslarından **değişken adı** türetilir.

3. **`main` branch'ine yazma.** Sadece `ansibleui/*` branch'leri. Koruma kodunu
   kaldırma veya atlama.

4. **Secret'ı log'a / DB'ye / API yanıtına yazma.** Parola, token, PAT, sertifika
   parolası hiçbir katmanda açıkta görünmez.

5. **Kodda sabit kimlik bilgisi.** URL, kullanıcı adı, parola, token — hepsi ayarlardan.

6. **Sessiz hata yutma.** `except: pass`, `except Exception: pass`, boş `catch {}`.

## Girdi Doğrulama

```python
# Depo ici dosya yollari MUTLAKA dogrulayicidan gecer
from app.core.paths import validate_repo_path

path = validate_repo_path(user_input)   # ".." reddedilir, allowlist zorunlu
```

İzinli kökler: `playbooks/`, `roles/`, `roles_custom/`, `inventory/`, `group_vars/`,
`templates/`, `azure-pipelines/`.

## Enjeksiyon Önleme

| Tür | Kural |
|---|---|
| SQL | Yalnızca SQLAlchemy parametreli sorgular; string birleştirme yok |
| Komut | Git işlemleri **GitPython API'si**; `subprocess` + shell yok |
| YAML | `ruamel.yaml(typ="rt")`; `yaml.load` ile keyfi nesne yok |
| Jinja | Kullanıcı şablonu **render edilmez**, yalnızca `parse()` ile AST'e çevrilir |
| XSS | React varsayılan kaçırma; `dangerouslySetInnerHTML` yasak |
| Log | Kullanıcı verisindeki satır sonu karakterleri kaçırılır |

## SSRF Önleme

```python
# DOGRU - base URL yalnizca ayarlardan
url = f"{settings.ado_repo_api_root}/git/repositories/{repo_id}/pullrequests"

# YANLIS - kullanici girdisinden URL
url = request.target_url
```

Giden istemcilerde `follow_redirects=False`.

## Yetkilendirme

Yetki kontrolü **servis katmanında** yapılır, router'da değil:

```python
async def trigger_run(self, user: User, playbook: str, env: Environment) -> Run:
    self._authz.require(user, Action.RUN, env)   # once yetki
    ...
```

Varsayılan **ret**: açıkça izin verilmemiş her şey yasaktır.

## Kontrol Listesi

Bir değişikliği tamamlamadan önce:

- [ ] Yeni bir dış çağrı eklendiyse: TLS doğrulaması açık, base URL ayarlardan mı?
- [ ] Yeni bir dosya işlemi eklendiyse: yol doğrulayıcıdan geçiyor mu?
- [ ] Yeni bir log satırı eklendiyse: secret içerebilir mi?
- [ ] Yeni bir endpoint eklendiyse: yetki kontrolü servis katmanında mı?
- [ ] Yeni bir hata yolu eklendiyse: sessizce yutuluyor mu?
