# 03 — Alan Modeli

## 1. Kavramlar

Terim tanımları için ayrıca [15-glossary.md](15-glossary.md).

```
Repo (tek, sabit)
 └── RepoSnapshot        belirli bir commit'teki depo durumu
      ├── Role           roles/ veya roles_custom/ altındaki bir rol
      │    └── RoleSchema  rolün çıkarılmış parametre şeması (varyant başına)
      ├── Playbook       playbooks/ altındaki bir dosya
      │    └── Play      playbook içindeki bir oynatma (hosts + roles/tasks)
      │         └── Node  IR düğümü (rol, include, modül veya ham blok)
      ├── InventoryGroup INI envanterindeki bir grup
      │    └── Host
      └── VaultVarName   yalnızca AD — değer asla saklanmaz
```

```
Kullanıcı etkileşimi
 User ──► Draft ──► PublishRequest ──► (Azure DevOps PR)
   │                      │
   └────► Run ────────────┘   (çalıştırma her zaman main üzerinden)
            └── RunTaskResult   task × host durum matrisi
```

## 2. Temel Nesneler

### RepoSnapshot
Belirli bir commit SHA'sında depo durumunun indekslenmiş hâli. İndeks **türetilmiş**
veridir: her an silinip yeniden üretilebilir. Aynı anda yalnızca bir "aktif" snapshot olur.

### Role / RoleSchema
Bir rol, `state` gibi bir dağıtıcı (dispatcher) parametre içeriyorsa **varyant** başına
ayrı şema üretir:

| Rol | Varyant | Parametre şeması |
|---|---|---|
| `createWebSiteApp` | `@started` | `appNames: list[str]`, path birleştirme var |
| `createWebSiteApp` | `@recursive` | `appNames: list[{name, pool}]`, path birleştirme yok |
| `createWebSiteApp` | `@absent` | yalnızca `websiteName` |

Her şemanın bir **güven skoru** vardır (`high` / `medium` / `low`). Düşük güvenli şemalar
arayüzde "doğrulanmamış" rozetiyle gösterilir ve yönetici elle düzeltebilir
(`RoleSchemaOverride`). Ayrıntı: [05-role-schema-inference.md](05-role-schema-inference.md)

### Node
IR düğümü. Kimliği **deterministiktir**: dosya yolu + YAML içindeki konum.

```
playbooks/tsube/install_tsube.yml#/0/roles/1
roles_custom/install_isube/tasks/install_isube_nonprod.yml#/3
```

Aynı dosya iki kez parse edildiğinde aynı node kimlikleri üretilir. Bu, taslakların
ve canvas düzeninin commit'ler arasında korunmasını sağlar.
Ayrıntı: [04-ansible-ir-spec.md](04-ansible-ir-spec.md)

### Draft
Henüz yayınlanmamış değişiklik. `base_commit_sha` taşır; yayınlama anında bu SHA ile
`origin/main` karşılaştırılarak çakışma tespit edilir. Bir taslak birden fazla dosyaya
dokunabilir (ör. playbook + `pbList` güncellemesi).

### Run
Bir çalıştırma. Platform Ansible'ı çalıştırmaz; Azure Pipeline build'ini tetikler ve
sonucu izler. Build log'unun **tamamı DB'ye yazılmaz** — yalnızca ayrıştırılmış task
durumları ve özet saklanır; ham log Azure DevOps'ta kalır.

## 3. Veritabanı Şeması

İki kategori: **türetilmiş** (silinip yeniden üretilebilir) ve **kalıcı** (kaybedilemez).

### 3.1 Türetilmiş — İndeks Tabloları

| Tablo | Alanlar (özet) |
|---|---|
| `repo_snapshot` | `id`, `commit_sha`, `indexed_at`, `is_active`, `file_count`, `duration_ms` |
| `file_index` | `id`, `snapshot_id`, `path`, `kind` (playbook/role_task/inventory/pipeline/template), `content_hash`, `parse_status`, `parse_error` |
| `role` | `id`, `snapshot_id`, `name`, `source` (roles/roles_custom), `path`, `task_file_count`, `description` |
| `role_schema` | `id`, `role_id`, `variant`, `params` (JSONB), `dispatcher_param`, `confidence`, `usage_count`, `warnings` (JSONB) |
| `role_schema_override` | `id`, `role_name`, `variant`, `params` (JSONB), `updated_by`, `updated_at`, `note` |
| `playbook` | `id`, `snapshot_id`, `path`, `name`, `environments` (JSONB), `in_pblist` (JSONB) |
| `play` | `id`, `playbook_id`, `index`, `name`, `hosts`, `vars_files` (JSONB) |
| `node_index` | `id`, `snapshot_id`, `file_path`, `node_id`, `node_type`, `role_name`, `variant`, `summary`, `warnings` (JSONB) |
| `inventory_group` | `id`, `snapshot_id`, `name`, `file_path`, `parent_names` (JSONB), `vars` (JSONB) |
| `inventory_host` | `id`, `snapshot_id`, `name`, `group_names` (JSONB), `vars` (JSONB) |
| `vault_var_name` | `id`, `snapshot_id`, `name`, `referenced_in` (JSONB) — **yalnızca ad, değer yok** |

`role_schema_override` **türetilmiş değildir** (kullanıcı emeği içerir) fakat indeksle
birlikte yaşar; snapshot'a değil, rol adı + varyanta bağlanır.

### 3.2 Kalıcı — Uygulama Tabloları

| Tablo | Alanlar (özet) |
|---|---|
| `user` | `id`, `username`, `display_name`, `email`, `password_hash` (argon2id), `provider` (local/ldap), `is_active`, `created_at`, `last_login_at` |
| `user_role_binding` | `id`, `user_id`, `role` (viewer/editor/approver/admin), `environment` (nonprod/prod/dmz_nonprod/dmz_prod/\*), `granted_by`, `granted_at` |
| `draft` | `id`, `owner_id`, `title`, `base_commit_sha`, `status` (open/published/discarded), `created_at`, `updated_at` |
| `draft_revision` | `id`, `draft_id`, `revision`, `file_path`, `content` (text), `created_at` |
| `publish_request` | `id`, `draft_id`, `requested_by`, `branch_name`, `commit_sha`, `pr_id`, `pr_url`, `status` (queued/pushed/pr_open/merged/failed), `error`, `created_at` |
| `run` | `id`, `playbook_path`, `environment`, `commit_sha`, `triggered_by`, `approved_by`, `ado_build_id`, `status` (queued/running/succeeded/failed/canceled), `started_at`, `finished_at`, `host_count`, `summary` (JSONB) |
| `run_task_result` | `id`, `run_id`, `task_index`, `task_name`, `role_name`, `host`, `status` (ok/changed/failed/skipped/unreachable), `duration_ms`, `message` |
| `audit_log` | `id`, `at`, `actor_id`, `action`, `target_type`, `target_id`, `environment`, `request_id`, `ip`, `detail` (JSONB) |
| `app_setting` | `key`, `value` (JSONB), `updated_by`, `updated_at` |

## 4. İlişki Diyagramı

```
user ──1:N──► user_role_binding
  │
  ├──1:N──► draft ──1:N──► draft_revision
  │            └──1:N──► publish_request
  ├──1:N──► run ──1:N──► run_task_result
  └──1:N──► audit_log

repo_snapshot ──1:N──► file_index
      ├──1:N──► role ──1:N──► role_schema
      ├──1:N──► playbook ──1:N──► play
      ├──1:N──► node_index
      ├──1:N──► inventory_group ─┐
      ├──1:N──► inventory_host ◄─┘ (çoka-çok, JSONB ile düzleştirilmiş)
      └──1:N──► vault_var_name

role_schema_override ──(role_name + variant ile eşleşir)──► role_schema
```

## 5. Boyut Bütçesi

Veritabanı küçük tutulmalıdır (kurumsal kısıt).

| Veri | Tahmin | Not |
|---|---|---|
| İndeks (tüm tablolar) | < 50 MB | ~900 dosya, ~3000 node |
| Taslaklar | < 50 MB | Dosya içeriği metin olarak; 90 gün sonra arşivlenir |
| Çalıştırma kayıtları | < 200 MB/yıl | **Ham log yok**, yalnızca ayrıştırılmış durumlar |
| Denetim kayıtları | < 100 MB/yıl | 2 yıl saklanır, sonra arşiv |
| **Toplam** | **< 1 GB** | |

Bunu sağlayan kurallar:
1. Build log'larının tamamı DB'ye **yazılmaz**; ADO'da kalır, `ado_build_id` ile erişilir.
2. Yalnızca **aktif** snapshot ile son 3 snapshot tutulur; eskiler silinir.
3. `draft_revision` taslak başına en fazla 50 revizyon tutar.
4. `run_task_result` çalıştırma başına üst sınırla kısıtlanır; aşımda özetlenir.

## 6. Veri Yaşam Döngüsü

| Veri | Oluşma | Silinme |
|---|---|---|
| `repo_snapshot` ve indeks | Her yeni commit'te | Son 3 snapshot dışındakiler otomatik |
| `draft` | Kullanıcı düzenlediğinde | Yayınlandıktan 30 gün sonra; `discarded` ise 7 gün |
| `run` | Çalıştırma tetiklendiğinde | 2 yıl sonra arşiv |
| `audit_log` | Her yazma işleminde | **Asla silinmez** (2 yıl sonra soğuk arşive taşınır) |
| `vault_var_name` | İndeksleme sırasında | Snapshot ile birlikte |

## 7. Değişmezler (Invariants)

Bunlar veritabanı kısıtları ve servis katmanı denetimleriyle güvence altına alınır:

1. Aynı anda en fazla **bir** `repo_snapshot.is_active = true`.
2. `vault_var_name` tablosunda **değer sütunu yoktur** — şema düzeyinde imkânsız.
3. `publish_request.branch_name` asla `main` olamaz (CHECK kısıtı).
4. `run.environment` prod veya dmz_prod ise `approved_by` **NOT NULL** olmalıdır.
5. `draft_revision` içeriği yalnızca allowlist'teki klasörlere ait dosya yolları taşıyabilir.
6. `user_role_binding` içinde aynı (user, role, environment) üçlüsü tekrar edemez.
7. `audit_log` kayıtları yalnızca eklenir (append-only); güncelleme/silme uygulama
   katmanında engellenir.

## 8. Göç (Migration) Politikası

- Tüm şema değişiklikleri Alembic ile; elle SQL çalıştırılmaz.
- Her göç geri alınabilir (`downgrade` yazılır).
- Türetilmiş tablolarda veri göçü yazılmaz — indeks yeniden üretilir.
- Kalıcı tablolarda sütun silme, kod dağıtımından **bir sürüm sonra** yapılır.
