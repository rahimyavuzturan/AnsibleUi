---
description: "Use when writing tests: golden round-trip tests, unit tests, integration tests with fake Azure DevOps, Playwright E2E and security tests. Covers coverage targets and fixture policy."
applyTo: "backend/tests/**,frontend/src/**/*.test.ts,frontend/src/**/*.test.tsx,frontend/e2e/**"
---

# Test Kuralları

> Strateji: [docs/14-testing-strategy.md](../../docs/14-testing-strategy.md)

## Altın Testler (Golden Tests) — En Yüksek Öncelik

`backend/tests/golden/` içindeki testler projenin can damarıdır. Başarısızlarsa
CI durur ve sonraki adımlar çalışmaz.

Üç değişmez kontrol edilir:

```python
def test_roundtrip_is_byte_identical(fixture_path: Path) -> None:
    """Degistirilmeden okunup yazilan dosya birebir ayni olmali."""

def test_patch_only_touches_target(fixture_path: Path) -> None:
    """Tek parametre degistiginde diff yalnizca o satiri icermeli."""

def test_no_task_is_lost(fixture_path: Path) -> None:
    """Gorev sayisi ve sirasi korunmali."""
```

### Fixture Politikası

- Fixture'lar gerçek depodan **kopyalanır**, elle sadeleştirilmez. Zor durumlar
  (gömülü PowerShell, Jinja koşulları, anchor'lar) korunur.
- Gerçek sunucu adı / IP / sertifika parolası içeren fixture'lar anonimleştirilir
  ama **yapı** bozulmaz.
- Yeni bir parser hatası bulunduğunda: önce hatayı yeniden üreten fixture eklenir,
  sonra düzeltme yapılır.
- `skip` / `xfail` ile altın test devre dışı bırakılmaz.

## Test Piramidi

| Katman | Kapsam | Araç |
|---|---|---|
| Birim | `app/ansible/` ≥ %90, diğerleri ≥ %70 | pytest |
| Entegrasyon | API uçları, sahte ADO sunucusu, gerçek Postgres | pytest + httpx + testcontainers |
| E2E | 10 kritik kullanıcı akışı | Playwright |
| Güvenlik | 8 senaryo (bkz. docs/08) | pytest |

## Genel Kurallar

1. **Her WP kendi testleriyle biter.** "Testi sonra yazarız" kabul edilmez.
2. **Davranış test edilir, uygulama değil.** Özel metotları test etme.
3. **Ağ çağrısı sahtelenir.** Gerçek Azure DevOps'a giden test yazılmaz
   (`respx` veya `httpx.MockTransport`).
4. **Zaman ve UUID sabitlenir.** `freezegun` / sabit tohum; kararsız test yasak.
5. **Anlık görüntü testleri `syrupy` ile.** Değişen anlık görüntü PR'da
   gözle incelenir, körlemesine `--snapshot-update` yapılmaz.
6. **Test adları ne doğruladığını söyler:**
   `test_publish_rejects_when_branch_is_main` — `test_publish_2` değil.

## Güvenlik Testleri (zorunlu)

- `..` içeren yol reddediliyor mu
- İzinli kök dışı yol reddediliyor mu
- `main` branch'ine push reddediliyor mu
- Vault dosyası okuma girişimi engelleniyor mu
- Secret log'a düşüyor mu
- Yetkisiz kullanıcı 403 alıyor mu
- Onaysız çalıştırma engelleniyor mu
- Hata yanıtı iç ayrıntı sızdırıyor mu

## Frontend Testleri

- Testing Library; `container.querySelector` yerine erişilebilir sorgular.
- Kullanıcı etkileşimi `userEvent` ile.
- MSW ile API sahtelenir.

## Bitti Tanımı

- [ ] Yeni kod için pozitif ve negatif durum testi var
- [ ] Altın testler yeşil ve atlanmamış
- [ ] Kapsam hedefi karşılanıyor
- [ ] Testler kararlı (üç kez arka arkaya çalıştırıldı)
