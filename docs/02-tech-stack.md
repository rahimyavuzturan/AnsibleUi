# 02 — Teknoloji Yığını

Her seçim için: **ne**, **neden**, **alternatif neden seçilmedi**.
Bu dokümanda kararı verilmemiş bir bağımlılık eklenecekse önce bir ADR yazılır.

## Backend

| Alan | Seçim | Gerekçe | Değerlendirilen alternatif |
|---|---|---|---|
| Dil | **Python 3.12** | Ansible'ın kendi dili; Jinja2 ve YAML ekosistemi birinci sınıf. Ekip Ansible bağlamında Python'a zaten aşina. | .NET/Java: YAML round-trip ve Jinja AST analizi için olgun kütüphane yok |
| Web framework | **FastAPI** | Async, Pydantic ile otomatik doğrulama, OpenAPI şeması bedava, WebSocket yerleşik | Django: ORM-ağır, bu projede REST+WS yeterli. Flask: async ve şema desteği zayıf |
| **YAML** | **ruamel.yaml** (round-trip) | **Projenin temel gereksinimi.** Yorumları, tırnak stilini, anahtar sırasını, boş satırları korur | PyYAML: yorumları ve biçimi **yok eder** — G5 hedefini imkânsız kılar. Tartışmaya kapalı: [ADR-0002](adr/ADR-0002-ruamel-roundtrip.md) |
| Jinja analizi | **jinja2** `Environment.parse()` + AST | Değişken referanslarını güvenilir çıkarır; `{{ x \| default(y) }}` gibi yapıları doğru yorumlar | Regex: iç içe filtreler ve `{% if %}` bloklarında sessizce yanlış sonuç verir |
| Doğrulama | **Pydantic v2** | IR node'ları ve API şemaları için tek model dili; Rust çekirdeği ile hızlı | dataclasses + manuel doğrulama: fazla el emeği |
| ORM | **SQLAlchemy 2.0** (async) + **Alembic** | Olgun, tip dostu 2.0 API'si, şema göçü standart | Tortoise/Piccolo: ekosistem ve migration olgunluğu daha az |
| Git | **GitPython** | Nesne API'si; shell string'i kurulmadığı için komut enjeksiyonu yüzeyi yok | `subprocess` + git CLI: enjeksiyon riski, hata ayrıştırması kırılgan |
| HTTP istemcisi | **httpx** | Async, timeout ve retry kontrolü net, özel CA bundle desteği | requests: async değil; aiohttp: API'si daha zahmetli |
| Kimlik | **passlib[argon2]** + **python-jose** | Argon2id modern parola özeti standardı | bcrypt: kabul edilebilir ama argon2id tercih edilir |
| Log | **structlog** | JSON yapısal log; secret maskeleme işlemcisi eklenebilir | logging: yapısal log için fazla el emeği |
| Zamanlama | **APScheduler** (worker içinde) | Tek pod içinde periyodik iş için yeterli; ek altyapı yok | **Celery + Redis: MVP'de bilinçli olarak YOK.** İki ek bileşen, yük bunu gerektirmiyor |
| Test | **pytest** + pytest-asyncio + **syrupy** | Golden/snapshot testler syrupy ile okunaklı | unittest: fixture ergonomisi zayıf |
| Lint | **ruff** (+ format) + **mypy --strict** | Tek araçta lint+format, çok hızlı | black+isort+flake8: üç araç, daha yavaş |

## Frontend

| Alan | Seçim | Gerekçe | Değerlendirilen alternatif |
|---|---|---|---|
| Framework | **React 18 + TypeScript** (strict) | Ekip tercihi; canvas ve form ekosistemi en zengin | Vue/Svelte: React Flow dengi olgunlukta canvas kütüphanesi yok |
| Derleme | **Vite** | Hızlı HMR, basit yapılandırma | Next.js: SSR'a ihtiyaç yok; SPA + ayrı API daha uygun |
| **Canvas** | **@xyflow/react** (React Flow v12) | Node/edge modeli, özel node, kesikli kenar, minimap, otomatik yerleşim — hepsi hazır | Konva/D3: graf semantiği sıfırdan yazılır. JointJS: ticari lisans |
| UI kit | **Tailwind CSS + shadcn/ui** (Radix) | Erişilebilir primitifler, kopyalanabilir bileşenler, hızlı ve tutarlı görsel dil | MUI: tema özelleştirmesi ağır. Ant Design: görsel dili kurumsal kimliğe uzak |
| Sunucu durumu | **TanStack Query v5** | Cache, invalidation, iyimser güncelleme, WebSocket ile senkron | Redux Toolkit Query: Redux bağımlılığı gereksiz |
| İstemci durumu | **Zustand** | Canvas durumu için hafif, boilerplate'siz | Redux: bu ölçek için fazla tören |
| Form | **react-hook-form + Zod** | Çalışma zamanında üretilen şemadan dinamik form kurmaya elverişli | Formik: performans ve dinamik şema desteği zayıf |
| Kod editörü | **Monaco** (`@monaco-editor/react`) | Ham YAML node'ları ve diff görünümü; VS Code ile aynı deneyim | CodeMirror 6: iyi, fakat Monaco'nun DiffEditor'ü hazır geliyor |
| Diff | **Monaco DiffEditor** | Yayınlama önizlemesi için ek bağımlılık gerekmiyor | react-diff-viewer: ayrı bağımlılık, daha az yetenekli |
| Test | **Vitest** + Testing Library + **Playwright** | Vite ile aynı dönüşüm hattı; Playwright çoklu tarayıcı E2E | Jest: Vite ile ek yapılandırma gerektirir |

## Veri ve Altyapı

| Alan | Seçim | Gerekçe |
|---|---|---|
| Veritabanı | **PostgreSQL 16** | Kurumsal standart; JSONB ile IR parçacıklarını saklamaya elverişli. Küçük tutulur (<1 GB) — build log'ları DB'ye yazılmaz |
| Depolama | **PVC** (`ReadWriteOnce`, ~5 GB) | Git çalışma kopyası. Tek yazar kuralı worker ile sağlanır |
| Container | Çok aşamalı **Dockerfile**, non-root, slim taban | Saldırı yüzeyini ve imaj boyutunu küçültür |
| Registry | **Harbor** (kurumsal) | Mevcut altyapı |
| Orkestrasyon | **Rancher / Kubernetes** + **Helm** | Ekibin mevcut dağıtım yöntemi |
| Gözlemlenebilirlik | `prometheus-fastapi-instrumentator` | Prometheus ile doğrudan uyumlu |
| Yerel geliştirme | **docker-compose** | Tek komutla tam yığın |

## Faz 7 — Yapay Zekâ

| Alan | Seçim | Gerekçe |
|---|---|---|
| Model | Kurum içi **Qwen** (büyük varyant) | Veri kurum dışına çıkmaz; kurumsal kısıtlara uygun |
| Protokol | OpenAI uyumlu `/v1/chat/completions` | Qwen sunucuları bu arayüzü sağlar; sağlayıcı değişse de kod aynı kalır |
| İstemci | **httpx** (mevcut) | Ek bağımlılık yok |
| Soyutlama | `app/ai/provider.py` arayüzü | Model/sağlayıcı değişimi tek dosyada kalır |

Vektör veritabanı **kullanılmaz**: bağlam, rol şemaları ve benzer playbook örneklerinden
deterministik olarak üretilir. Depo ölçeği (65 rol, 120 playbook) bunu mümkün kılar.

## Bilinçli Olarak Kullanılmayanlar

| Teknoloji | Neden kullanılmıyor |
|---|---|
| Celery / Redis | Tek worker + APScheduler yeterli. İki ek bileşen, ek hata yüzeyi |
| Vektör veritabanı | Depo küçük; deterministik bağlam üretimi daha doğru sonuç verir |
| GraphQL | REST + OpenAPI ekip için daha tanıdık; şema üretimi bedava |
| Kubernetes Operator | Aşırı mühendislik; Helm chart yeterli |
| Mikroservis mimarisi | Üç servis (web/api/worker) zaten yeterli ayrışma sağlıyor |
| Server-side rendering | SPA + ayrı API, iç araç için uygun; SEO gereksinimi yok |
| Ansible Runner / AWX | Kendi runner'ı hedef dışı; AWX mevcut pipeline modelini değiştirmeyi gerektirir |

## Sürüm Politikası

- Tüm bağımlılıklar üst sınırla sabitlenir (`~=` veya `^`).
- Güvenlik denetimi CI'da bloklayıcı: `pip-audit`, `npm audit --audit-level=high`.
- Ana sürüm (major) yükseltmeleri ayrı PR'da, ayrı test koşumuyla yapılır.
