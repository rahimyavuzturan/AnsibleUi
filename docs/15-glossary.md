# 15 — Terim Sözlüğü

## Ansible Terimleri

| Terim | Türkçe karşılık | Açıklama |
|---|---|---|
| **playbook** | playbook | Bir veya daha fazla oynatma içeren YAML dosyası. Çevrilmez. |
| **play** | oynatma | Playbook içinde bir host kümesine uygulanan görev bloğu |
| **task** | görev | Tek bir işlem adımı (bir modül çağrısı) |
| **role** | rol | Yeniden kullanılabilir görev, şablon ve dosya paketi |
| **module** | modül | Ansible'ın çalıştırdığı birim (`win_copy`, `win_iis_website`) |
| **inventory** | envanter | Hedef sunucuların ve gruplarının tanımı |
| **host** | sunucu / host | Tek bir hedef makine |
| **group** | grup | Sunucu kümesi. `[web:children]` ile iç içe olabilir |
| **vars / variables** | değişken | Playbook, rol veya envanterde tanımlı değerler |
| **facts** | olgu | Ansible'ın hedeften topladığı bilgiler (`ansible_os_family`) |
| **register** | kayıt | Bir görevin çıktısını değişkene atama |
| **handler** | işleyici | `notify` ile tetiklenen koşullu görev |
| **vault** | vault | Ansible'ın şifreli secret deposu |
| **idempotent** | değişmez sonuçlu | Aynı görevin tekrar çalışması ek değişiklik yaratmaz |
| **changed** | değişti | Görev hedefte bir şey değiştirdi (hata değil, bilgi) |
| **skipped** | atlandı | `when` koşulu sağlanmadığı için çalışmadı |
| **unreachable** | ulaşılamadı | Sunucuya bağlanılamadı |
| **WinRM** | WinRM | Windows uzaktan yönetim protokolü |
| **dispatcher** | dağıtıcı | Bu projeye özgü: `state` gibi bir parametreye göre farklı görev dosyası seçen rol deseni |

## Azure DevOps Terimleri

| Terim | Türkçe karşılık | Açıklama |
|---|---|---|
| **Azure DevOps Server (TFS)** | — | Kurum içi (on-prem) sürüm. `dev.azure.com` değil |
| **collection** | koleksiyon | Sunucu üzerindeki proje kümesi (`KT`) |
| **project** | proje | `KT.ITAutomation` |
| **pipeline** | pipeline | CI/CD tanımı. Çevrilmez |
| **agent pool** | agent havuzu | Pipeline'ı çalıştıran makineler (`AnsibleTestEnv`, `Ansible`) |
| **build** | build / çalıştırma | Pipeline'ın bir koşumu |
| **timeline** | zaman çizelgesi | Build adımlarının durum listesi |
| **PAT** | PAT | Personal Access Token |
| **secure file** | güvenli dosya | Pipeline'a sağlanan gizli dosya (vault parolası) |
| **pull request** | pull request (PR) | Değişiklik inceleme talebi. Çevrilmez |
| **service hook** | service hook | Olay tetikli giden webhook |
| **pbList** | pbList | Bu depoya özgü: pipeline'daki playbook yolu açılır listesi |

## Proje Terimleri

| Terim | Açıklama |
|---|---|
| **IR** (Intermediate Representation) | Ara temsil. YAML'ın tipli, arayüze uygun görünümü. Doğruluk kaynağı değildir |
| **round-trip** | Gidiş-dönüş. Parse → serialize sonrası dosyanın aynı kalması |
| **byte-identical** | Bayt düzeyinde özdeş. Round-trip sözleşmesinin ölçütü |
| **node** | Canvas'taki bir öğe. Bir rol çağrısı, include veya ham blok |
| **RAW node** | Görselleştirilemeyen, ham YAML olarak korunan node (`NodeType.RAW`). Sebebi `lock_reason` alanında açıklanır |
| **örtük bağımlılık** | İki node arasında `register` üzerinden kurulan, YAML'da görünmeyen ilişki |
| **şema çıkarımı** | Rol parametrelerinin kod ve kullanımdan otomatik tespiti |
| **güven skoru** | Çıkarılan şemanın güvenilirlik derecesi (`high`/`medium`/`low`) |
| **varyant** | Bir rolün dağıtıcı parametreye göre farklı parametre seti (`createWebSiteApp@recursive`) |
| **doğrulayıcı** | Dosyalar arası tutarlılık kuralı (V001-V010) |
| **taslak (draft)** | Henüz yayınlanmamış değişiklik |
| **yayınlama (publish)** | Taslağı branch + commit + PR'a dönüştürme |
| **ön kontrol (preflight)** | Çalıştırma öncesi bloklayıcı denetimler |
| **snapshot** | Belirli bir commit'teki indekslenmiş depo durumu |
| **altın test** | Round-trip sözleşmesini doğrulayan test kümesi |
| **iş paketi (WP)** | Work Package. Bağımsız tamamlanabilir geliştirme birimi |
| **dört göz ilkesi** | Prod çalıştırmada tetikleyen ve onaylayanın farklı kişi olması |

## Rol Modeli

| Rol | Yetki |
|---|---|
| **Viewer** | Yalnızca görüntüleme |
| **Editor** | Düzenleme, PR açma, nonprod çalıştırma |
| **Approver** | Editor + prod çalıştırma + onay verme |
| **Admin** | Approver + kullanıcı/rol/şema/ayar yönetimi |

## Ortamlar

| Ortam | Agent havuzu | Onay | Açıklama |
|---|---|---|---|
| `nonprod` | `AnsibleTestEnv` | Gerekmez | Dev, test, prep sunucuları |
| `prod` | `Ansible` | **Gerekir** | Üretim |
| `dmz_nonprod` | (dmz test) | Gerekmez | DMZ test |
| `dmz_prod` | `spd1ansible` | **Gerekir** | DMZ üretim |

## Bu Depoya Özgü Adlar

| Ad | Anlam |
|---|---|
| **isube** | İnternet şube uygulaması (`OBA.Web.InternetBanking`) |
| **msube** | Mobil şube |
| **tsube** | Ticari şube |
| **BOA** | Kurumun temel uygulama çatısı |
| **altortam** | Alt ortamlar (dev/test/prep) |
| **fresh_server** | Sıfırdan sunucu kurulumu senaryosu |
| **sdl / stl / sxl** | Sunucu adı önekleri: dev / test / prep |
| **spl / srv** | Üretim sunucu önekleri |

## Kısaltmalar

| Kısaltma | Açılım |
|---|---|
| ADO | Azure DevOps |
| ADR | Architecture Decision Record (Mimari Karar Kaydı) |
| IR | Intermediate Representation (Ara Temsil) |
| PVC | Persistent Volume Claim |
| RWO / RWX | ReadWriteOnce / ReadWriteMany |
| RBAC | Role-Based Access Control |
| SPA | Single Page Application |
| WBS | Work Breakdown Structure (İş Kırılım Yapısı) |
| WP | Work Package (İş Paketi) |
| SSRF | Server-Side Request Forgery |
| HMAC | Hash-based Message Authentication Code |
| FQCN | Fully Qualified Collection Name (`ansible.windows.win_copy`) |
