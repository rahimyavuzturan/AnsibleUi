# AnsibleUI

Mevcut `Ansible.appAdminConfig` Ansible deposunun üzerine oturan, görsel bir otomasyon platformu.

Ansible'ı bilmeyen bir ekip üyesinin de mevcut playbook'ları güvenle görüntüleyip
düzenleyebilmesini, her değişikliğin izlenebilir bir Pull Request'e dönüşmesini ve
çalıştırmanın mevcut Azure Pipeline üzerinden yapılmasını hedefler.

## Temel İlke

> **YAML tek doğruluk kaynağıdır (source of truth). Arayüz yalnızca bir görünümdür.**

Arayüzün görsel olarak temsil edemediği hiçbir yapı (gömülü PowerShell, karmaşık Jinja,
`set_fact` dallanmaları) bozulmaz; "ham YAML" kartı olarak aynen korunur.
Bir dosyayı açıp hiçbir değişiklik yapmadan kaydetmek, dosyayı **byte düzeyinde**
değiştirmemelidir. Bu kural `backend/tests/test_roundtrip_golden.py` ile sürekli doğrulanır.

## Ne Yapar

| Yetenek | Açıklama |
|---|---|
| Katalog | 65 rol, ~120 playbook ve envanter gruplarını aranabilir hale getirir |
| Görsel düzenleyici | Rolleri sürükle-bırak ile sırala, parametrelerini formla doldur |
| Bağımlılık grafı | Sertifika → binding gibi **örtük** `register` zincirlerini görünür kılar |
| Doğrulama | Dosyalar arası tutarsızlıkları (ör. eksik klasör tanımı) çalıştırmadan önce yakalar |
| Yayınlama | Değişikliği `ansibleui/*` branch'ine yazar ve Azure DevOps'ta PR açar |
| Çalıştırma | Mevcut Azure Pipeline'ı tetikler, canlı log ve task durumlarını gösterir |

## Ne Yapmaz

- Ansible'ı kendi içinde çalıştırmaz (kendi runner'ı yoktur).
- Hedef Windows sunuculara doğrudan bağlanmaz.
- Vault **değerlerini** okumaz, göstermez, saklamaz (yalnızca değişken adlarını listeler).
- `main` branch'ine doğrudan commit atmaz.
- Referans alınan `Ansible.appAdminConfig` deposunu değiştirmez.

## Hızlı Başlangıç

Gereksinimler: Docker Desktop, Node.js 20+, Python 3.12+.

```powershell
# 1. Ortam değişkenlerini hazırla
Copy-Item .env.example .env

# 2. Tüm servisleri ayağa kaldır (api + web + postgres)
docker compose up --build

# 3. Tarayıcıda aç
#    Arayüz     -> http://localhost:5173
#    API        -> http://localhost:8000
#    API dokümanı -> http://localhost:8000/docs
```

Docker olmadan geliştirme için [docs/01-architecture.md](docs/01-architecture.md) dosyasındaki
"Yerel Geliştirme" bölümüne bakın.

## Depo Yapısı

```
ansible-ui/
├── backend/          FastAPI uygulaması (Python 3.12)
│   └── app/
│       ├── ansible/  ★ Ansible Intelligence Core — parser, IR, şema çıkarımı, graf
│       ├── api/      HTTP router'ları (ince katman)
│       ├── services/ İş mantığı
│       ├── gitops/   Git işlemleri (GitPython)
│       ├── ado/      Azure DevOps Server REST istemcisi
│       ├── db/       SQLAlchemy modelleri
│       ├── auth/     Kimlik doğrulama sağlayıcıları
│       └── core/     Yapılandırma, log, hata tipleri
├── frontend/         React 18 + TypeScript + Vite
├── deploy/           Helm chart ve Kubernetes manifestleri
├── docs/             Tasarım dokümanları ve ADR'ler
└── .github/          Agent kuralları ve CI tanımları
```

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [docs/00-overview.md](docs/00-overview.md) | Problem, amaç, başarı kriterleri |
| [docs/01-architecture.md](docs/01-architecture.md) | Bileşenler, veri akışı, yerel geliştirme |
| [docs/02-tech-stack.md](docs/02-tech-stack.md) | Teknoloji seçimleri ve gerekçeleri |
| [docs/04-ansible-ir-spec.md](docs/04-ansible-ir-spec.md) | ★ Kayıpsız gidiş-dönüş sözleşmesi |
| [docs/08-security-and-rbac.md](docs/08-security-and-rbac.md) | Tehdit modeli ve yetkilendirme |
| [docs/13-roadmap-wbs.md](docs/13-roadmap-wbs.md) | Faz planı ve iş kırılımı |
| [docs/15-glossary.md](docs/15-glossary.md) | Terim sözlüğü |

Tüm liste için [docs/](docs/) klasörüne bakın.

## Katkı

Bu depoda çalışan her geliştirici ve yapay zekâ agent'ı için bağlayıcı kurallar
[AGENTS.md](AGENTS.md) dosyasındadır. Alan bazlı detaylı kurallar
[.github/instructions/](.github/instructions/) altındadır ve ilgili dosyalar düzenlenirken
otomatik yüklenir. Katkı süreci için [CONTRIBUTING.md](CONTRIBUTING.md).

## Durum

Faz 0 (Temel) — geliştirme aşamasında. Yol haritası: [docs/13-roadmap-wbs.md](docs/13-roadmap-wbs.md).
