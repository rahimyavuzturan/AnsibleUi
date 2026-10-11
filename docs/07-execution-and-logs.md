# 07 — Çalıştırma ve Log

## 1. Model

Platform Ansible'ı **kendisi çalıştırmaz**. Mevcut Azure Pipeline'ı tetikler ve sonucu izler.

```
Kullanıcı                  Platform                    Azure DevOps            Agent
   │                          │                             │                    │
   │ playbook + ortam seç     │                             │                    │
   ├─────────────────────────►│                             │                    │
   │                          │ ön kontroller               │                    │
   │                          │ (4 adet, bloklayıcı)        │                    │
   │                          │                             │                    │
   │                          │ POST /build/builds          │                    │
   │                          ├────────────────────────────►│                    │
   │                          │◄── buildId ─────────────────┤                    │
   │◄── runId ────────────────┤                             │ kuyruğa al ───────►│
   │                          │                             │                    │
   │                          │ worker: 5 sn'de bir         │              ansible-playbook
   │                          │ GET timeline + logs         │                    │
   │                          ├────────────────────────────►│◄───────────────────┤
   │                          │ ansible -v çıktısını        │                    │
   │                          │ ayrıştır                    │                    │
   │◄══ WebSocket ════════════┤                             │                    │
   │    task × host durumları │                             │                    │
```

Gerekçe ve bedelleri: [ADR-0003](adr/ADR-0003-pipeline-trigger-not-own-runner.md)

## 2. Ortam Eşlemesi

Her ortamın kendi pipeline tanımı ve agent havuzu vardır:

| Ortam | Pipeline dosyası | Agent havuzu | Onay |
|---|---|---|---|
| `nonprod` | `azure-pipelines/nonprod/azure-pipelines-playbook.yml` | `AnsibleTestEnv` | Gerekmez |
| `prod` | `azure-pipelines/prod/azure-pipelines-playbook.yml` | `Ansible` | **Approver** |
| `dmz_nonprod` | `azure-pipelines/dmz_nonprod/azure-pipelines-playbook.yml` | (dmz test) | Gerekmez |
| `dmz_prod` | `azure-pipelines/dmz_prod/azure-pipelines-playbook.yml` | `spd1ansible` | **Approver** |

Pipeline tanım kimlikleri yapılandırmadan gelir:
`ANSIBLEUI_PIPELINE_NONPROD_ID`, `ANSIBLEUI_PIPELINE_PROD_ID`, vb.

## 3. Ön Kontroller

Hepsi **bloklayıcıdır**. Herhangi biri başarısızsa çalıştırma başlatılmaz.

| # | Kontrol | Hata mesajı (kullanıcıya) |
|---|---|---|
| 1 | Playbook `origin/main`'de var mı? | «Bu playbook henüz main'de yok. Önce PR'ınızın merge edilmesi gerekiyor.» |
| 2 | Playbook ilgili ortamın `pbList` listesinde mi? | «Bu playbook <ortam> pipeline listesinde tanımlı değil, çalıştırılamaz.» |
| 3 | Kullanıcının o ortam için `run` yetkisi var mı? | «<ortam> ortamında çalıştırma yetkiniz yok.» |
| 4 | prod / dmz_prod ise onay alınmış mı? | «Bu ortam için Approver onayı gerekiyor.» |

Ayrıca kullanıcıya **çalıştırma öncesi özet** gösterilir ve onaylatılır:

```
Playbook   : altortam/install_isube/install_isube_test.yml
Ortam      : nonprod  (havuz: AnsibleTestEnv)
Commit     : 16522d0  "fix: isube profile klasoru"
Hedef      : test_isube  →  stlisube1, stlisube2   (2 sunucu)
Roller     : create_dir, copyFile_Multiple, installUninstallPackage, ... (17 adım)
Uyarılar   : yok
```

Hedef host listesi envanter indeksinden hesaplanır. Bu, "hangi sunuculara dokunacağım?"
sorusunu çalıştırmadan **önce** cevaplar — mevcut sistemde bu bilgi hiç görünmüyordu.

## 4. Tetikleme

```http
POST {repoApiRoot}/build/builds?api-version=6.0
```

```json
{
  "definition": { "id": 42 },
  "sourceBranch": "refs/heads/main",
  "parameters": "{\"pbList\":\"altortam/install_isube/install_isube_test.yml\"}"
}
```

`parameters` alanının **JSON olarak kodlanmış bir metin** olması Azure DevOps'un
beklediği biçimdir.

Çalıştırma **her zaman `main` üzerinden** yapılır. Rastgele branch çalıştırmak
mümkün değildir — bu, "PR merge edilmeden prod'a bir şey gitmesi" riskini ortadan kaldırır.

## 5. Log Toplama

Worker, aktif çalıştırmalar için 5 saniyede bir yoklama yapar:

```
GET /build/builds/{buildId}                 → genel durum
GET /build/builds/{buildId}/timeline        → adım (step) durumları
GET /build/builds/{buildId}/logs/{logId}    → log içeriği (artımlı)
```

Artımlı okuma: her log için son okunan satır sayısı tutulur; yalnızca yeni satırlar
işlenir. Bu, uzun çalıştırmalarda gereksiz veri transferini önler.

### Sonlanma

Build durumu `completed` olduğunda son bir tam okuma yapılır, sonuç özetlenir ve
yoklama durdurulur. `run` kaydı nihai durumuna geçer.

## 6. Ansible Çıktısı Ayrıştırma

Pipeline `-v` ile çalıştığı için çıktı öngörülebilir bir yapıdadır.

### Tanınan Desenler

```
PLAY [install isube_test (fresh server - full server prep)] ********************
TASK [Gathering Facts] *********************************************************
ok: [stlisube1]
TASK [create_dir : Create directories] *****************************************
changed: [stlisube1] => (item=D:\WebSites\OBA.Web.InternetBanking)
failed: [stlisube2] => {"msg": "..."}
skipping: [stlisube1]
fatal: [stlisube2]: UNREACHABLE! => {...}

PLAY RECAP *********************************************************************
stlisube1 : ok=45  changed=12  unreachable=0  failed=0  skipped=3  rescued=0  ignored=0
stlisube2 : ok=40  changed=10  unreachable=0  failed=1  skipped=3  rescued=0  ignored=0
```

| Desen | Çıkarım |
|---|---|
| `PLAY [ad]` | Yeni oynatma başlangıcı |
| `TASK [rol : görev adı]` | Yeni görev; `rol` ve `görev adı` ayrıştırılır |
| `ok: [host]` | `status = ok` |
| `changed: [host]` | `status = changed` |
| `failed: [host]` / `fatal: [host]` | `status = failed`, mesaj JSON'dan çıkarılır |
| `skipping: [host]` | `status = skipped` |
| `UNREACHABLE!` | `status = unreachable` |
| `=> (item=...)` | Döngü öğesi; ana göreve gruplanır |
| `PLAY RECAP` | Host başına nihai sayaçlar |

### Çıktı Modeli

```python
class RunTaskResult(BaseModel):
    task_index: int
    task_name: str
    role_name: str | None
    host: str
    status: Literal["ok", "changed", "failed", "skipped", "unreachable"]
    duration_ms: int | None
    message: str | None       # yalnizca hata durumunda, maskelenmis
```

Arayüzde **task × host matrisi** olarak gösterilir:

```
                              stlisube1   stlisube2
Gathering Facts                   ok          ok
create_dir : Create directories   changed     changed
copyFile_Multiple : Copy files    changed     failed ⚠
installUninstallPackage : ...     ok          skipped
```

Bu görünüm, "hangi sunucuda hangi adımda takıldı?" sorusunu tek bakışta cevaplar.

## 7. Güvenlik: Log Maskeleme

Ham log'lar Azure DevOps'ta kalır, **veritabanına yazılmaz**. Arayüze gönderilen
ve DB'ye yazılan her metin maskeleme filtresinden geçer:

| Hedef | Örnek |
|---|---|
| Parola benzeri anahtarlar | `password`, `passwd`, `secret`, `token`, `apikey`, `pfx`, `thumbprint` içeren satırlar |
| Ansible `no_log` çıktıları | `the output has been hidden` → olduğu gibi bırakılır |
| Bağlantı dizeleri | `Server=...;Password=...` desenleri |
| PAT / Bearer | `Bearer ey...`, `Basic ...` |

Maskelenen değer `***` ile değiştirilir; anahtarın kendisi görünür kalır (hata ayıklama
için bağlam gerekir).

Ansible'ın `-v` çıktısı zaten `no_log: true` olan görevlerin değerlerini gizler, fakat
buna güvenilmez — maskeleme her hâlükârda uygulanır.

## 8. WebSocket Protokolü

```
WS /ws/runs/{runId}
```

Mesaj tipleri:

```json
{"type": "run_status",  "status": "running", "started_at": "..."}
{"type": "task_update", "task_index": 3, "task_name": "...", "role_name": "create_dir",
                        "results": [{"host": "stlisube1", "status": "changed"}]}
{"type": "log_append",  "lines": ["TASK [...] ****", "changed: [stlisube1]"]}
{"type": "run_done",    "status": "succeeded", "recap": {...}, "duration_ms": 184000}
{"type": "error",       "message": "Azure DevOps'a ulasilamiyor, yeniden deneniyor"}
```

Kurallar:
- Bağlantı açılırken JWT doğrulanır ve kullanıcının o çalıştırmayı görme yetkisi kontrol edilir.
- Bağlantı koparsa istemci üstel geri çekilme ile yeniden bağlanır ve son durumu tam olarak alır.
- WebSocket yalnızca bir **hızlandırıcıdır**; tüm veri `GET /api/runs/{id}` ile de alınabilir.

## 9. Çalıştırma Geçmişi

Her çalıştırma kalıcı olarak saklanır:

| Alan | Kullanım |
|---|---|
| Kim tetikledi, kim onayladı | Hesap verebilirlik |
| Hangi commit | Tam olarak hangi kod çalıştı |
| Hangi playbook ve ortam | Kapsam |
| Hedef host'lar | Etki alanı |
| Sonuç ve süre | Eğilim analizi |
| ADO build kimliği | Ham log'a köprü |

Filtreler: ortam, playbook, kullanıcı, durum, tarih aralığı.
"Tekrar çalıştır" düğmesi, aynı parametrelerle yeni bir çalıştırma başlatır —
ön kontroller **yeniden** uygulanır.

## 10. Sınırlar

| Sınır | Etki | Kabul gerekçesi |
|---|---|---|
| ~5 sn log gecikmesi | Gerçek zamanlı değil | Kurulum playbook'ları dakikalarca sürüyor; 5 sn önemsiz |
| Çalıştırma iptali | Yalnızca ADO build'i iptal edilir; devam eden Ansible görevi kesilmez | Ansible'ın doğal davranışı |
| Eşzamanlılık | Agent havuzu kapasitesiyle sınırlı | Mevcut durumla aynı |
| `--check` (dry-run) | MVP'de yok | Pipeline parametresi eklenmesi gerekir → Faz 8 (WP-83) |
| Kısmi çalıştırma (tek task) | Desteklenmez | Ansible/pipeline modeli buna uygun değil |
