# AGENTS.md — AnsibleUI Proje Kuralları

Bu dosya, bu depoda çalışan **her geliştirici ve her yapay zekâ agent'ı** için bağlayıcıdır.
Alan bazlı detaylı kurallar [.github/instructions/](.github/instructions/) altındadır ve
ilgili dosyalar düzenlenirken otomatik yüklenir.

---

## 1. Proje Nedir

AnsibleUI, `../Ansible.appAdminConfig` Ansible deposunun üzerine oturan bir web platformudur.
65 rol ve ~120 playbook'u keşfedilebilir kılar, playbook'ları görsel olarak düzenletir,
her değişikliği Azure DevOps Server'da bir **Pull Request**'e dönüştürür ve çalıştırmayı
**mevcut Azure Pipeline'ı tetikleyerek** yapar.

Ayrıntı: [docs/00-overview.md](docs/00-overview.md) · [docs/01-architecture.md](docs/01-architecture.md)

---

## 2. Değişmez Kurallar (ihlal = PR reddi)

Bu on kural tartışmaya açık değildir. Bir görev bunlardan birini ihlal etmeyi gerektiriyorsa,
görevi yapma — durumu bildir.

1. **Referans depo salt-okunurdur.** `Ansible.appAdminConfig/` klasörü asla değiştirilmez,
   yeniden düzenlenmez, dosya eklenmez. Yalnızca okunur ve test fixture'ı olarak kullanılır.

2. **YAML tek doğruluk kaynağıdır.** YAML yazarken **her zaman** `ruamel.yaml` round-trip modu
   kullanılır. `yaml.safe_dump`, `yaml.dump`, `json.dumps` ile YAML üretmek **yasaktır**.
   Gerekçe: [docs/adr/ADR-0002-ruamel-roundtrip.md](docs/adr/ADR-0002-ruamel-roundtrip.md)

3. **`main` branch'ine yazılmaz.** Tüm commit'ler `ansibleui/<kullanıcı>/<slug>` biçimindeki
   branch'lere gider. Kodda `main`'e push'u engelleyen koruma kaldırılamaz veya atlanamaz.

4. **Vault değerleri okunmaz.** Backend `/etc/ansible/vault/**` yolunu hiçbir koşulda açmaz.
   Yalnızca playbook'lardaki `{{ degisken_adi }}` referanslarından **değişken adları** türetilir.
   Secret değerleri log'a, DB'ye, API yanıtına veya hata mesajına asla yazılmaz.

5. **TLS doğrulaması kapatılmaz.** `verify=False`, `ssl._create_unverified_context`,
   `NODE_TLS_REJECT_UNAUTHORIZED=0` yasaktır. İç sertifikalar için CA bundle mount edilir.

6. **Sessiz hata yutulmaz.** `except: pass`, `except Exception: pass`, boş `catch {}` yasaktır.
   `# type: ignore` ve `@ts-ignore` yalnızca satır içi gerekçe yorumuyla kullanılır.

7. **Her iş paketi testiyle gelir.** `ruff`, `mypy --strict`, `pytest`, `eslint`, `tsc --noEmit`,
   `vitest` yeşil olmadan hiçbir iş "bitti" sayılmaz.

8. **Kapsam dışına çıkılmaz.** Sadece istenen iş paketi yapılır. Fark edilen ek ihtiyaçlar
   koda değil, [docs/13-roadmap-wbs.md](docs/13-roadmap-wbs.md) dosyasının "Not Düşülenler"
   bölümüne yazılır.

9. **Mimari karar alındıysa ADR yazılır.** Yeni bir kütüphane, protokol veya kalıcı desen
   seçildiyse [docs/adr/](docs/adr/) altına numaralı bir ADR eklenir.

10. **Dil ayrımı.** Kullanıcıya görünen tüm metinler (UI etiketleri, hata mesajları, doküman)
    **Türkçe**; kod, değişken, fonksiyon, dosya adı, commit mesajı, kod yorumu **İngilizce**.

---

## 3. Mimari Sınırlar

Katmanlar tek yönlü bağımlıdır. Ok yönünün tersine import **yapılmaz**:

```
api  →  services  →  {ansible, gitops, ado, db, auth}  →  core
```

| Katman | Sorumluluk | Yapamayacağı |
|---|---|---|
| `app/api/` | HTTP router, istek/yanıt şeması, yetki kontrolü çağrısı | İş mantığı içeremez, DB'ye doğrudan erişemez |
| `app/services/` | İş mantığı, orkestrasyon, yetki kararı | FastAPI tiplerini (`Request`, `Response`) import edemez |
| `app/ansible/` | Parse, IR, şema çıkarımı, graf, doğrulama | **Saf olmalı**: ağ, DB, git, dosya sistemi yazma yok |
| `app/gitops/` | Git işlemleri (GitPython) | `subprocess` ile git çağıramaz |
| `app/ado/` | Azure DevOps Server REST | İş mantığı içeremez |
| `app/db/` | SQLAlchemy modelleri, repository | İş kuralı içeremez |
| `app/core/` | Config, log, hata tipleri, yol güvenliği | Üst katmanlardan hiçbir şey import edemez |

> `app/ansible/` paketinin saflığı özellikle önemlidir: tüm parser/IR mantığı yan etkisiz
> olmalıdır ki golden testler hızlı ve deterministik çalışsın.

Not: Git paketi `app/gitops/` adını taşır (`app/git/` değil) — aksi hâlde `GitPython`
kütüphanesinin `git` modülüyle isim çakışması olur.

---

## 4. Komutlar

```powershell
# Tüm yığın (api + web + postgres)
docker compose up --build

# Backend — kurulum, test, kalite
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check . ; .\.venv\Scripts\python.exe -m mypy app

# Backend — geliştirme sunucusu
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev ; npm run test ; npm run lint ; npm run typecheck
```

---

## 5. Kod Standartları

**Python 3.12**
- `from __future__ import annotations` her modülün başında.
- Tam tip ipucu zorunlu (`mypy --strict` geçmeli). `Any` yalnızca gerekçeli.
- Public fonksiyon/sınıflarda Türkçe docstring; satır içi yorumlar İngilizce.
- Satır uzunluğu 100. Formatlama `ruff format`.
- Hatalar `app/core/errors.py` içindeki tip hiyerarşisinden fırlatılır, çıplak `Exception` değil.
- I/O `async def`, saf hesaplama `def`.

**TypeScript / React 18**
- `strict: true`. `any` yasak, bilinmeyen için `unknown` + daraltma.
- Fonksiyonel bileşen + hook. Sınıf bileşeni yok.
- Sunucu durumu TanStack Query, istemci durumu Zustand. `useEffect` ile veri çekme yok.
- `dangerouslySetInnerHTML` yasak.
- Dosya adları: bileşen `PascalCase.tsx`, diğerleri `kebab-case.ts`.

---

## 6. Test Kuralları

| Tür | Yer | Ne zaman |
|---|---|---|
| Golden (round-trip) | `backend/tests/golden/` | `app/ansible/` değiştiğinde **zorunlu** |
| Birim | `backend/tests/unit/`, `frontend/src/**/*.test.ts` | Her yeni fonksiyon/bileşen |
| Entegrasyon | `backend/tests/integration/` | DB, git veya ADO'ya dokunan her akış |
| E2E | `frontend/e2e/` | Kullanıcıya görünen her akış |

**Altın test kuralı:** `Ansible.appAdminConfig` altındaki her `.yml` dosyası parse edilip
yeniden serialize edildiğinde **byte düzeyinde aynı** olmalıdır. Bu test kırmızıysa
hiçbir şey merge edilmez. Ayrıntı: [docs/14-testing-strategy.md](docs/14-testing-strategy.md)

Dış sistemler (ADO, LDAP, LLM) testlerde **her zaman** sahte (fake) ile değiştirilir.
Gerçek ağ çağrısı yapan test yazılmaz.

---

## 7. Commit ve Branch

Conventional Commits, kapsam iş paketi numarasını içerir:

```
feat(ansible): WP-10 round-trip parser ekle
fix(editor): WP-43 node sirasi bozuldugunda uyari gosterilmiyordu
docs(adr): ADR-0004 PR tabanli yazma yolu
test(golden): WP-10 tum repo icin byte-identical dogrulamasi
```

Tipler: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `build`, `ci`.
Kapsamlar: `ansible`, `api`, `services`, `gitops`, `ado`, `db`, `auth`, `editor`, `catalog`,
`runs`, `ui`, `infra`, `adr`, `golden`.

---

## 8. Güvenlik

Her değişiklikte OWASP Top 10 gözetilir. Tam tehdit modeli:
[docs/08-security-and-rbac.md](docs/08-security-and-rbac.md)

Sık karşılaşılan üç tuzak:
- **Path traversal:** Depo içi dosya yolları `app/core/paths.py` içindeki doğrulayıcıdan
  geçmelidir. `..` reddedilir, allowlist dışı klasöre yazılmaz.
- **SSRF:** Giden HTTP isteklerinin base URL'i **yalnızca** ayarlardan gelir.
  Kullanıcı girdisinden URL oluşturulmaz.
- **Komut enjeksiyonu:** Git işlemleri GitPython API'si ile yapılır, shell string'i kurulmaz.

---

## 9. Çalışma Düzeni

Bu proje küçük agent'lar tarafından **iş paketi (WP) bazında** geliştirilir.
Bir göreve başlarken:

1. [docs/13-roadmap-wbs.md](docs/13-roadmap-wbs.md) dosyasından WP'nin girdi/çıktı/kabul
   kriterini oku.
2. İlgili alan kuralını [.github/instructions/](.github/instructions/) altından oku.
3. WP'nin bağımlı olduğu WP'lerin tamamlandığını doğrula.
4. Kodu ve testlerini birlikte yaz.
5. Kalite komutlarını çalıştır, hepsi yeşil olmalı.
6. WBS dosyasında WP'yi tamamlandı olarak işaretle.

---

## 10. Doküman Haritası

| Doküman | Ne zaman okunmalı |
|---|---|
| [docs/00-overview.md](docs/00-overview.md) | Projeye ilk bakış, amaç ve kapsam |
| [docs/01-architecture.md](docs/01-architecture.md) | Bileşen ve veri akışı gerektiğinde |
| [docs/02-tech-stack.md](docs/02-tech-stack.md) | Kütüphane seçimi gerektiğinde |
| [docs/03-domain-model.md](docs/03-domain-model.md) | DB veya kavram modeli işlerinde |
| [docs/04-ansible-ir-spec.md](docs/04-ansible-ir-spec.md) | ★ `app/ansible/` üzerinde çalışırken |
| [docs/05-role-schema-inference.md](docs/05-role-schema-inference.md) | Şema çıkarımı işlerinde |
| [docs/06-git-sync-and-ado.md](docs/06-git-sync-and-ado.md) | Git/PR/ADO işlerinde |
| [docs/07-execution-and-logs.md](docs/07-execution-and-logs.md) | Çalıştırma ve log işlerinde |
| [docs/08-security-and-rbac.md](docs/08-security-and-rbac.md) | Yetki, kimlik, güvenlik işlerinde |
| [docs/09-api-contract.md](docs/09-api-contract.md) | Yeni endpoint yazarken |
| [docs/10-ui-ux-spec.md](docs/10-ui-ux-spec.md) | Frontend işlerinde |
| [docs/11-deployment-rancher.md](docs/11-deployment-rancher.md) | Helm, K8s, Docker işlerinde |
| [docs/12-ai-assistant.md](docs/12-ai-assistant.md) | Faz 7 yapay zekâ işlerinde |
| [docs/13-roadmap-wbs.md](docs/13-roadmap-wbs.md) | **Her görev başlangıcında** |
| [docs/14-testing-strategy.md](docs/14-testing-strategy.md) | Test yazarken |
| [docs/15-glossary.md](docs/15-glossary.md) | Terim belirsizliğinde |
| [docs/demo-script.md](docs/demo-script.md) | Sunum/demo hazırlığında |
| [docs/adr/](docs/adr/) | Bir kararın *neden* böyle olduğunu ararken |

---

## 11. Alan Kuralları Haritası

Aşağıdaki dosyalar, kapsadıkları yol düzenlenirken otomatik olarak devreye girer.
Kendi alanının dışında bir dosyaya dokunuyorsan ilgili kuralı da oku.

| Kural dosyası | Kapsadığı yol |
|---|---|
| [security](.github/instructions/security.instructions.md) | Tüm dosyalar |
| [ansible-core](.github/instructions/ansible-core.instructions.md) ★ | `backend/app/ansible/**` |
| [backend-python](.github/instructions/backend-python.instructions.md) | `backend/**/*.py` |
| [api-contract](.github/instructions/api-contract.instructions.md) | `backend/app/api/**` |
| [database](.github/instructions/database.instructions.md) | `backend/app/db/**`, `backend/alembic/**` |
| [git-ado](.github/instructions/git-ado.instructions.md) | `backend/app/gitops/**`, `backend/app/ado/**` |
| [ai-assistant](.github/instructions/ai-assistant.instructions.md) | `backend/app/ai/**`, `frontend/src/features/ai/**` |
| [frontend-react](.github/instructions/frontend-react.instructions.md) | `frontend/**` |
| [canvas-editor](.github/instructions/canvas-editor.instructions.md) | `frontend/src/features/editor/**` |
| [testing](.github/instructions/testing.instructions.md) | Test dosyaları |
| [infra-k8s](.github/instructions/infra-k8s.instructions.md) | `deploy/**`, `Dockerfile`, compose |
| [docs](.github/instructions/docs.instructions.md) | `docs/**`, `*.md` |
