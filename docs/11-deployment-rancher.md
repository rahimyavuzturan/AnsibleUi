# 11 — Rancher / Kubernetes Dağıtımı

## 1. Genel Yapı

```
Namespace: ansible-ui
├── Ingress            ansibleui.kuveytturk.com.tr (kurumsal TLS)
├── Deployment  web     nginx + React SPA          replica: 2
├── Deployment  api     FastAPI                     replica: 2
├── Deployment  worker  APScheduler + git           replica: 1  ← tek yazar
├── StatefulSet postgres (veya harici yönetilen DB)
├── PVC         repo-data   5Gi   ReadWriteOnce
├── ConfigMap   ansibleui-config
├── Secret      ansibleui-secrets
├── Secret      ansibleui-ca      (iç CA bundle)
└── NetworkPolicy
```

## 2. PVC ve Tek Yazar Kuralı

PVC `ReadWriteOnce` modundadır. Git çalışma kopyasına aynı anda iki süreç yazarsa
(`git checkout`, `git fetch`) çalışma kopyası bozulur.

| Bileşen | PVC erişimi |
|---|---|
| `worker` | **ReadWrite** — git fetch, checkout, commit, push |
| `api` | **ReadOnly** — dosya içeriği okuma |
| `web` | Erişim yok |

RWO PVC'nin birden fazla pod'a bağlanabilmesi için tüm pod'lar **aynı node'da**
olmalıdır. Bu, pod affinity ile sağlanır:

```yaml
affinity:
  podAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app.kubernetes.io/component: worker
        topologyKey: kubernetes.io/hostname
```

**Alternatif (daha basit):** `api.replicaCount: 1` ve worker ile aynı pod'da
çalıştırmak. MVP için bu yeterlidir ve affinity karmaşıklığını ortadan kaldırır.
Helm değeri `deployment.mode: simple | scaled` ile seçilir.

Depolama sınıfı `ReadWriteMany` destekliyorsa (NFS, CephFS) bu kısıt kalkar;
yine de tek yazar kuralı **uygulama düzeyinde** korunur.

## 3. Helm Chart

```
deploy/helm/ansible-ui/
├── Chart.yaml
├── values.yaml                 # varsayılanlar
├── values-nonprod.yaml
├── values-prod.yaml
└── templates/
    ├── _helpers.tpl
    ├── configmap.yaml
    ├── secret.yaml              # yalnızca şablon; değerler dışarıdan
    ├── pvc.yaml
    ├── deployment-web.yaml
    ├── deployment-api.yaml
    ├── deployment-worker.yaml
    ├── service-web.yaml
    ├── service-api.yaml
    ├── ingress.yaml
    ├── networkpolicy.yaml
    ├── serviceaccount.yaml
    └── NOTES.txt
```

### Önemli `values.yaml` Alanları

```yaml
deployment:
  mode: simple                  # simple | scaled

image:
  registry: harbor.kuveytturk.com.tr
  repository: ansible-ui
  tag: ""                       # Chart.appVersion kullanılır
  pullPolicy: IfNotPresent
  pullSecrets: [harbor-cred]

api:
  replicaCount: 1
  resources:
    requests: {cpu: 200m, memory: 512Mi}
    limits:   {cpu: 1000m, memory: 1Gi}

worker:
  replicaCount: 1               # ASLA artırılmaz
  resources:
    requests: {cpu: 100m, memory: 256Mi}
    limits:   {cpu: 500m, memory: 512Mi}

web:
  replicaCount: 2
  resources:
    requests: {cpu: 50m, memory: 64Mi}
    limits:   {cpu: 200m, memory: 128Mi}

persistence:
  enabled: true
  size: 5Gi
  storageClass: ""
  accessMode: ReadWriteOnce

postgres:
  enabled: false                # üretimde harici DB tercih edilir
  externalUrl: ""               # Secret'tan gelir

ingress:
  enabled: true
  className: nginx
  host: ansibleui.kuveytturk.com.tr
  tls:
    enabled: true
    secretName: ansibleui-tls

ado:
  baseUrl: https://ktdevops/tfs
  collection: KT
  project: KT.ITAutomation
  repository: Ansible.appAdminConfig
  apiVersion: "6.0"

caBundle:
  enabled: true
  secretName: ansibleui-ca
  key: ca-bundle.crt

pipelines:
  nonprodId: 0
  prodId: 0
  dmzNonprodId: 0
  dmzProdId: 0
```

## 4. Yapılandırma Değişkenleri

Tümü `ANSIBLEUI_` öneklidir ([backend/app/core/config.py](../backend/app/core/config.py)).

### ConfigMap (hassas değil)

| Değişken | Örnek | Açıklama |
|---|---|---|
| `ANSIBLEUI_ENV` | `production` | Ortam |
| `ANSIBLEUI_LOG_LEVEL` | `INFO` | Log seviyesi |
| `ANSIBLEUI_REPO_PATH` | `/data/repo` | Git çalışma kopyası |
| `ANSIBLEUI_REPO_URL` | `https://ktdevops/tfs/KT/KT.ITAutomation/_git/Ansible.appAdminConfig` | |
| `ANSIBLEUI_REPO_DEFAULT_BRANCH` | `main` | |
| `ANSIBLEUI_BRANCH_PREFIX` | `ansibleui` | Yazma branch öneki |
| `ANSIBLEUI_ADO_BASE_URL` | `https://ktdevops/tfs` | |
| `ANSIBLEUI_ADO_COLLECTION` | `KT` | |
| `ANSIBLEUI_ADO_PROJECT` | `KT.ITAutomation` | |
| `ANSIBLEUI_ADO_REPOSITORY` | `Ansible.appAdminConfig` | |
| `ANSIBLEUI_ADO_API_VERSION` | `6.0` | |
| `ANSIBLEUI_CA_BUNDLE_PATH` | `/etc/ssl/certs/ca-bundle.crt` | |
| `ANSIBLEUI_PIPELINE_*_ID` | `42` | Ortam başına pipeline tanımı |
| `ANSIBLEUI_INDEX_INTERVAL_SECONDS` | `60` | |
| `ANSIBLEUI_RUN_POLL_INTERVAL_SECONDS` | `5` | |
| `ANSIBLEUI_AUTH_PROVIDER` | `local` | `local` \| `ldap` |

### Secret (hassas)

| Değişken | Açıklama |
|---|---|
| `ANSIBLEUI_DATABASE_URL` | Parola içerir |
| `ANSIBLEUI_ADO_PAT` | Kapsam: Code RW, PR RW, Build R+Execute. **Merge yetkisi verilmez** |
| `ANSIBLEUI_JWT_SECRET` | ≥32 bayt rastgele |
| `ANSIBLEUI_WEBHOOK_SECRET` | ADO service hook HMAC sırrı |
| `ANSIBLEUI_AI_API_KEY` | Faz 7 |

Secret'lar **imaja gömülmez**, Git'e yazılmaz. Kurumsal secret yönetimi varsa
(Vault, Sealed Secrets) oradan beslenir.

## 5. Konteyner İmajları

Her ikisi de çok aşamalı, non-root, slim taban.

```dockerfile
# backend/Dockerfile (özet)
FROM python:3.12-slim AS builder
# bağımlılıklar wheel olarak derlenir

FROM python:3.12-slim
RUN useradd --uid 10001 --create-home appuser
USER 10001
COPY --from=builder /wheels /wheels
# ...
HEALTHCHECK CMD python -c "import httpx; httpx.get('http://localhost:8000/healthz')"
```

`worker`, `api` ile **aynı imajı** kullanır; yalnızca komut farklıdır
(`python -m app.worker`). Bu, imaj sayısını ve sürüm uyumsuzluğu riskini azaltır.

### Güvenlik Bağlamı

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: [ALL]
  seccompProfile:
    type: RuntimeDefault
```

`readOnlyRootFilesystem: true` ile birlikte `/tmp` ve PVC için `emptyDir`/PVC bağlanır.

## 6. Sağlık Kontrolleri

| Sonda | Yol | Ayarlar |
|---|---|---|
| Liveness | `/healthz` | initialDelay 20s, period 15s, failure 3 |
| Readiness | `/readyz` | initialDelay 10s, period 10s, failure 3 |
| Startup | `/healthz` | failureThreshold 30, period 10s — ilk klon uzun sürebilir |

`/readyz` kontrolleri: PostgreSQL bağlantısı, PVC erişimi, aktif indeks varlığı.
İlk indeksleme tamamlanmadan `503 INDEX_NOT_READY` döner.

## 7. Ağ Politikası

```yaml
egress:
  - to: ktdevops       (443)     # Azure DevOps Server
  - to: postgres       (5432)
  - to: qwen-endpoint  (443)     # Faz 7
  - to: kube-dns       (53)
ingress:
  - from: ingress-controller → web, api
```

Hedef Windows sunucularına giden trafik **açıkça reddedilir** — platform oraya hiç
bağlanmamalıdır.

## 8. İlk Kurulum

```powershell
# 1. Namespace
kubectl create namespace ansible-ui

# 2. Secret'lar (değerler kurumsal secret yönetiminden)
kubectl -n ansible-ui create secret generic ansibleui-secrets `
  --from-literal=ANSIBLEUI_ADO_PAT="<pat>" `
  --from-literal=ANSIBLEUI_JWT_SECRET="<32+ bayt>" `
  --from-literal=ANSIBLEUI_DATABASE_URL="postgresql+asyncpg://..." `
  --from-literal=ANSIBLEUI_WEBHOOK_SECRET="<sir>"

# 3. İç CA bundle
kubectl -n ansible-ui create secret generic ansibleui-ca `
  --from-file=ca-bundle.crt=./ca-bundle.crt

# 4. Harbor kimliği
kubectl -n ansible-ui create secret docker-registry harbor-cred `
  --docker-server=harbor.kuveytturk.com.tr `
  --docker-username="<kullanici>" --docker-password="<parola>"

# 5. Kurulum
helm upgrade --install ansible-ui ./deploy/helm/ansible-ui `
  --namespace ansible-ui `
  --values ./deploy/helm/ansible-ui/values-nonprod.yaml
```

İlk açılışta yönetici hesabı `ANSIBLEUI_BOOTSTRAP_ADMIN` ile oluşturulur ve
**ilk girişte parola değiştirme** zorunludur.

## 9. Veritabanı Göçü

Göçler bir Helm `pre-upgrade` hook Job'ı olarak çalışır:

```yaml
annotations:
  "helm.sh/hook": pre-install,pre-upgrade
  "helm.sh/hook-weight": "-5"
  "helm.sh/hook-delete-policy": before-hook-creation
command: ["alembic", "upgrade", "head"]
```

Göç başarısız olursa yükseltme durur ve mevcut sürüm çalışmaya devam eder.

## 10. Yedekleme

| Veri | Yedek gerekli mi | Yöntem |
|---|---|---|
| PostgreSQL — kalıcı tablolar | **Evet** | Günlük `pg_dump`, 30 gün saklama |
| PostgreSQL — indeks tabloları | Hayır | Yeniden üretilebilir |
| PVC (git çalışma kopyası) | Hayır | Azure DevOps'tan yeniden klonlanabilir |
| Secret'lar | **Evet** | Kurumsal secret yönetiminde |

Felaket kurtarma: yeni namespace'e Helm kur → DB'yi geri yükle → indeks otomatik
yeniden üretilir. Hedef kurtarma süresi < 1 saat.

## 11. Gün 1 Doğrulama Listesi

Dağıtımdan önce bu varsayımlar **fiilen test edilmelidir**:

| # | Doğrulama | Nasıl |
|---|---|---|
| 1 | Pod'dan `ktdevops`'a HTTPS erişimi | `kubectl run -it --rm curl --image=curlimages/curl -- curl -v https://ktdevops/tfs/KT/_apis/` |
| 2 | Desteklenen `api-version` | Aynı çağrının yanıt başlıkları |
| 3 | PAT'in gerekli kapsamları var mı | Test PR'ı açma denemesi (nonprod) |
| 4 | İç CA bundle doğru mu | `curl --cacert ca-bundle.crt https://ktdevops/` |
| 5 | ADO service hook desteği | ADO arayüzünde Service Hooks bölümü |
| 6 | PVC RWO davranışı | İki pod aynı node'a schedule olabiliyor mu |
| 7 | Qwen endpoint erişimi (Faz 7) | `curl` ile `/v1/models` |
| 8 | Pipeline tanım kimlikleri | `GET /build/definitions` |

Sonuçlar bu dokümanın sonuna tarih ve kişi belirtilerek eklenir.

## 12. İşletim Kılavuzu (Runbook)

| Belirti | Kontrol | Çözüm |
|---|---|---|
| «Senkronizasyon gecikti» | Worker log'u, `/api/status` | PAT geçerli mi, ağ erişimi var mı |
| `503 INDEX_NOT_READY` | Worker log'u | İlk indeksleme sürüyor, bekle; uzunsa log'a bak |
| PR açılamıyor | `publish_request.error` | PAT kapsamı, branch koruma kuralları |
| Çalıştırma tetiklenmiyor | Pipeline tanım kimlikleri | `ANSIBLEUI_PIPELINE_*_ID` doğru mu |
| Log gelmiyor | Build timeline yanıtı | Build çalışıyor mu, PAT'te Build Read var mı |
| Pod `CrashLoopBackOff` | `kubectl logs` | Zorunlu ortam değişkeni eksik olabilir |
| PVC bağlanamıyor | Pod affinity | `deployment.mode: simple`'a geç |
| Yüksek bellek | `/metrics` | İndeksleme sırasında beklenir; limiti artır |

**Acil durdurma:** `kubectl -n ansible-ui scale deployment --all --replicas=0`
Pipeline'lar ve depo etkilenmez; yalnızca arayüz erişilemez olur.
