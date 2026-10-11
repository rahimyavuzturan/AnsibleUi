---
description: "Use when changing SQLAlchemy models, Alembic migrations, repositories or query code. Covers derived-vs-persistent data split, size budget and migration safety."
applyTo: "backend/app/db/**,backend/alembic/**"
---

# Veritabanı Kuralları

> Veri modeli ve boyut bütçesi: [docs/03-domain-model.md](../../docs/03-domain-model.md) ·
> Gerekçe: [ADR-0006](../../docs/adr/ADR-0006-postgres-small-footprint.md)

## Türetilmiş / Kalıcı Ayrımı

Her yeni tablo bu iki kümeden birine girer. Hangisi olduğu model docstring'inde yazılır.

| Tür | Anlamı | Örnek |
|---|---|---|
| **Türetilmiş** | Depodan yeniden üretilebilir, silinse veri kaybı olmaz | `role_schema`, `playbook_index`, `inventory_host` |
| **Kalıcı** | Yalnızca burada yaşar, kaybı geri alınamaz | `user`, `draft`, `run`, `approval`, `audit_log` |

Türetilmiş tablolar senkronizasyonda güvenle yeniden yazılabilir.
Kalıcı tablolar **asla** toplu silinmez.

## Boyut Bütçesi

Toplam hedef **< 1 GB**. Bunu korumak için:

1. Ansible log çıktısı DB'ye **yazılmaz** — PVC üzerinde dosya, DB'de yalnızca yol.
2. Dosya içeriği DB'de tutulmaz — kaynak git deposudur.
3. Büyük JSON alanları `jsonb` ve yalnızca özet veri.
4. `audit_log` ve `run` için saklama politikası (varsayılan 90 gün) tanımlıdır.
5. Yeni bir tablo satır başına > 10 KB büyüyecekse önce gerekçe ve ADR.

## Model Kuralları

```python
class Draft(Base):
    """Kalici. Kullanicinin yayinlanmamis degisiklik kumesi."""
    __tablename__ = "draft"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    base_commit: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- SQLAlchemy 2.0 `Mapped[...]` / `mapped_column` biçimi; eski `Column` kullanılmaz.
- Birincil anahtar `UUID`; `run` gibi sıralı tablolarda `created_at` indeksli.
- Zaman damgaları UTC ve `timezone=True`.
- Tablo adları tekil ve `snake_case`.
- Sorgular repository sınıfları üzerinden; router veya servis içinde ham `select()` yok.

## Migrasyon Kuralları

1. Her şema değişikliği bir Alembic revizyonu ister; elle `CREATE TABLE` yok.
2. Revizyon mesajı WP numarasını içerir: `alembic revision -m "WP-31 add draft table"`.
3. `downgrade()` gerçekten yazılır; `pass` bırakılmaz.
4. Yıkıcı adımlar (sütun silme, tip daraltma) ayrı bir revizyonda ve PR açıklamasında belirtilir.
5. Migrasyon üretildikten sonra `alembic upgrade head` **ve** `alembic downgrade -1`
   yerelde denenir.
6. Veri taşıma gerekiyorsa migrasyon içinde ORM değil, `op.execute()` ile ham SQL kullanılır
   (model sınıfları zamanla değişir, migrasyon sabit kalmalı).

## Bitti Tanımı

- [ ] Model docstring'i türetilmiş/kalıcı sınıfını belirtiyor
- [ ] Alembic revizyonu üretildi, `upgrade` ve `downgrade` denendi
- [ ] Repository metodu için test yazıldı
- [ ] Boyut etkisi > 10 MB/ay ise [docs/03](../../docs/03-domain-model.md) bütçe tablosu güncellendi
