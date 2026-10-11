# 14 — Test Stratejisi

## 1. Test Piramidi

```
        ╱╲          E2E (Playwright)           ~10 senaryo
       ╱──╲         Kullanıcı akışları
      ╱────╲
     ╱──────╲       Entegrasyon (pytest)       ~60 test
    ╱────────╲      DB, git, sahte ADO
   ╱──────────╲
  ╱────────────╲    Birim (pytest, vitest)     ~400 test
 ╱──────────────╲   Saf mantık
╱────────────────╲
─────────────────── ★ ALTIN TESTLER            ~900 dosya
                     Round-trip byte-identical
```

Altın testler piramidin dışındadır: bunlar **doğruluk sözleşmesinin** kanıtıdır.

## 2. Altın Testler ★

### 2.1 Round-Trip Sözleşmesi

```python
@pytest.mark.parametrize("yaml_path", iter_reference_yaml_files())
def test_roundtrip_is_byte_identical(yaml_path: Path) -> None:
    """Her YAML dosyasi parse->serialize sonrasi byte duzeyinde ayni kalmalidir."""
    original = yaml_path.read_bytes()
    document = parse_document(original.decode("utf-8"))
    produced = serialize_document(document).encode("utf-8")
    assert produced == original
```

Kapsam: `Ansible.appAdminConfig` altındaki **tüm** `.yml` ve `.yaml` dosyaları
(477 dosya: playbook'lar, rol görevleri, pipeline'lar).

**Son durum (2026-09-30, WP-10):** 477/477 birebir — 1441 altın test yeşil, sıfır atlama.

| Kural | Gerekçe |
|---|---|
| Bu test kırmızıysa **hiçbir şey merge edilmez** | Sözleşme ihlali demektir |
| Referans depo yoksa `skip` | Yeni geliştirici kurulumu engellenmemeli |
| CI'da referans depo **zorunlu** klonlanır (`ANSIBLEUI_GOLDEN_REQUIRED=1`) | CI'da atlanmasına izin verilmez |
| Başarısız dosya adı ve ilk farklı bayt konumu raporlanır | Hata ayıklanabilir olmalı |
| Bilinen bozuk dosyalar `KNOWN_BROKEN` listesinde açıkça tutulur | Sessiz ayrıştırma hatası kabul edilmez |

### 2.2 Yama Sözleşmesi

Bir parametre değiştiğinde, dosyanın **geri kalanı** değişmemelidir:

```python
def test_patch_only_touches_target(isube_freshserver: Path) -> None:
    """Hedefli yama, dokunulmayan satirlari degistirmemelidir."""
    original = _read_exact(isube_freshserver)
    document = parse_document(original)

    span = document.span("/0/vars/paths/0")
    edit = TextEdit(span.start, span.end, "'D:\\WebSitesYeni'")
    produced = serialize_document(document, [edit])

    diff = list(difflib.unified_diff(original.splitlines(), produced.splitlines(), n=0))
    added = [line for line in diff if line.startswith("+") and not line.startswith("+++")]
    removed = [line for line in diff if line.startswith("-") and not line.startswith("---")]

    assert len(added) == 1
    assert len(removed) == 1
```

### 2.3 Node Kapsamı

Hiçbir görev "kaybolmamalıdır":

```python
def test_no_task_is_lost(isube_freshserver: Path) -> None:
    """Dosyadaki her ust duzey gorev bir IR node'una eslenmelidir."""
    document = parse_document(isube_freshserver.read_text(encoding="utf-8"))
    assert len(document.nodes) == 17
    assert all(node.type is not NodeType.UNKNOWN for node in document.nodes)
```

## 3. Birim Testleri

### Backend Öncelikleri

| Modül | Odak |
|---|---|
| `ansible/parser.py` | Biçim tespiti, hatalı YAML işleme, kodlama |
| `ansible/ir.py` | Node tipi kararı, kimlik üretimi, kısmi kilitleme |
| `ansible/serializer.py` | Girinti/tırnak koruma, yazma sonrası doğrulama |
| `ansible/inventory.py` | Grup, children, vars, iç içe miras |
| `ansible/schema_infer.py` | Tip çıkarımı, dağıtıcı tespiti, güven skoru |
| `ansible/graph.py` | Örtük kenar tespiti, döngü kontrolü |
| `ansible/validators.py` | V001-V010'un her biri, pozitif ve negatif durum |
| `core/paths.py` | Traversal, allowlist, Windows/POSIX ayrımı |
| `core/logging.py` | Secret maskeleme |
| `gitops/repo_service.py` | Branch adı üretimi, `main` koruması |
| `services/log_parser.py` | Ansible çıktı desenleri |

### Frontend Öncelikleri

| Alan | Odak |
|---|---|
| Şemadan form üretimi | Her parametre tipi doğru kontrole eşleniyor |
| Canvas etkileşimleri | Sürükleme, sıralama, örtük bağımlılık engeli |
| Diff görüntüleme | Doğru satırlar vurgulanıyor |
| Durum bileşenleri | Yükleniyor/boş/hata/dolu |
| Erişilebilirlik | Klavye gezinimi, ARIA etiketleri |

## 4. Entegrasyon Testleri

Gerçek PostgreSQL (testcontainers veya compose) ve gerçek git deposu (geçici)
kullanılır. **Gerçek ağ çağrısı yapılmaz.**

| Test | Doğruladığı |
|---|---|
| İndeksleme akışı | Klon → parse → DB; artımlı güncelleme |
| Taslak yaşam döngüsü | Oluştur → düzenle → revizyon → yayınla |
| Yayınlama akışı | Branch + commit + push (yerel bare depoya) + sahte PR |
| Çakışma senaryosu | Temel değiştiğinde doğru davranış |
| `pbList` güncellemesi | Doğru dosya, alfabetik sıra, geri kalan byte-identical |
| Çalıştırma akışı | Ön kontroller → sahte build → log ayrıştırma → WebSocket |
| Yetki matrisi | Rol × eylem × ortam kombinasyonlarının tamamı |

### Sahte ADO Sunucusu

`tests/fakes/fake_ado.py` — gerçek API'nin sözleşmesini taklit eden bir FastAPI
uygulaması. Şunları destekler: PR oluşturma, build kuyruğa alma, timeline, log.
Hata senaryoları (401, 409, 502) parametreyle tetiklenebilir.

## 5. E2E Testleri

Playwright ile, tam yığın `docker compose` üzerinde.

| # | Senaryo |
|---|---|
| E1 | Giriş → pano → çıkış |
| E2 | Rol kataloğunda arama → `createWebSiteApp` detayı → 3 varyantı görme |
| E3 | Envanter gezgini → `test_isube` → host'lar ve hedefleyen playbook'lar |
| E4 | Playbook aç → node listesi → örtük bağımlılık okunu görme |
| E5 | `create_dir` node'una yol ekleme → taslağa kaydetme |
| E6 | Doğrulayıcı uyarısını tetikleme ve görme |
| E7 | Diff önizleme → PR açma (sahte ADO) |
| E8 | Çakışma senaryosu → yeniden temelleme |
| E9 | Çalıştırma ön kontrolü → tetikleme → canlı log izleme |
| E10 | Viewer kullanıcı prod'da çalıştırmayı deniyor → engelleniyor |

## 6. Güvenlik Testleri

[08-security-and-rbac.md](08-security-and-rbac.md) bölüm 8'de listelenen testler
her koşuda çalışır:

| Test | Doğruladığı |
|---|---|
| `test_git_safety.py` | `main`'e push istisna fırlatır |
| `test_paths.py` | Traversal ve allowlist dışı reddedilir |
| `test_authz_matrix.py` | Tam yetki matrisi |
| `test_no_vault_read.py` | Kod tabanında vault yolu okuma yok |
| `test_logging_mask.py` | Riskli anahtarlar maskelenir |
| `test_no_tls_bypass.py` | `verify=False` deseni yok |
| `test_four_eyes.py` | Onaysız prod çalıştırma engellenir |
| `test_layering.py` | Katman bağımlılık yönü korunur |

Son üçü **statik kod analizi** ile çalışır: kaynak dosyalar taranır, yasak desen
bulunursa test başarısız olur.

## 7. Performans Testleri

| Ölçüt | Hedef | Yöntem |
|---|---|---|
| Tam indeksleme | < 60 sn | `pytest --benchmark` |
| Artımlı indeksleme (1 dosya) | < 2 sn | Aynı |
| Şema çıkarımı (65 rol) | < 10 sn | Aynı |
| Rol arama API | < 300 ms | Yük testi |
| Canvas (100 node) | < 16 ms/kare | Playwright trace |

Performans testleri CI'da **bilgi amaçlıdır**, bloklayıcı değildir; ancak %50'den
fazla gerileme uyarı üretir.

## 8. Test Verisi

| Kaynak | Kullanım |
|---|---|
| **Gerçek referans depo** | Altın testler, şema çıkarımı, doğrulayıcılar |
| `tests/fixtures/yaml/` | Kenar durumlar: bozuk YAML, anchor, çok belge, CRLF |
| `tests/fixtures/logs/` | Gerçek Ansible çıktıları (anonimleştirilmiş) |
| `tests/factories/` | DB nesneleri için fabrika fonksiyonları |

**Kural:** Referans depodan alınan fixture'lar aynen kopyalanır, "temizlenmez".
Gerçek dünyadaki dağınıklık test edilmesi gereken şeydir.

Hassas içerik (gerçek host adları, sertifika yolları) fixture'lara kopyalanırken
anonimleştirilir; yapısal özellikler korunur.

## 9. CI Boru Hattı

```
1. Kurulum        (Python 3.12, Node 20, referans depo klonu)
2. Lint           ruff check · ruff format --check · eslint · prettier --check
3. Tip kontrolü   mypy --strict · tsc --noEmit
4. ★ Altın test   pytest tests/golden          ← en önce, en hızlı geri bildirim
5. Birim testler  pytest tests/unit · vitest
6. Entegrasyon    pytest tests/integration
7. Güvenlik       pip-audit · npm audit --audit-level=high
8. Derleme        docker build (backend + frontend)
9. E2E            playwright test
```

Adım 4 başarısızsa sonraki adımlar **çalıştırılmaz** — en kritik sözleşme o.

## 10. Kapsam Hedefleri

| Alan | Hedef | Zorunlu mu |
|---|---|---|
| `app/ansible/` | **≥ 90%** | Evet — bloklayıcı |
| `app/services/` | ≥ 80% | Evet |
| `app/gitops/`, `app/ado/` | ≥ 80% | Evet |
| `app/api/` | ≥ 70% | Hayır — E2E kapsıyor |
| Frontend `features/` | ≥ 70% | Hayır |

Kapsam bir **araçtır**, hedef değildir. Kritik yolların test edilmesi, yüzdenin
tutturulmasından önemlidir.

## 11. Agent'lar İçin Kurallar

`app/ansible/` üzerinde çalışan bir agent şunları yapmadan işi bitmiş sayamaz:

1. Altın testi çalıştır ve **atlanmadığını** doğrula:
   `pytest tests/golden -v` çıktısında `skipped` görünmemeli.
2. Yeni bir node tipi eklediyse, o tip için kapsam testi yaz.
3. Yeni bir doğrulayıcı eklediyse, pozitif **ve** negatif durum testi yaz.
4. Parser davranışını değiştirdiyse, tam altın test koşumu yap.

Diğer alanlarda:
- Yeni endpoint → sözleşme testi (mutlu yol + yetkisiz + doğrulama hatası).
- Yeni servis metodu → birim testi + bağımlılıkları sahte ile.
- Yeni UI bileşeni → render testi + etkileşim testi + erişilebilirlik testi.
