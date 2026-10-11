---
description: "Use when editing Dockerfiles, Helm charts, Kubernetes manifests, docker-compose or Rancher deployment configuration. Covers PVC single-writer rule, security context, probes and secret handling."
applyTo: "deploy/**,**/Dockerfile,docker-compose.yml,**/*.tpl"
---

# Altyapı ve Kubernetes Kuralları

> Ayrıntı: [docs/11-deployment-rancher.md](../../docs/11-deployment-rancher.md)

## PVC Tek Yazar Kuralı

Git çalışma kopyası `ReadWriteOnce` bir PVC üzerindedir. Aynı anda **yalnızca bir
pod** bu birime yazar.

- Varsayılan `deployment.mode: simple` — api ve worker tek pod, tek düğüm.
- `deployment.mode: scaled` seçilirse api çoğaltılabilir ama **yalnızca worker**
  PVC'yi bağlar; api git'e dolaylı erişir.
- Çoğaltma sayısını artıran bir değişiklik bu kuralı açıkça ele almadan birleştirilmez.

## Konteyner Kuralları

1. **Çok aşamalı derleme**; son imajda derleme araçları bulunmaz.
2. **Root olmayan kullanıcı**: `runAsNonRoot: true`, `runAsUser: 10001`.
3. `readOnlyRootFilesystem: true`; yazılabilir yollar `emptyDir` veya PVC.
4. `allowPrivilegeEscalation: false`, tüm `capabilities` düşürülür.
5. Taban imajlar sabit etiket + digest ile; `latest` yasak.
6. İmajlar Harbor'a yüklenir; dış registry'den doğrudan çekme yok.

## Yapılandırma ve Sırlar

| Tür | Yer |
|---|---|
| Sır olmayan ayar | ConfigMap → `ANSIBLEUI_*` ortam değişkenleri |
| PAT, JWT anahtarı, DB parolası | Kubernetes Secret |
| CA bundle | ConfigMap, dosya olarak bağlanır |

- Sır değerleri `values.yaml` içine yazılmaz; `existingSecret` ile referans verilir.
- Helm şablonlarında sır değerini log'layan veya annotation'a koyan kod yok.

## Sağlık Kontrolleri

| Prob | Uç | Anlamı |
|---|---|---|
| `startupProbe` | `/healthz` | İlk açılış, migrasyon sonrası |
| `readinessProbe` | `/readyz` | DB ve depo erişilebilir |
| `livenessProbe` | `/healthz` | Süreç canlı |

`readyz` dış bağımlılıkları (Azure DevOps) **zorunlu** görmez; erişilemezse uygulama
`degraded` olur ama trafiği reddetmez.

## Kaynaklar

Her konteynerde `requests` ve `limits` tanımlı. Başlangıç değerleri
[docs/11](../../docs/11-deployment-rancher.md) içindedir; değiştirilirse orası da güncellenir.

## Veritabanı Migrasyonu

Helm `pre-upgrade` hook'u ile ayrı bir Job. Uygulama konteyneri başlangıçta
`alembic upgrade head` **çalıştırmaz** (çoklu pod yarışını önlemek için).

## docker-compose (yalnızca yerel geliştirme)

- Üretim yapılandırmasıyla karıştırılmaz.
- Varsayılan parolalar yalnızca yereldir ve `.env.example` içinde açıkça belirtilir.

## Bitti Tanımı

- [ ] `helm lint` ve `helm template` temiz
- [ ] İmaj root olmayan kullanıcıyla çalışıyor
- [ ] Yeni ayar `values.yaml`, `.env.example` ve [docs/11](../../docs/11-deployment-rancher.md) içinde
- [ ] PVC bağlayan pod sayısı değişmediyse doğrulandı
- [ ] Sır değeri hiçbir şablonda düz metin değil
