---
description: "Use when adding or changing REST endpoints, routers, request/response schemas, error envelopes, pagination or status codes in the FastAPI layer."
applyTo: "backend/app/api/**"
---

# API Sözleşmesi Kuralları

> Sözleşmenin tamamı: [docs/09-api-contract.md](../../docs/09-api-contract.md).
> Endpoint eklerken veya değiştirirken o dosya **aynı commit'te** güncellenir.

## Router Katmanının İşi

Router yalnızca: girdiyi doğrular → servisi çağırır → yanıtı şekillendirir.

```python
# DOGRU
@router.post("/drafts/{draft_id}/publish")
async def publish(
    draft_id: UUID,
    body: PublishRequest,
    user: CurrentUser,
    svc: PublishService = Depends(get_publish_service),
) -> PublishResponse:
    result = await svc.publish(user, draft_id, body.title, body.description)
    return PublishResponse.model_validate(result)

# YANLIS - is mantigi router'da
@router.post("/drafts/{draft_id}/publish")
async def publish(...):
    if user.role not in ("editor", "admin"):      # yetki servis katmaninda olmali
        raise HTTPException(403)
    repo = Repo(settings.repo_path)               # altyapi router'da olmaz
    repo.git.checkout("-b", branch)
```

## Zorunlu Kurallar

1. **Yetki kontrolü servis katmanında.** Router'da rol karşılaştırması yapma.
2. **`HTTPException` doğrudan fırlatılmaz.** Domain hataları fırlatılır; global
   handler HTTP'ye çevirir.
3. **Yol parametresi olarak depo yolu alınmaz.** Query veya body ile alınır ve
   `validate_repo_path` ile doğrulanır.
4. **Her yanıt bir Pydantic modeli.** `dict` döndürme.
5. **Liste uçları sayfalanır.** `limit` (varsayılan 50, en çok 200) ve `cursor`.
6. **Durum kodları:** 200 okuma, 201 oluşturma, 202 asenkron kabul, 204 silme,
   400 doğrulama, 401 kimlik, 403 yetki, 404 yok, 409 çakışma, 422 şema, 429 limit.

## Hata Zarfı

```json
{
  "error": {
    "code": "DRAFT_STALE",
    "message": "Taslak, deponun güncel hâliyle çakışıyor.",
    "details": { "draft_base": "a1b2c3", "head": "d4e5f6" },
    "request_id": "01J8X..."
  }
}
```

`message` **Türkçe ve kullanıcıya gösterilebilir**; `code` sabit ve İngilizce;
`details` makine tarafından okunur.

## Adlandırma

- Yollar çoğul ve kebab-case: `/api/role-schemas`, `/api/runs/{run_id}/logs`
- Alanlar `snake_case` (frontend tarafında dönüştürülür)
- Eylem uçları alt kaynak olarak: `POST /api/drafts/{id}/publish`

## Bitti Tanımı

- [ ] [docs/09-api-contract.md](../../docs/09-api-contract.md) güncellendi
- [ ] İstek ve yanıt için Pydantic modelleri tanımlı
- [ ] Mutlu yol + en az bir hata yolu için entegrasyon testi
- [ ] Yetkilendirme testi (yetkisiz kullanıcı 403 alıyor)
- [ ] Frontend istemci tipleri güncellendi (`frontend/src/lib/api.ts`)
