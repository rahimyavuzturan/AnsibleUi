# 01 — Mimari

## 1. Üst Düzey Görünüm

```
┌──────────────────── Rancher namespace: ansible-ui ─────────────────────┐
│                                                                         │
│   Ingress (kurumsal TLS)                                                │
│       │                                                                 │
│       ├─► ansibleui-web        nginx + React SPA (statik)               │
│       │                                                                 │
│       ├─► ansibleui-api        FastAPI · REST + WebSocket               │
│       │        │                                                        │
│       │        ├──► PostgreSQL     index, taslak, denetim, RBAC         │
│       │        └──► PVC /data/repo  (salt-okunur bağlama)               │
│       │                                                                 │
│       └─   ansibleui-worker    APScheduler · tek replika                │
│                │                                                        │
│                ├──► PVC /data/repo  (okuma-yazma — tek yazar)           │
│                └──► PostgreSQL                                          │
└─────────────────────────────────────────────────────────────────────────┘
          │                    │                      │
          ▼                    ▼                      ▼
   ktdevops (ADO Server)   Qwen LLM (Faz 7)    Hedef Windows sunucular
   git + REST API                              ERİŞİM YOK (bilinçli)
```

### Servisler

| Servis | Sorumluluk | Replika | Durum |
|---|---|---|---|
| `ansibleui-web` | React SPA'yı statik sunar, `/api` ve `/ws` isteklerini API'ye yönlendirir | 2 | Durumsuz |
| `ansibleui-api` | REST + WebSocket, yetkilendirme, okuma (DB index'inden), taslak yönetimi | 2 | Durumsuz |
| `ansibleui-worker` | Git fetch, indeksleme, PR açma, build log toplama | **1** | PVC sahibi |

### Neden ayrı worker?

PVC `ReadWriteOnce` modundadır ve git çalışma kopyasına **aynı anda tek yazar** olmalıdır.
İki API replikası aynı klonda `git checkout` yaparsa çalışma kopyası bozulur.

Çözüm: git çalışma kopyasına **yalnızca worker yazar**. API replikaları dosya içeriğini
PVC'den salt-okunur okur, yapısal veriyi ise PostgreSQL index'inden alır.
Yazma işlemleri (branch+commit+push+PR) API tarafından bir **iş kaydı** olarak kuyruğa
alınır ve worker tarafından işlenir.

> MVP basitleştirmesi: API tek replika ile de başlatılabilir. Helm değeri
> `api.replicaCount` ile kontrol edilir. Tasarım her iki durumda da doğrudur.

Ayrıntı: [ADR-0006](adr/ADR-0006-postgres-small-footprint.md) ·
[11-deployment-rancher.md](11-deployment-rancher.md)

## 2. Backend Katmanları

```
backend/app/
├── api/           FastAPI router'ları — ince, iş mantığı yok
├── services/      İş mantığı ve orkestrasyon
├── ansible/       ★ Ansible Intelligence Core — SAF (yan etkisiz)
│   ├── parser.py        ruamel.yaml round-trip okuma
│   ├── ir.py            IR node tipleri (Pydantic)
│   ├── serializer.py    IR → YAML (dokunulmayan alt ağaç aynen korunur)
│   ├── inventory.py     INI envanter ayrıştırıcı
│   ├── schema_infer.py  Rol parametre şeması çıkarımı
│   ├── validators.py    Dosyalar arası tutarlılık kuralları
│   └── graph.py         Örtük/açık bağımlılık kenarları
├── gitops/        Git işlemleri (GitPython) — `git/` DEĞİL, isim çakışması olur
├── ado/           Azure DevOps Server REST istemcisi (httpx)
├── db/            SQLAlchemy 2.0 modelleri + repository'ler
├── auth/          AuthProvider arayüzü (Local → sonra LDAP)
└── core/          config, logging, errors, paths
```

### Bağımlılık Yönü

```
api  →  services  →  {ansible, gitops, ado, db, auth}  →  core
```

Ters yönde import **yasaktır** ve `tests/unit/test_layering.py` ile denetlenir.

### `app/ansible/` Saflık Kuralı

Bu paket **yan etkisizdir**: ağ çağrısı, veritabanı erişimi, git komutu, dosya yazma
içermez. Dosya okuma yalnızca çağıran tarafından verilen içerik üzerinden yapılır.

Gerekçe:
- Golden testler hızlı ve deterministik çalışır (milisaniye, ağ yok).
- Parser mantığı, çalıştırma bağlamından bağımsız olarak test edilebilir.
- Aynı mantık ileride bir CLI aracında veya pre-commit hook'unda yeniden kullanılabilir.

## 3. Veri Akışları

### 3.1 Okuma — Azure DevOps → Arayüz

```
worker ──(60 sn veya webhook)──► git fetch origin main
   │
   ├─ Yeni commit var mı?  Hayır → bekle
   │                       Evet ↓
   ├─ git diff ile değişen dosyaları bul
   ├─ SADECE değişen dosyaları parse et (artımlı indeksleme)
   ├─ PostgreSQL index'ini güncelle
   └─ WebSocket ile açık istemcilere "repo güncellendi" bildir
                                  │
                        api ──────┴──► tarayıcı (TanStack Query cache invalidation)
```

Webhook (ADO service hook) varsa gecikme saniyelere iner; yoksa yoklama (polling)
yedek mekanizma olarak çalışır. İkisi birlikte kullanılır.

### 3.2 Yazma — Arayüz → Azure DevOps

```
Kullanıcı düzenler
   └─► POST /api/drafts            taslak DB'ye yazılır (base_commit_sha ile)
                                   ── henüz hiçbir şey push edilmedi ──
Kullanıcı "Yayınla" der
   └─► POST /api/publish/preview   üretilecek YAML + unified diff döner
   └─► kullanıcı diff'i onaylar
   └─► POST /api/publish
          └─ worker işi:
             1. base_commit_sha hâlâ güncel mi? (değilse çakışma ekranı)
             2. git checkout -b ansibleui/<kullanici>/<slug>
             3. dosyaları yaz (ruamel round-trip serializer)
             4. gerekiyorsa pbList listesini güncelle
             5. commit (trailer: AnsibleUI-User, AnsibleUI-Draft-Id)
             6. git push origin <branch>
             7. ADO REST: POST .../pullrequests
             8. PR URL'i taslağa iliştirilir, denetim kaydı yazılır
```

**Merge asla platform tarafından yapılmaz.** İnsan onayı Azure DevOps'ta verilir.

Ayrıntı: [06-git-sync-and-ado.md](06-git-sync-and-ado.md)

### 3.3 Çalıştırma

```
Kullanıcı: playbook + ortam seçer
   └─► POST /api/runs
          ├─ Ön kontroller (hepsi bloklayıcı):
          │    a. Playbook origin/main'de var mı?
          │    b. İlgili ortamın pbList listesinde var mı?
          │    c. Kullanıcının o ortam için RBAC izni var mı?
          │    d. prod / dmz_prod ise: Approver onayı alınmış mı?
          ├─ ADO: POST /_apis/build/builds  { definition, parameters: {pbList} }
          └─ run kaydı oluşturulur (kim, ne zaman, hangi commit, build id)

worker ──(5 sn)──► GET /_apis/build/builds/{id}/timeline
                   GET /_apis/build/builds/{id}/logs/{logId}  (artımlı)
                   └─ ansible -v çıktısını ayrıştır
                      └─ task × host durum matrisi
                         └─ WebSocket /ws/runs/{id} ──► tarayıcı
```

Ayrıntı: [07-execution-and-logs.md](07-execution-and-logs.md)

## 4. Neden Kendi Runner'ı Yok

Platform Ansible'ı kendisi çalıştırmaz; mevcut Azure Pipeline'ı tetikler.

| Kazanım | Açıklama |
|---|---|
| Güvenlik modeli korunur | Vault parolası secure file olarak yalnızca agent'ta; platform hiç görmez |
| Ağ topolojisi korunur | DMZ ve prod ağlarına erişim yalnızca ilgili agent pool'larında |
| Denetim tekliği | Tüm çalıştırmalar ADO build geçmişinde; ikinci bir kaynak oluşmaz |
| Sorumluluk netliği | Platform devre dışı kalsa bile pipeline'lar çalışmaya devam eder |
| Hız | Kendi runner'ı yazmak WinRM, vault, ağ izolasyonu gerektirir — MVP'ye sığmaz |

Bedeli: canlı log gerçek zamanlı değil (~5 sn gecikme) ve `pbList` kısıtı.
Her ikisi de kabul edildi. Gerekçe: [ADR-0003](adr/ADR-0003-pipeline-trigger-not-own-runner.md)

## 5. Frontend Yapısı

```
frontend/src/
├── app/           Uygulama kabuğu, router, sağlayıcılar
├── features/      Özellik bazlı dikey dilimler
│   ├── catalog/     Rol ve playbook kataloğu
│   ├── inventory/   Envanter gezgini
│   ├── editor/      ★ React Flow canvas + dinamik form + ham YAML
│   ├── publish/     Diff önizleme ve PR açma
│   ├── runs/        Çalıştırma konsolu ve geçmiş
│   └── admin/       Kullanıcılar, roller, şema geçersiz kılmaları
├── components/    Paylaşılan sunum bileşenleri (iş mantığı yok)
├── lib/           API istemcisi, yardımcılar, tipler
└── styles/        Tailwind katmanları ve tema
```

Kural: `features/*` birbirini import **etmez**. Paylaşım `components/` veya `lib/`
üzerinden yapılır. Bu, özelliklerin ayrı agent'lar tarafından paralel geliştirilmesini sağlar.

## 6. Durum Yönetimi

| Durum türü | Araç | Örnek |
|---|---|---|
| Sunucu durumu | TanStack Query | Rol listesi, playbook içeriği, çalıştırma geçmişi |
| Düzenleyici durumu | Zustand | Canvas node konumları, seçili node, kirli (dirty) bayrağı |
| Form durumu | react-hook-form + Zod | Rol parametre formları |
| URL durumu | React Router | Açık dosya, seçili node, arama sorgusu |

`useEffect` ile veri çekme **yapılmaz**. Tüm sunucu etkileşimi TanStack Query üzerinden.

## 7. Yerel Geliştirme

### Docker ile (önerilen)

```powershell
Copy-Item .env.example .env
docker compose up --build
# Arayüz http://localhost:5173 · API http://localhost:8000 · Dokümantasyon /docs
```

### Docker olmadan

```powershell
# 1. Veritabanı
docker compose up -d postgres

# 2. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 3. Frontend (ayrı terminal)
cd frontend
npm install
npm run dev
```

Referans Ansible deposu `../Ansible.appAdminConfig` konumunda bulunmalıdır; golden testler
ve yerel indeksleme bunu kullanır. Yoksa golden testler atlanır.

## 8. Gözlemlenebilirlik

| Uç nokta | Amaç |
|---|---|
| `/healthz` | Liveness — süreç ayakta mı |
| `/readyz` | Readiness — DB ve PVC erişilebilir mi |
| `/metrics` | Prometheus — istek süresi, hata oranı, indeksleme süresi, kuyruk derinliği |

Log'lar `structlog` ile JSON olarak `stdout`'a yazılır. Her istek `request_id` taşır;
bu kimlik API yanıtında da döner ve hata bildirimini log'a bağlamayı sağlar.
Secret maskeleme filtresi tüm log işlemcilerine bağlıdır.

## 9. Mimari Kısıtlar Özeti

| Kısıt | Kaynak | Sonuç |
|---|---|---|
| PVC `ReadWriteOnce` | Rancher | Git çalışma kopyasına tek yazar (worker) |
| Veritabanı küçük olmalı | Kurumsal politika | Build log'ları DB'de tutulmaz, ADO'da kalır |
| Pod'dan hedef sunuculara erişim yok | Ağ izolasyonu | Kendi runner'ı yok, pipeline tetiklenir |
| Azure DevOps **Server** (TFS) | Mevcut altyapı | `api-version` 6.0 varsayılır, sürüm-toleranslı istemci |
| İç sertifika otoritesi | Kurumsal PKI | CA bundle mount edilir, TLS doğrulama asla kapatılmaz |
| `pbList` elle yazılmış dropdown | Mevcut pipeline | Yeni playbook PR'ı aynı anda pbList'i günceller |
