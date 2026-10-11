# 13 — Yol Haritası ve İş Kırılımı (WBS)

> **Bu dosya canlı bir belgedir.** Bir iş paketi tamamlandığında durumu burada güncellenir.

## Durum Özeti

| Faz | Kapsam | Durum |
|---|---|---|
| Faz 0 | Temel | 🔄 Devam ediyor |
| Faz 1 | Ansible Intelligence Core | 🔄 Devam ediyor |
| Faz 2 | Git ve Azure DevOps | ⬜ Başlamadı |
| Faz 3 | API ve Veri Modeli | ⬜ Başlamadı |
| Faz 4 | Frontend | ⬜ Başlamadı |
| Faz 5 | Çalıştırma Konsolu | ⬜ Başlamadı |
| Faz 6 | Auth, RBAC, Dağıtım | ⬜ Başlamadı |
| **MVP** | **Faz 0-6** | |
| Faz 7 | Yapay Zekâ Asistanı | ⬜ MVP sonrası |
| Faz 8 | İleri Özellikler | ⬜ MVP sonrası |
| Faz 9 | Ölçeklenme | ⬜ MVP sonrası |

Durum sembolleri: ⬜ başlamadı · 🔄 devam ediyor · ✅ tamamlandı · ⛔ engellendi

## Okuma Kılavuzu

- `[P]` — Bu iş paketi diğerleriyle **paralel** yürütülebilir.
- `←WP-xx` — Bu iş paketine **bağımlıdır**; önce o tamamlanmalıdır.
- **Kabul kriteri** karşılanmadan iş paketi tamamlanmış sayılmaz.

---

## FAZ 0 — Temel

| WP | Başlık | Çıktı | Kabul kriteri | Durum |
|---|---|---|---|---|
| WP-00 | Depo iskeleti | `backend/`, `frontend/`, `deploy/`, `docs/`, `.github/`, `docker-compose.yml`, `.env.example` | `docker compose up` ile API `/healthz` ve SPA yanıt veriyor | 🔄 |
| WP-01 `[P]` | Dokümantasyon | `docs/00-15`, `docs/adr/`, `docs/demo-script.md` | Tüm dosyalar mevcut, iç bağlantılar çalışıyor | ✅ |
| WP-02 `[P]` | Agent kuralları | `AGENTS.md`, `.github/instructions/*.instructions.md` | Her dosyada geçerli frontmatter; `applyTo` desenleri doğru | ✅ |
| WP-03 `[P]` | Kalite altyapısı | ruff, mypy, pytest, eslint, prettier, vitest, CI pipeline | Tüm kalite komutları yeşil; CI çalışıyor | ⬜ |
| WP-04 `[P]` | Bağlantı doğrulama | `docs/11` bölüm 11'deki 8 maddenin test sonuçları | Sonuçlar dokümana tarih ve kişi ile yazıldı | ⬜ |

WP-04 kritiktir: pod → `ktdevops` erişimi, `api-version`, PAT kapsamları ve webhook
desteği doğrulanmazsa Faz 2 planı değişir.

---

## FAZ 1 — Ansible Intelligence Core ★ EN RİSKLİ

Bu faz **önce** yapılır. Kayıpsız gidiş-dönüş çalışmıyorsa projenin temel vaadi geçersizdir.

| WP | Başlık | Çıktı | Kabul kriteri | Durum |
|---|---|---|---|---|
| WP-10 | Round-trip parser/serializer | `ansible/roundtrip.py` | **Altın test**: referans depodaki TÜM `.yml` parse→serialize sonrası **byte-identical** (K1) | ✅ |
| WP-11 ←WP-10 | IR node modeli | `ansible/ir.py` | `install_isube_nonprod_freshserver.yml` içindeki 17 üst düzey görevin tamamı doğru node tipine ayrışıyor, hiçbiri kaybolmuyor | ✅ |
| WP-12 `[P]` | INI envanter ayrıştırıcı | `ansible/inventory.py` | `inventory/z_altortam_all` tüm grup/children/vars doğru; `ansible-inventory --list` ile karşılaştırma testi geçiyor | ⬜ |
| WP-13 ←WP-11 | Rol şeması çıkarımı | `ansible/schema_infer.py` | 65 rolün ≥%80'i için şema (K2); `createWebSiteApp` 3, `iis_binding_http` 4 varyanta ayrışıyor | ⬜ |
| WP-14 ←WP-11 | Bağımlılık grafı | `ansible/graph.py` | `importCertificate → iis_binding_http` örtük kenarı tespit ediliyor | ⬜ |
| WP-15 ←WP-11 | Doğrulayıcılar | `ansible/validators.py` | V001-V010 uygulanmış; bilinen isube/msube hataları yakalanıyor (K5) | ⬜ |

**Faz 1 çıkış kapısı:** WP-10'un altın testi yeşil olmadan Faz 2'ye geçilmez.

**WP-10 sonucu (2026-09-30):** ✅ 477/477 dosya birebir. 1441 altın test, sıfır atlama.

**WP-11 sonucu (2026-09-30):** ✅ 474 ayrıştırılabilir dosyanın tamamı IR'a çevriliyor; 1269 rol çağrısı (809 `roles:` girdisi + 460 `include_role`) ve 111 `include_tasks` hedefi eksiksiz tanınıyor. Yalnızca **2 node** `RAW` kalıyor ve ikisi de depodaki gerçek bir hatadan kaynaklanıyor (aşağıya not düşüldü). Kilitli parametre oranı %10'un altında. `app/ansible/ir.py` kapsamı %96.
Tasarım ölçüm sonrası değişti: tam yeniden üretim yerine **cerrahi metin yaması**
— bkz. [ADR-0007](adr/ADR-0007-surgical-text-patching.md). `app/ansible/` kapsamı %96.

---

## FAZ 2 — Git ve Azure DevOps

| WP | Başlık | Çıktı | Kabul kriteri | Durum |
|---|---|---|---|---|
| WP-20 `[P]` | Git servis katmanı | `gitops/repo_service.py` | Clone/fetch/branch/commit/push çalışıyor; `main`'e push **test ile kanıtlanmış** şekilde imkânsız | ⬜ |
| WP-21 `[P]` | ADO REST istemcisi | `ado/client.py` | Sahte sunucuya karşı sözleşme testleri geçiyor; TLS doğrulama açık; retry/backoff var | ⬜ |
| WP-22 ←WP-20,WP-10 | Depo indeksleyici | `services/index_service.py` + worker job | Tam indeksleme <60 sn; artımlı indeksleme yalnızca değişen dosyaları parse ediyor | ⬜ |
| WP-23 ←WP-20,WP-21 | Yayınlama akışı | `services/publish_service.py` | Taslak → diff → branch → commit → push → PR; PR URL'i dönüyor; çakışma senaryosu testli | ⬜ |
| WP-24 ←WP-23 | `pbList` güncelleme | `services/pipeline_file_service.py` | Yeni playbook PR'ında doğru ortam dosyasının `values` listesine alfabetik eklendi; dosyanın geri kalanı byte-identical | ⬜ |

---

## FAZ 3 — API ve Veri Modeli

| WP | Başlık | Çıktı | Kabul kriteri | Durum |
|---|---|---|---|---|
| WP-30 `[P]` | DB şeması + Alembic | `db/models.py`, migration'lar | `alembic upgrade head` temiz DB'de çalışıyor; değişmezler (bölüm 7) kısıtlarla zorlanıyor | ⬜ |
| WP-31 ←WP-30 | Katalog ve arama API | `/api/roles`, `/api/playbooks`, `/api/inventory`, `/api/search` | Arama <300 ms; OpenAPI şeması üretiliyor | ⬜ |
| WP-32 ←WP-30,WP-11 | Düzenleyici API | `/api/documents/*`, `/api/drafts/*` | Node yaması uygulanıyor; dokunulmayan içerik byte-identical kalıyor | ⬜ |
| WP-33 ←WP-23 | Yayınlama API | `/api/publish/preview`, `/api/publish` | Diff önizleme doğru; bloklayıcı doğrulama varsa `can_publish: false` | ⬜ |
| WP-34 ←WP-21 | Çalıştırma API | `/api/runs/*`, `/ws/runs/{id}` | 4 ön kontrol bloklayıcı çalışıyor | ⬜ |

---

## FAZ 4 — Frontend

| WP | Başlık | Çıktı | Kabul kriteri | Durum |
|---|---|---|---|---|
| WP-40 `[P]` | Uygulama kabuğu | Layout, tema, navigasyon, durum bileşenleri | [docs/10](10-ui-ux-spec.md) tasarım diliyle uyumlu; 4 durum (yükleniyor/boş/hata/dolu) ele alınmış | ⬜ |
| WP-41 ←WP-31 | Rol kataloğu | Arama, filtre, rol detayı | 65 rol listeleniyor; `createWebSiteApp` 3 varyantıyla ve gerçek kullanım örnekleriyle görünüyor | ⬜ |
| WP-42 ←WP-31 | Envanter gezgini | Grup ağacı, host detayı | `test_isube` → 2 host + hedefleyen playbook'lar görünüyor | ⬜ |
| WP-43 ←WP-32,WP-13 | **Görsel düzenleyici** | React Flow canvas, dinamik form, Monaco ham YAML | `install_isube_nonprod_freshserver.yml` açılıyor, 17 node görünüyor, bir `create_dir` yoluna ekleme yapılıp kaydediliyor | ⬜ |
| WP-44 ←WP-14 | Graf görselleştirme | Sıra + örtük + dosya kenarları, uyarı rozetleri | Sertifika→binding kesikli oku görünüyor; sıra bozulunca bloklayıcı uyarı çıkıyor | ⬜ |
| WP-45 ←WP-42,WP-43 | Hedef bağlama | Envanterden `hosts:` alanına sürükle-bırak | Sürükleme sonrası YAML doğru güncelleniyor | ⬜ |
| WP-46 ←WP-33 | Diff ve yayınlama | Monaco DiffEditor, PR formu, çakışma ekranı | Azure DevOps'ta PR gerçekten açılıyor | ⬜ |

---

## FAZ 5 — Çalıştırma Konsolu

| WP | Başlık | Çıktı | Kabul kriteri | Durum |
|---|---|---|---|---|
| WP-50 ←WP-21 | Ansible log ayrıştırıcı | `services/log_parser.py` | 3 gerçek build log'undan doğru task×host matrisi; maskeleme çalışıyor | ⬜ |
| WP-51 ←WP-34,WP-50 | Çalıştırma ekranı | Ön kontrol özeti, onay, canlı log, durum matrisi | Demo senaryosu uçtan uca çalışıyor (K3) | ⬜ |
| WP-52 `[P]` | Çalıştırma geçmişi | Liste, filtre, detay, tekrar çalıştır | Her çalıştırma denetim izinde görünüyor | ⬜ |

---

## FAZ 6 — Auth, RBAC, Dağıtım

| WP | Başlık | Çıktı | Kabul kriteri | Durum |
|---|---|---|---|---|
| WP-60 | AuthProvider + yerel kullanıcılar | `auth/`, login ekranı, JWT çerez | LDAP için arayüz hazır; sahte sağlayıcı ile test ediliyor | ⬜ |
| WP-61 ←WP-60 | RBAC ve onay akışı | Ortam kapsamlı roller, dört göz ilkesi | Rol×eylem×ortam matrisi tam test edilmiş; Viewer prod'da çalıştıramıyor | ⬜ |
| WP-62 ←WP-60 | Denetim izi | `audit_log` + yönetim ekranı | Tüm yazma işlemleri kayıtlı; kayıtlar değiştirilemiyor | ⬜ |
| WP-63 `[P]` | Docker ve Helm | `deploy/helm/ansible-ui`, Dockerfile'lar | `helm install` ile Rancher namespace'inde ayağa kalkıyor; PVC ve Ingress çalışıyor | ⬜ |
| WP-64 ←WP-63 | Yapılandırma ve secret | ConfigMap, Secret şablonları, CA bundle | `verify=False` hiçbir yerde yok; secret log'a düşmüyor | ⬜ |
| WP-65 | E2E ve demo | Playwright senaryoları, `docs/demo-script.md` doğrulaması | CI'da yeşil; demo <5 dk | ⬜ |

**→ MVP BİTİŞ**

---

## FAZ 7 — Yapay Zekâ Asistanı

| WP | Başlık | Çıktı |
|---|---|---|
| WP-70 | LLM soyutlama katmanı | Qwen istemcisi, timeout/retry, token bütçesi, istem log'u |
| WP-71 ←WP-70 | Bağlam üretici | Rol şemaları + envanter + benzer playbook'lardan deterministik bağlam |
| WP-72 ←WP-71 | Doğal dilden playbook | Sohbet → IR taslağı → doğrulama → canvas önizleme → insan onayı |
| WP-73 ←WP-70 | Hata açıklayıcı | Maskelenmiş log → Türkçe açıklama + öneri |
| WP-74 ←WP-71 | Değişiklik gözden geçirme | Diff analizi, riskli desen işaretleme |
| WP-75 | Güvenlik bariyerleri | Denetim, istem enjeksiyonu koruması, kapalı varsayılan |

## FAZ 8 — İleri Özellikler

| WP | Başlık |
|---|---|
| WP-80 | Görev seviyesi düzenleyici (ham `win_*` modül node'ları, modül şema kataloğu) |
| WP-81 | Görsel pipeline tasarımcısı; `pbList` allowlist'inin platforma taşınması |
| WP-82 | `meta/argument_specs.yml` üretimi ve referans depoya PR ile kazandırma |
| WP-83 | `--check` (dry-run) modunda çalıştırma |
| WP-84 | Şablon/blueprint galerisi ("yeni sube sunucusu" gibi parametrik şablonlar) |
| WP-85 | LDAP entegrasyonu |
| WP-86 | Depo sağlık panosu (kullanılmayan roller, kopya desenler, lint önerileri) |

## FAZ 9 — Ölçeklenme

Çok-depo desteği · çok-koleksiyon · metrik ve SLO panoları · self-servis onboarding.

---

## Engeller

| # | Engel | Etki | Çözüm |
|---|---|---|---|
| E1 | Geliştirme makinesinde **Node 16.20.2** kurulu; bağımlılıklar Node ≥ 20 istiyor | Frontend kurulamaz, `npm ci` / `vitest` / `vite build` çalışmaz | Node 20 LTS kurulmalı (tercihen `nvm-windows` ile) |
| E2 | Docker Desktop **çalışmıyor** | `docker compose up` doğrulaması (WP-00 kabul kriteri) yapılamadı | Docker Desktop başlatılmalı |
| E3 | Referans depoda **3 bozuk YAML** dosyası | Bu dosyalar platformda salt-okunur görünür | Bilinçli kabul; `KNOWN_BROKEN` listesinde. Düzeltme ayrı bir PR'a konu olabilir |

## Riskler

| Risk | Etki | Azaltım |
|---|---|---|
| Kayıpsız round-trip beklenenden zor | MVP temeli çöker | ~~WP-10 **ilk** yapılır~~ **ÇÖZÜLDÜ (2026-09-30)** — cerrahi metin yamasıyla 477/477 birebir, [ADR-0007](adr/ADR-0007-surgical-text-patching.md) |
| Süre kısıtı | Kapsam sarkar | Kapsam Faz 0-6 ile kilitli; WP-80 ve WP-81 bilinçli olarak MVP dışı. Her hafta sonunda çalışan demo |
| ADO Server API uyumsuzluğu | Yazma/tetikleme çalışmaz | WP-04 ile gün 1'de tespit; istemci sürüm-toleranslı |
| PVC RWO çoklu replika | Dağıtım tıkanır | `deployment.mode: simple` ile tek replika; tek yazar kuralı uygulama düzeyinde |
| `pbList` kısıtı | Yeni playbook çalıştırılamaz | WP-24 aynı PR'da günceller; uzun vade WP-81 |
| Ağ erişimi varsayımları | Entegrasyon durur | WP-04 gün 1 doğrulaması |
| Şema çıkarımı düşük doğruluk | Formlar hatalı | Güven skoru + yönetici geçersiz kılma ekranı |
| Self-servis kullanıcılar prod'u bozar | Operasyonel risk | `main`'e yazma yok + RBAC + dört göz + ön kontrol özeti + denetim izi |

---

## Not Düşülenler

> Geliştirme sırasında fark edilen, kapsam dışı olduğu için yapılmayan işler buraya yazılır.
> Bir iş paketinin kapsamını genişletmek yerine buraya not düşülür.

| Tarih | Not | Önerilen faz |
|---|---|---|
| 2026-09-30 | Referans depodaki 3 bozuk YAML dosyası düzeltilebilir (`prod-dmz.yml`, `test-dmz.yml`, `install_FileBeat.yml`). Kapsam dışı: referans depo salt-okunur. | WP-86 (depo sağlık panosu) |
| 2026-09-30 | Karma satır sonu (`\n` + `\r\n`) içeren dosya tespit edilirse uyarı üretilmeli. Şu an baskın stil kullanılıyor; referans depoda karma dosya yok. | WP-15 (doğrulayıcılar) |
| 2026-09-30 | `playbooks/altortam/update_netcore_boa/install_boa_webapi.yml` dosyasının `roles:` listesinde **2 adet görev** var (`uri:` modülü). Geçerli Ansible değil; çalıştırılırsa *"role definitions must contain a role name"* hatası verir. IR bunları bozmadan `RAW` olarak koruyor ve sebebini açıklıyor. | WP-15 (doğrulayıcılar) — yeni kural: `roles:` altında görev |
