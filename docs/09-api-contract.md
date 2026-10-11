# 09 — API Sözleşmesi

Taban yol: `/api` · Kimlik: `httpOnly` çerezdeki JWT · Biçim: JSON (UTF-8)
Canlı şema: `GET /docs` (Swagger) ve `GET /openapi.json`

## 1. Genel Kurallar

| Konu | Kural |
|---|---|
| Adlandırma | Yollar çoğul ve kebab-case: `/api/role-schemas` |
| Alan adları | `snake_case` (Pydantic varsayılanı) |
| Zaman | ISO 8601, UTC, `Z` sonekli |
| Sayfalama | `?page=1&page_size=50`; yanıtta `total`, `page`, `page_size` |
| Sıralama | `?sort=name&order=asc` |
| Kısmi güncelleme | `PATCH`; tam değiştirme `PUT` |
| İdempotans | Yayınlama ve çalıştırma isteklerinde `Idempotency-Key` başlığı desteklenir |

## 2. Hata Biçimi

Tüm hatalar aynı zarfı kullanır:

```json
{
  "error": {
    "code": "VALIDATION_BLOCKER",
    "message": "Yayinlama engellendi: 1 bloklayici dogrulama hatasi var.",
    "details": [
      {
        "rule": "V001",
        "severity": "blocker",
        "file": "roles_custom/install_isube/tasks/install_isube_nonprod.yml",
        "node_id": "...#/1",
        "message": "appNames icindeki 'api\\Profile' icin create_dir listesinde klasor yok."
      }
    ],
    "request_id": "01JBQ7K3M9X2"
  }
}
```

`message` alanı **Türkçe ve kullanıcıya gösterilebilir** olmalıdır. `code` makine
tarafından işlenir. `request_id` log ile eşleştirme içindir.

### Hata Kodları

| HTTP | `code` | Anlam |
|---|---|---|
| 400 | `INVALID_REQUEST` | Gövde veya parametre hatalı |
| 401 | `UNAUTHENTICATED` | Oturum yok veya süresi dolmuş |
| 403 | `FORBIDDEN` | Yetki yetersiz |
| 403 | `APPROVAL_REQUIRED` | Bu ortam için onay gerekli |
| 404 | `NOT_FOUND` | Kaynak yok |
| 409 | `CONFLICT_BASE_CHANGED` | Taslağın temeli güncellenmiş |
| 409 | `PR_ALREADY_OPEN` | Bu branch için PR zaten açık |
| 422 | `VALIDATION_BLOCKER` | Doğrulayıcı bloklayıcı hata buldu |
| 429 | `RATE_LIMITED` | Hız sınırı aşıldı |
| 502 | `ADO_UNAVAILABLE` | Azure DevOps'a ulaşılamıyor |
| 503 | `INDEX_NOT_READY` | İlk indeksleme henüz tamamlanmadı |

## 3. Kimlik Doğrulama

| Yöntem | Yol | Açıklama |
|---|---|---|
| `POST` | `/api/auth/login` | `{username, password}` → çerez kurar, `{user, roles}` döner |
| `POST` | `/api/auth/logout` | Çerezi temizler, token'ı geçersiz kılar |
| `POST` | `/api/auth/refresh` | Token'ı yeniler |
| `GET` | `/api/auth/me` | Aktif kullanıcı ve ortam bazlı yetkileri |

```json
// GET /api/auth/me
{
  "id": "u_01H...",
  "username": "trahim",
  "display_name": "T. Rahim",
  "provider": "local",
  "permissions": {
    "nonprod":     ["view", "edit", "publish", "run"],
    "dmz_nonprod": ["view", "edit", "publish", "run"],
    "prod":        ["view"],
    "dmz_prod":    ["view"]
  }
}
```

## 4. Katalog

| Yöntem | Yol | Açıklama |
|---|---|---|
| `GET` | `/api/roles` | Rol listesi. `?source=roles\|roles_custom&q=<arama>` |
| `GET` | `/api/roles/{name}` | Rol detayı, tüm varyantların şemaları, kullanım örnekleri |
| `GET` | `/api/roles/{name}/usages` | Bu rolü kullanan playbook ve görev dosyaları |
| `GET` | `/api/playbooks` | Playbook listesi. `?environment=&q=` |
| `GET` | `/api/playbooks/{path}` | Playbook detayı (play'ler, hedef gruplar, pbList durumu) |
| `GET` | `/api/search` | Birleşik arama: rol + playbook + envanter + vault adı |
| `GET` | `/api/vault-vars` | Vault değişken **adları** ve nerede kullanıldıkları |

```json
// GET /api/roles/createWebSiteApp
{
  "name": "createWebSiteApp",
  "source": "roles",
  "path": "roles/createWebSiteApp",
  "dispatcher_param": "state",
  "variants": [
    {
      "variant": "recursive",
      "confidence": "high",
      "usage_count": 14,
      "params": [
        {
          "name": "appNames",
          "type": "list_obj",
          "required": true,
          "item_schema": {"name": "str", "pool": "str"},
          "examples": [[{"name": "api", "pool": "OBA.Web.InternetBanking"}]],
          "usage_count": 14,
          "description": "Olusturulacak uygulamalar ve kullanacaklari havuzlar."
        }
      ],
      "produces": [],
      "consumes": [],
      "warnings": []
    }
  ]
}
```

## 5. Envanter

| Yöntem | Yol | Açıklama |
|---|---|---|
| `GET` | `/api/inventory/groups` | Grup ağacı (children ilişkileriyle) |
| `GET` | `/api/inventory/groups/{name}` | Grup detayı: host'lar, değişkenler, hedefleyen playbook'lar |
| `GET` | `/api/inventory/hosts` | Host listesi. `?group=&q=` |
| `GET` | `/api/inventory/hosts/{name}` | Host detayı: üyesi olduğu gruplar, etkin değişkenler |
| `GET` | `/api/inventory/resolve` | `?hosts=<ifade>` → gerçek host listesi (çalıştırma öncesi özet için) |

## 6. Belgeler ve Düzenleme

| Yöntem | Yol | Açıklama |
|---|---|---|
| `GET` | `/api/documents/{path}` | Dosyanın IR temsili + ham metin + doğrulayıcı sonuçları |
| `GET` | `/api/documents/{path}/graph` | Node'lar ve kenarlar (sıra, örtük veri, dosya) |
| `GET` | `/api/documents/{path}/raw` | Ham YAML metni |
| `POST` | `/api/validate` | Bir taslak içeriği için doğrulayıcıları çalıştırır (kaydetmeden) |

```json
// GET /api/documents/playbooks%2Ftsube%2Finstall_tsube.yml
{
  "path": "playbooks/tsube/install_tsube.yml",
  "commit_sha": "16522d0",
  "plays": [
    {
      "node_id": "playbooks/tsube/install_tsube.yml#/0",
      "type": "play",
      "name": "install tsube prod",
      "hosts": "tsube_prod",
      "resolved_hosts": ["spltsube1", "spltsube2"],
      "vars_files": ["/etc/ansible/vault/vault.yml"],
      "children": [
        {
          "node_id": "playbooks/tsube/install_tsube.yml#/0/roles/0",
          "type": "role",
          "role_name": "install_tsube",
          "variant": null,
          "params": {"prod": true},
          "capabilities": {"editable": true, "reorderable": true, "deletable": true},
          "warnings": []
        }
      ]
    }
  ],
  "validations": [],
  "unsupported_node_count": 0
}
```

## 7. Taslaklar

| Yöntem | Yol | Açıklama |
|---|---|---|
| `GET` | `/api/drafts` | Kullanıcının taslakları (admin: tümü) |
| `POST` | `/api/drafts` | Yeni taslak: `{title, base_commit_sha}` |
| `GET` | `/api/drafts/{id}` | Taslak detayı, dokunulan dosyalar |
| `PATCH` | `/api/drafts/{id}` | Başlık güncelleme |
| `PUT` | `/api/drafts/{id}/files/{path}` | Dosya içeriğini taslağa yaz |
| `POST` | `/api/drafts/{id}/nodes/{node_id}` | Node parametresi güncelle (hedefli yama) |
| `DELETE` | `/api/drafts/{id}` | Taslağı iptal et |
| `GET` | `/api/drafts/{id}/revisions` | Revizyon geçmişi |

### Node Yaması

```json
// POST /api/drafts/{id}/nodes/{node_id}
{
  "operation": "set_params",
  "params": {
    "physical_path": "D:\\WebSites\\OBA.Web.InternetBanking\\"
  }
}
```

Desteklenen işlemler: `set_params`, `set_raw`, `move` (`{before_node_id}`),
`delete`, `duplicate`, `insert_role` (`{role_name, variant, params, position}`).

`move` işlemi, örtük bağımlılığı bozacaksa `422 VALIDATION_BLOCKER` döner ve
`details` içinde hangi değişkenin hangi node'dan geleceği açıklanır.

## 8. Yayınlama

| Yöntem | Yol | Açıklama |
|---|---|---|
| `POST` | `/api/publish/preview` | `{draft_id}` → diff + doğrulama sonuçları, **yazma yok** |
| `POST` | `/api/publish` | `{draft_id, title, description, reviewers?}` → branch + commit + push + PR |
| `GET` | `/api/publish/{id}` | Yayınlama isteği durumu ve PR bilgisi |
| `POST` | `/api/publish/{id}/rebase` | Çakışma durumunda güncel tabana taşı |

```json
// POST /api/publish/preview  → 200
{
  "base_commit_sha": "16522d0",
  "is_base_current": true,
  "files": [
    {
      "path": "roles_custom/install_isube/tasks/install_isube_nonprod_freshserver.yml",
      "change_type": "modified",
      "diff": "@@ -42,6 +42,7 @@\n       - D:\\WebSites\\...\n+      - D:\\WebSites\\...\\api\\Profile\n"
    },
    {
      "path": "azure-pipelines/nonprod/azure-pipelines-playbook.yml",
      "change_type": "modified",
      "diff": "...",
      "reason": "Yeni playbook pbList listesine eklendi."
    }
  ],
  "validations": [
    {"rule": "V002", "severity": "warning", "message": "..."}
  ],
  "can_publish": true
}
```

`can_publish` yalnızca **bloklayıcı** doğrulama yoksa `true` olur.

## 9. Çalıştırma

| Yöntem | Yol | Açıklama |
|---|---|---|
| `POST` | `/api/runs/preflight` | `{playbook_path, environment}` → ön kontroller + hedef özeti |
| `POST` | `/api/runs` | Çalıştırmayı başlat |
| `GET` | `/api/runs` | Geçmiş. `?environment=&status=&playbook=&user=&from=&to=` |
| `GET` | `/api/runs/{id}` | Çalıştırma detayı ve task×host matrisi |
| `POST` | `/api/runs/{id}/cancel` | ADO build'ini iptal et |
| `GET` | `/api/runs/{id}/log` | Ayrıştırılmış log satırları (sayfalı, maskelenmiş) |
| `WS` | `/ws/runs/{id}` | Canlı güncellemeler |

```json
// POST /api/runs/preflight  → 200
{
  "can_run": true,
  "requires_approval": false,
  "playbook_path": "altortam/install_isube/install_isube_test.yml",
  "environment": "nonprod",
  "agent_pool": "AnsibleTestEnv",
  "commit_sha": "16522d0",
  "target_group": "test_isube",
  "target_hosts": ["stlisube1", "stlisube2"],
  "step_count": 17,
  "roles": ["create_dir", "copyFile_Multiple", "installUninstallPackage"],
  "blockers": [],
  "warnings": []
}
```

```json
// POST /api/runs
{
  "playbook_path": "altortam/install_isube/install_isube_test.yml",
  "environment": "nonprod",
  "approval_token": null
}
```

Prod ortamlarında `approval_token`, Approver rolündeki **farklı** bir kullanıcının
`POST /api/approvals` ile ürettiği tek kullanımlık bir değerdir.

## 10. Onaylar

| Yöntem | Yol | Açıklama |
|---|---|---|
| `POST` | `/api/approvals` | Approver bir çalıştırma talebini onaylar → token döner |
| `GET` | `/api/approvals/pending` | Onay bekleyen talepler |

## 11. Yönetim

| Yöntem | Yol | Yetki |
|---|---|---|
| `GET/POST` | `/api/admin/users` | Admin |
| `PATCH/DELETE` | `/api/admin/users/{id}` | Admin |
| `GET/POST/DELETE` | `/api/admin/role-bindings` | Admin |
| `GET/PUT` | `/api/admin/role-schemas/{role}/{variant}` | Admin — şema geçersiz kılma |
| `POST` | `/api/admin/reindex` | Admin — tam yeniden indeksleme |
| `GET` | `/api/admin/audit` | Admin — denetim kayıtları, filtreli |
| `GET/PUT` | `/api/admin/settings` | Admin |

## 12. Sistem

| Yöntem | Yol | Kimlik | Açıklama |
|---|---|---|---|
| `GET` | `/healthz` | Gerekmez | Liveness |
| `GET` | `/readyz` | Gerekmez | Readiness (DB + PVC) |
| `GET` | `/metrics` | Gerekmez (ağ ile kısıtlı) | Prometheus |
| `GET` | `/api/status` | Gerekir | İndeks durumu, son commit, senkronizasyon gecikmesi |
| `POST` | `/api/webhooks/ado` | HMAC imzası | ADO service hook |

## 13. Hız Sınırları

| Uç nokta grubu | Sınır |
|---|---|
| `/api/auth/login` | 5 / dakika / IP, 10 / saat / kullanıcı |
| `/api/publish` | 10 / dakika / kullanıcı |
| `/api/runs` | 20 / saat / kullanıcı |
| Diğer | 300 / dakika / kullanıcı |

Aşımda `429 RATE_LIMITED` ve `Retry-After` başlığı döner.

## 14. Sürümleme

MVP'de sürümsüz (`/api/...`). Kırıcı değişiklik gerekirse `/api/v2/` eklenir ve
`/api/v1/` en az bir sürüm boyunca korunur. OpenAPI şeması her sürümde üretilir ve
frontend tipleri bundan türetilir.
