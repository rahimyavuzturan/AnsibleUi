# ADR-0003 — Kendi Runner Yerine Pipeline Tetikleme

- **Durum:** Kabul edildi
- **Tarih:** 2026-09-30

## Bağlam

Platform playbook çalıştırmayı desteklemelidir. İki yaklaşım vardı:

1. **Kendi runner'ı** — Platform kendi container'ında `ansible-playbook` çalıştırır.
2. **Pipeline tetikleme** — Platform mevcut Azure Pipeline'ı REST API ile tetikler.

Mevcut durum:
- 4 ayrı ortam, 4 ayrı agent havuzu (`AnsibleTestEnv`, `Ansible`, `spd1ansible`, dmz test).
- Vault parolası Azure DevOps secure file olarak yalnızca agent'a iniyor.
- DMZ ve üretim ağlarına erişim yalnızca ilgili agent'lardan mümkün.
- Rancher pod'undan hedef Windows sunuculara erişim **yok** (ağ izolasyonu).

## Karar

**Platform Ansible'ı çalıştırmaz. Mevcut Azure Pipeline'ı tetikler ve sonucu izler.**

```http
POST /_apis/build/builds?api-version=6.0
{ "definition": {"id": 42},
  "sourceBranch": "refs/heads/main",
  "parameters": "{\"pbList\":\"<playbook yolu>\"}" }
```

Log'lar build timeline ve log uçlarından artımlı olarak çekilir, `ansible -v` çıktısı
ayrıştırılır ve WebSocket ile arayüze aktarılır.

## Gerekçe

| Kriter | Kendi runner | Pipeline tetikleme |
|---|---|---|
| Vault erişimi | Platform parolayı görmek zorunda | **Platform hiç görmez** |
| Ağ erişimi | DMZ/prod ağlarına erişim gerekir (yok) | Mevcut agent'lar kullanılır |
| Denetim tekliği | İkinci bir çalıştırma kaydı oluşur | Tümü ADO build geçmişinde |
| Güvenlik incelemesi | Yeni ve geniş bir yüzey | Mevcut model korunur |
| Uygulama maliyeti | WinRM, vault, izolasyon, kuyruk | REST çağrısı + log yoklama |
| MVP'ye uygunluk | Sığmaz | Sığar |
| Canlı log | Gerçek zamanlı | ~5 sn gecikmeli |

Belirleyici olan **vault** maddesidir: kendi runner'ı, platformun üretim sertifika
parolalarına erişmesini gerektirirdi. Bu, platformun ele geçirilmesini doğrudan bir
üretim olayına dönüştürürdü.

Pipeline tetikleme modelinde platformun ele geçirilmesi en kötü durumda
"kötü niyetli bir PR açılması" ile sonuçlanır — o da insan incelemesinden geçer.

## Sonuçlar

**Olumlu**
- Vault parolası platformda hiç bulunmaz.
- Mevcut güvenlik ve ağ modeli değişmez; yeni güvenlik incelemesi gerekmez.
- Tüm çalıştırmalar tek yerde (ADO build geçmişi) kayıtlı.
- Platform devre dışı kalsa pipeline'lar çalışmaya devam eder.
- Uygulama maliyeti düşük → MVP'ye sığar.

**Olumsuz**
- Log ~5 saniye gecikmeli. Kabul: kurulum playbook'ları dakikalarca sürüyor.
- Çalıştırma yalnızca `main` üzerinden yapılabilir. **Bu aslında bir özelliktir**:
  PR merge edilmeden hiçbir şey çalışmaz.
- `pbList` açılır listesi kısıtı ortaya çıkar (bkz. aşağıda).
- `--check` (dry-run) MVP'de desteklenemez; pipeline parametresi eklenmesi gerekir.

**`pbList` kısıtı ve çözümü**

Pipeline, playbook yolunu elle yazılmış bir `values` listesinden alır. Bu listede
olmayan playbook çalıştırılamaz.

MVP çözümü: playbook oluşturan her PR, **aynı PR içinde** ilgili ortamın pipeline
dosyasındaki `values` listesini alfabetik sırada günceller (WP-24).
Uzun vade: listeyi platforma taşımak (WP-81).

## Uygulama

- [docs/07-execution-and-logs.md](../07-execution-and-logs.md) — tetikleme ve log akışı.
- [docs/06-git-sync-and-ado.md](../06-git-sync-and-ado.md) bölüm 4 — `pbList` çözümü.
- Ön kontroller (WP-34): playbook `main`'de mi, `pbList`'te mi, yetki var mı, onay alındı mı.
