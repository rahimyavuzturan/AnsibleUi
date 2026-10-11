# Katkı Rehberi

Bu depo **iş paketi (WP)** bazında geliştirilir. Her WP'nin girdisi, çıktısı ve kabul kriteri
[docs/13-roadmap-wbs.md](docs/13-roadmap-wbs.md) dosyasında tanımlıdır.

Bağlayıcı kurallar için önce [AGENTS.md](AGENTS.md) dosyasını okuyun.

## Geliştirme Ortamı

Gereksinimler: Python 3.12+, Node.js 20+, Docker Desktop, Git.

```powershell
# Depoyu hazırla
Copy-Item .env.example .env

# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Frontend
cd ..\frontend
npm install

# Referans Ansible deposu (test fixture'ı olarak gerekir)
# ../Ansible.appAdminConfig konumunda bulunmalıdır.
```

Referans depo yoksa golden testler otomatik olarak atlanır (skip), fakat
`app/ansible/` üzerinde çalışırken bu testlerin çalışması **zorunludur**.

## Bir İş Paketini Tamamlama

1. **Oku** — WBS'ten WP tanımını, ilgili `docs/` dosyasını ve alan kuralını
   ([.github/instructions/](.github/instructions/)).
2. **Doğrula** — Bağımlı WP'ler tamamlanmış mı?
3. **Yaz** — Kod ve testleri birlikte. Kapsam dışına çıkma.
4. **Kontrol et** — Aşağıdaki kalite kapısını geçir.
5. **İşaretle** — WBS'te WP durumunu güncelle.

## Kalite Kapısı

Bir değişiklik ancak aşağıdakilerin tamamı yeşilse tamamlanmış sayılır:

```powershell
# Backend
cd backend
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest

# Frontend
cd ..\frontend
npm run lint
npm run typecheck
npm run test
```

`app/ansible/` altında değişiklik yaptıysanız golden testin gerçekten **çalıştığını**
(atlanmadığını) doğrulayın:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/golden -v
```

## Commit Biçimi

Conventional Commits, kapsam WP numarasını içerir:

```
feat(ansible): WP-10 round-trip parser ekle
fix(editor): WP-43 node sirasi bozuldugunda uyari gosterilmiyordu
```

Commit mesajı ve kod yorumları İngilizce; dokümanlar ve kullanıcıya görünen metinler Türkçe.

## Branch

```
ansibleui/<kullanici>/<wp-no>-<kisa-aciklama>
ornek: ansibleui/trahim/wp10-roundtrip-parser
```

`main` branch'ine doğrudan commit atılmaz.

## Yeni Bağımlılık Ekleme

1. [docs/02-tech-stack.md](docs/02-tech-stack.md) dosyasında zaten karar verilmiş mi bak.
2. Verilmemişse bir ADR yaz ([docs/adr/](docs/adr/)), alternatifleri ve gerekçeyi belirt.
3. `pyproject.toml` / `package.json` dosyasına ekle ve sürümü sabitle.
4. `pip-audit` / `npm audit` çalıştır.

## Doküman Güncelleme

Kod ile doküman birlikte değişir. Şu durumlarda doküman güncellemesi **zorunludur**:

| Değişiklik | Güncellenecek doküman |
|---|---|
| Yeni endpoint | `docs/09-api-contract.md` |
| DB şeması | `docs/03-domain-model.md` |
| IR node tipi | `docs/04-ansible-ir-spec.md` |
| Yeni ortam değişkeni | `.env.example` + `docs/11-deployment-rancher.md` |
| Mimari karar | `docs/adr/ADR-XXXX-*.md` |
| WP tamamlandı | `docs/13-roadmap-wbs.md` |

## Yardım

- Terim belirsizliği: [docs/15-glossary.md](docs/15-glossary.md)
- Mimari soru: [docs/01-architecture.md](docs/01-architecture.md) ve [docs/adr/](docs/adr/)
- "Bunu neden böyle yapıyoruz?": ilgili ADR'ye bakın; yoksa yazın.
