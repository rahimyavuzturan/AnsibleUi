---
description: "Use when writing or reviewing Python backend code: FastAPI services, Pydantic models, async patterns, layering rules, error handling, logging and typing standards."
applyTo: "backend/**/*.py"
---

# Backend Python Kuralları

## Katman Sınırları

```
api  →  services  →  {ansible, gitops, ado, db, auth}  →  core
```

Ok yönünün tersine import **yasaktır**. Örneğin `app/db/` içinden `app/services/`
import edilemez.

| Katman | Sorumluluk | İçermez |
|---|---|---|
| `api/` | HTTP, doğrulama, serileştirme | İş mantığı |
| `services/` | İş akışı, yetki kontrolü, orkestrasyon | HTTP detayı, SQL |
| `ansible/` | YAML/IR — **saf** | Ağ, DB, dosya yazma |
| `gitops/` | Yerel depo işlemleri (GitPython) | HTTP API çağrısı |
| `ado/` | Azure DevOps REST istemcisi | Git nesnesi işleme |
| `db/` | SQLAlchemy modelleri ve repository'ler | İş kuralı |
| `core/` | Ayarlar, hatalar, log, yol doğrulama | Domain bilgisi |

> Paket adı `gitops/` — `git/` **değil** (GitPython ile ad çakışması).

## Tip ve Stil

- Tüm public fonksiyonlarda tam tip imzası. `Any` yalnızca gerekçeli ve yorumlu.
- `mypy --strict` temiz olmalı; `# type: ignore` gerekçe yorumu ister.
- `ruff format` ve `ruff check` temiz.
- Modül/fonksiyon/değişken adları İngilizce; kullanıcıya dönen metinler Türkçe.

## Async Kuralları

```python
# DOGRU - async fonksiyonda bloklayan is thread'e tasinir
result = await anyio.to_thread.run_sync(repo.git.fetch)

# YANLIS - event loop'u bloklar
result = repo.git.fetch()
```

Git ve dosya sistemi işlemleri bloklayıcıdır; `async def` içinde doğrudan çağrılmaz.

## Pydantic v2

- API şemaları `app/api/schemas/` altında; DB modelleriyle **aynı sınıf değildir**.
- `model_config = ConfigDict(extra="forbid")` — bilinmeyen alan sessizce yutulmaz.
- Doğrulama Pydantic'e bırakılır; elle `if not x: raise` tekrarı yazılmaz.

## Hata Yönetimi

```python
# DOGRU
from app.core.errors import ConflictError

if draft.base_commit != current_head:
    raise ConflictError(
        code="DRAFT_STALE",
        message="Taslak, deponun güncel hâliyle çakışıyor.",
        details={"draft_base": draft.base_commit, "head": current_head},
    )

# YANLIS
except Exception:
    pass
```

- Uygulama hataları `app/core/errors.py` içindeki tiplerden türer.
- Global exception handler tek tip zarfa çevirir (bkz.
  [docs/09-api-contract.md](../../docs/09-api-contract.md)).
- `except Exception` yakalanırsa mutlaka loglanır **ve** yeniden fırlatılır ya da
  anlamlı bir domain hatasına çevrilir.

## Loglama

```python
import structlog
log = structlog.get_logger(__name__)

log.info("draft.published", draft_id=draft.id, pr_id=pr.id, file_count=len(files))
```

- Yapılandırılmış log; f-string ile mesaj birleştirme yok.
- `request_id` context'ten otomatik eklenir.
- Hassas anahtarlar `app/core/logging.py` maskeleyicisinden geçer.

## Bağımlılık Ekleme

Yeni paket `pyproject.toml` içine eklenir, gerekçesi PR açıklamasında belirtilir.
Mimari etkisi varsa önce ADR. Reddedilen teknolojiler:
[docs/02-tech-stack.md](../../docs/02-tech-stack.md).

## Bitti Tanımı

- [ ] `ruff check . && ruff format --check .`
- [ ] `mypy --strict app`
- [ ] `pytest` yeşil, yeni kod için test var
- [ ] Katman ihlali yok
- [ ] Yeni ayar eklendiyse `.env.example` ve [docs/11](../../docs/11-deployment-rancher.md) güncel
