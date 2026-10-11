# ADR-0004 — PR Tabanlı Yazma Yolu

- **Durum:** Kabul edildi
- **Tarih:** 2026-09-30

## Bağlam

Platform, kullanıcıların yaptığı değişiklikleri Azure DevOps deposuna yazmalıdır.
Hedef kitle yalnızca otomasyon ekibi değil; **uygulama ekipleri de self-servis**
kullanacak.

Seçenekler:

1. `main` branch'ine doğrudan commit.
2. Branch + commit + **Pull Request**, merge insan onayıyla.
3. Kullanıcı seçer (taslak / branch / PR).

## Karar

**Her değişiklik `ansibleui/<kullanıcı>/<slug>` branch'ine yazılır ve bir Pull Request
açılır. Merge her zaman Azure DevOps'ta bir insan tarafından yapılır.**

Platform **merge etmez**; PAT'e merge yetkisi verilmez.

`main`'e yazma yapısal olarak imkânsız kılınır:
- Branch adı üretiminde `ansibleui/` öneki zorunlu.
- Push fonksiyonunda çalışma zamanı kontrolü: yasaklı branch adları reddedilir.
- Bu davranış `tests/integration/test_git_safety.py` ile kanıtlanır.

## Gerekçe

| Kriter | Doğrudan commit | **PR tabanlı** | Kullanıcı seçer |
|---|---|---|---|
| Hata yakalama | Yok | İnsan incelemesi | Değişken |
| Denetim izi | Zayıf | Güçlü (PR geçmişi) | Tutarsız |
| Self-servis güvenliği | **Tehlikeli** | Güvenli | Tehlikeli seçenek mevcut |
| Mevcut süreçle uyum | Uyumsuz | Uyumlu | Kısmen |
| Geri alınabilirlik | Zor | PR reddedilebilir | Değişken |
| Kullanıcı hızı | En hızlı | Bir onay adımı | — |

Belirleyici olan **self-servis** kararıdır. Uygulama ekipleri Ansible uzmanı değildir;
değişikliklerinin bir uzman tarafından incelenmesi gerekir. Doğrudan commit, bu
incelemeyi ortadan kaldırırdı.

Seçenek 3 reddedildi: güvenli olmayan bir seçeneği sunmak, er ya da geç kullanılması
demektir. Tek ve güvenli bir yol daha iyidir.

Bu karar aynı zamanda **çalıştırmanın yalnızca `main` üzerinden yapılmasıyla**
birleşince güçlü bir garanti üretir: hiçbir değişiklik insan onayı olmadan bir
sunucuya uygulanamaz.

## Sonuçlar

**Olumlu**
- İnsan incelemesi zorunlu → uzman gözü her değişikliği görür.
- Tam denetim izi: PR geçmişi + commit trailer + `audit_log`.
- Mevcut ekip alışkanlığıyla uyumlu.
- Geri alma kolay: PR reddedilir, hiçbir şey olmamış gibi olur.
- Platformun ele geçirilmesi doğrudan üretim etkisi yaratmaz.

**Olumsuz**
- Ek adım: kullanıcı PR'ının merge edilmesini beklemek zorunda.
- Çakışma yönetimi gerekir (`base_commit_sha` takibi, yeniden temelleme akışı).
- İnceleyenler üzerinde yük oluşur.
- Taslaktan çalıştırmaya kadar geçen süre uzar.

**Azaltımlar**
- Taslaklar günlerce durabilir; acele gerekmez.
- Otomatik PR açıklaması inceleyene bağlam verir: değişiklik özeti, etkilenen roller,
  **etkilenen host grupları**, doğrulayıcı sonuçları.
- Doğrulayıcılar, incelemeye gelmeden önce hataların çoğunu yakalar → inceleme yükü azalır.

## Uygulama

```python
FORBIDDEN_BRANCHES = frozenset({"main", "master", "HEAD"})

def push(self, branch: str) -> None:
    """Branch'i uzaga gonderir; korumali branch adlarini reddeder."""
    if branch in FORBIDDEN_BRANCHES:
        raise UnsafeBranchError(branch)
    if not branch.startswith(f"{self._settings.branch_prefix}/"):
        raise UnsafeBranchError(branch)
    self._repo.remote("origin").push(branch)
```

Ayrıntı: [docs/06-git-sync-and-ado.md](../06-git-sync-and-ado.md) bölüm 3.
