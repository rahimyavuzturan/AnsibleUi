# 00 — Genel Bakış

## Problem

`Ansible.appAdminConfig` deposu, kurumun Windows sunucu kurulum otomasyonunu barındırır:
65 rol, ~120 playbook, 4 ortam (nonprod / prod / dmz_nonprod / dmz_prod), INI formatında
envanterler ve Azure Pipeline üzerinden çalıştırma.

Sistem çalışıyor, fakat **erişilebilir değil**. 20 kişilik ekipte Ansible'a hakim olan
birkaç kişi var. Tespit edilen somut sorunlar:

| Sorun | Kanıt |
|---|---|
| **Keşfedilebilirlik yok** | Bir rolün ne yaptığını anlamak için `roles/<ad>/tasks/*.yml` dosyalarını açıp okumak gerekiyor. Parametreleri hiçbir yerde tanımlı değil — `defaults/main.yml` ve `meta/argument_specs.yml` yok. |
| **Sessiz hatalar** | `create_dir` listesi ile `createWebSiteApp.appNames` listesi elle senkron tutuluyor. Eksik bir klasör, playbook'un **son adımında** "specified folder must already exist" hatasıyla patlıyor — önceki 16 adım çoktan uygulanmış oluyor. |
| **Görünmez bağımlılıklar** | `iis_binding_http`, sertifikayı en son çalışan `importCertificate` görevinin `register` değişkeninden alıyor. Görev sırası değişirse yanlış sertifika bağlanıyor ve bu hiçbir yerde belli olmuyor. |
| **Kopyala-yapıştır çoğalması** | isube/msube/tsube için neredeyse aynı üç dosya var; aralarındaki farklar kasıtlı mı hata mı belli değil. |
| **Çalıştırma sürtünmesi** | Yeni playbook, pipeline'daki elle yazılmış `pbList` dropdown'ına eklenmeden çalıştırılamıyor. |
| **Denetim izi zayıf** | Kimin neyi neden değiştirdiği yalnızca git geçmişinde; hangi sunuculara ne uygulandığı ayrı yerde. |

## Amaç

Ansible'ı **20 kişilik ekibin tamamına** hitap eder hâle getirmek — mevcut güvenlik ve
çalıştırma modelini bozmadan.

### Hedefler

| # | Hedef | Ölçüt |
|---|---|---|
| G1 | Ansible bilmeyen biri mevcut bir playbook'u güvenle değiştirebilsin | Yeni kullanıcı, eğitimsiz, 10 dakikada bir klasör ekleme değişikliğini PR'a dönüştürebiliyor |
| G2 | Her değişiklik izlenebilir olsun | Tüm yazma işlemleri PR + denetim kaydı üretiyor; `main`'e doğrudan yazma teknik olarak imkansız |
| G3 | Depo keşfedilebilir olsun | 65 rol ve ~120 playbook aranabilir; her rolün parametreleri ve gerçek kullanım örnekleri görünür |
| G4 | Çalıştırma şeffaf olsun | Arayüzden tetiklenen çalıştırmanın canlı log'u ve task×host durum matrisi izlenebiliyor |
| G5 | Mevcut YAML bozulmasın | Depodaki her `.yml` parse→serialize sonrası **byte düzeyinde aynı** |
| G6 | Hatalar çalıştırmadan önce yakalansın | Bilinen tutarsızlık desenleri (eksik klasör, kopuk sertifika zinciri) düzenleme anında uyarı üretiyor |

### Hedef Olmayanlar (MVP)

- Ansible'ı platformun kendi içinde çalıştırmak (kendi runner'ı) — mevcut agent pool'ları kullanılır.
- Hedef Windows sunuculara doğrudan bağlanmak.
- Vault değerlerini okumak veya yönetmek.
- `Ansible.appAdminConfig` deposunu yeniden yapılandırmak veya refactor etmek.
- Birden fazla Ansible deposunu desteklemek (Faz 9).
- Ansible'ın tüm modül evrenini görselleştirmek — yalnızca bu depoda fiilen kullanılanlar.

## Başarı Kriterleri

| # | Kriter | Doğrulama |
|---|---|---|
| K1 | Referans depodaki tüm `.yml` dosyaları için round-trip **%100 byte-identical** | `pytest tests/golden` |
| K2 | 65 rolün **≥%80'i** için parametre şeması otomatik çıkarılıp form üretilebiliyor | `pytest -k schema_infer` + kapsam raporu |
| K3 | Demo senaryosu uçtan uca **<5 dakika** | [demo-script.md](demo-script.md) elle koşum |
| K4 | p95 sayfa yüklenmesi <2 sn, rol arama <300 ms | Playwright + API metrikleri |
| K5 | Bilinen üç hata deseni düzenleme anında yakalanıyor | `pytest -k validators` |

## Paydaşlar

| Rol | Beklenti |
|---|---|
| Otomasyon ekibi | Mevcut iş akışını bozmayan, hızlandıran bir araç; YAML'a istedikleri an inebilmek |
| Uygulama ekipleri | Ansible öğrenmeden kendi kurulumlarını tanımlayıp tetikleyebilmek |
| Güvenlik / operasyon | Onaysız prod değişikliği olmaması, tam denetim izi, secret sızmaması |
| Yönetim | Kurulum süresinin ve hata oranının düşmesi; bilginin tek kişiye bağlı olmaması |

## Temel Tasarım İlkesi

> **YAML tek doğruluk kaynağıdır. Arayüz yalnızca bir görünümdür.**

Bu ilke, benzer araçların başarısız olduğu noktayı adresler: kendi iç modelini doğruluk
kaynağı yapan araçlar, elle yazılmış YAML'ı bozar ve ekip araca güvenmeyi bırakır.

Sonuçları:
- Arayüzün temsil edemediği yapı (gömülü PowerShell, karmaşık Jinja, `set_fact`) **kaybolmaz**;
  "ham YAML" kartı olarak aynen korunur ve metin olarak düzenlenebilir.
- Depoda elle yapılan değişiklik arayüzde anında görünür; arayüz "sahiplik" iddia etmez.
- Arayüz herhangi bir anda devre dışı kalsa, depo tam olarak çalışır durumda kalır.

Ayrıntı: [04-ansible-ir-spec.md](04-ansible-ir-spec.md) ·
[ADR-0001](adr/ADR-0001-yaml-source-of-truth.md)

## Kapsam Özeti

**MVP'de var:** rol/playbook/envanter kataloğu ve arama · görsel playbook düzenleyici
(rol sürükle-bırak, şemadan üretilen dinamik form, ham YAML node'ları) · envanterden hedef
bağlama · örtük bağımlılık grafı ve uyarılar · dosyalar arası doğrulayıcılar ·
taslak → diff → branch → PR akışı · `pbList` otomatik güncelleme · pipeline tetikleme,
canlı log ve task durumları · yerel kimlik doğrulama, ortam kapsamlı RBAC, onay, denetim izi ·
Helm ile Rancher dağıtımı.

**MVP'de yok:** yapay zekâ asistanı (Faz 7) · görev seviyesi ham modül düzenleme (Faz 8) ·
görsel pipeline tasarımcısı (Faz 8) · LDAP (Faz 8) · kendi Ansible runner'ı ·
vault değeri okuma/yazma · çok-depo desteği (Faz 9).

Faz ve iş paketi kırılımı: [13-roadmap-wbs.md](13-roadmap-wbs.md)

## Mevcut Sistemin Doğrulanmış Özellikleri

Tasarım kararları bu tespitlere dayanır:

| Konu | Durum |
|---|---|
| Git remote | `https://ktdevops/tfs/KT/KT.ITAutomation/_git/Ansible.appAdminConfig` — **on-prem Azure DevOps Server (TFS)**, `dev.azure.com` değil |
| Branch'ler | `main` (varsayılan, CI tetikli), `ertan` (kişisel) |
| Roller | `roles/` 47 generic + `roles_custom/` 18 composite = **65** |
| Playbook'lar | ~120 (pipeline `pbList` listesinde) |
| Envanter | **INI formatı**; `inventory/` altında ortam bazlı klasörler |
| Bağlantı | `ansible_connection=winrm`, `ntlm`, port 5985, kimlik vault'tan |
| Agent pool'ları | nonprod → `AnsibleTestEnv`, prod → `Ansible`, dmz_prod → `spd1ansible` |
| Çalıştırma | `Ansible@0` task'ı, `--vault-password-file` secure file'dan |
| Dağıtım | `main`'e merge → CI → `scripts/copyRolestoRoles.sh` → roller `/etc/ansible/roles`'a kopyalanır |
| Vault | Depo **dışında**: `/etc/ansible/vault/vault_*.yml` |
| Eksikler | `ansible.cfg`, `requirements.yml`, `meta/argument_specs.yml`, lint, test, `.gitignore` — hiçbiri yok |
