# 12 — Yapay Zekâ Asistanı (Faz 7)

> Bu bölüm **MVP kapsamı dışındadır**. Mimari, bu yetenek sonradan eklenebilecek
> şekilde tasarlanmıştır; bu doküman o tasarımı sabitler.

## 1. Amaç

Ansible bilmeyen kullanıcının, ne istediğini **doğal dille** anlatarak çalışan bir
playbook taslağına ulaşabilmesi.

> «Yeni bir isube test sunucusu kur: IIS kurulsun, sertifikalar yüklensin,
> 24 app pool ve 25 uygulama oluşturulsun.»

## 2. Temel Güvenlik İlkesi

> **Yapay zekâ hiçbir zaman doğrudan yazma veya çalıştırma yapamaz.**

Her çıktı şu zinciri geçmek zorundadır:

```
LLM çıktısı
   → IR'ye ayrıştırma          (geçerli yapı değilse reddedilir)
   → Şema doğrulaması          (rol parametreleri şemaya uymalı)
   → Doğrulayıcılar (V001-V010)
   → Canvas'ta önizleme
   → İNSAN ONAYI               ← burada durur
   → Taslak
   → Diff → PR → insan merge
   → Pipeline çalıştırma (ayrıca yetki + onay gerekir)
```

Yapay zekâ, kullanıcının **zaten sahip olduğu** yetkilerin ötesine geçemez.
Bu, LLM'in yanılmasını (hallucination) zararsız hâle getirir: en kötü durumda
kullanıcı reddedeceği bir taslak görür.

## 3. Model ve Erişim

| Konu | Değer |
|---|---|
| Model | Kurum içi **Qwen** (büyük varyant) |
| Protokol | OpenAI uyumlu `POST /v1/chat/completions` |
| Erişim | Yalnızca pod → iç endpoint; veri kurum dışına çıkmaz |
| İstemci | `httpx` (mevcut bağımlılık) |
| Soyutlama | `app/ai/provider.py` — sağlayıcı değişimi tek dosyada kalır |

```python
class LLMProvider(Protocol):
    async def complete(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse: ...
```

Zaman aşımı, yeniden deneme, token bütçesi ve maliyet/kullanım sayacı bu katmanda.

## 4. Bağlam Üretimi

Vektör veritabanı **kullanılmaz**. Depo küçüktür (65 rol, 120 playbook) ve bağlam
deterministik olarak üretilebilir — bu daha doğru ve denetlenebilir sonuç verir.

```
Kullanıcı isteği
   │
   ├─ Anahtar kelime çıkarımı ("isube", "IIS", "sertifika", "app pool")
   │
   ├─ İlgili rol şemaları           (en fazla 15 rol, tam parametre listesiyle)
   ├─ Benzer playbook örnekleri     (en fazla 3, tam içerikle)
   ├─ Envanter grupları             (yalnızca adlar ve host sayıları)
   ├─ Vault değişken ADLARI         (değer YOK)
   └─ Doğrulayıcı kuralları özeti   (V001-V010)
        │
        ▼
   Sistem istemi + kullanıcı mesajı → LLM
```

### Bağlama Girmeyenler

| Girmez | Neden |
|---|---|
| Vault **değerleri** | Erişim zaten yok |
| Host adları (üretim) | Gereksiz bilgi yayılımı; yalnızca grup adları verilir |
| Kullanıcı kimlikleri, parolalar | Gereksiz |
| Ham build log'ları | Hata açıklayıcı dışında gereksiz; o da maskelenmiş verilir |

## 5. Özellikler

### WP-72 — Doğal Dilden Playbook

LLM'den **YAML değil, yapılandırılmış IR taslağı** istenir:

```json
{
  "intent": "yeni isube test sunucusu kurulumu",
  "target_group": "test_isube",
  "steps": [
    {"role": "create_dir", "params": {"paths": ["D:\\WebSites\\..."]}},
    {"role": "features_for_iis", "params": {}},
    {"role": "importCertificate", "params": {"certPath": "..."}}
  ],
  "notes": ["Sertifika parolasi icin uat_boa_standardyeni_cert_password kullanildi"]
}
```

Neden YAML değil?
- Yapılandırılmış çıktı şema ile doğrulanabilir; YAML metni doğrulanamaz.
- IR'ye çevirmek, serializer'ın biçim garantilerini korur.
- Yanlış yapıdaki çıktı **ayrıştırma aşamasında** reddedilir, kullanıcıya hiç ulaşmaz.

Sonuç canvas'ta önizlenir; kullanıcı node bazında kabul/ret edebilir.

### WP-73 — Hata Açıklayıcı

Başarısız çalıştırmanın **maskelenmiş** log'u verilir; çıktı:

```
Ne oldu   : copyFile_Multiple gorevi stlisube2 sunucusunda basarisiz oldu.
Neden     : \\appfiles\DSC\... paylasimina erisilemedi (Access Denied).
Oneri     : Sunucunun paylasim yetkisini kontrol edin veya
            sunucunun domain uyeligini dogrulayin.
Ilgili    : roles/copyFile_Multiple/tasks/main.yml
```

Bu, "log'da bir şey aramak" ile "ne yapacağını bilmek" arasındaki farkı kapatır.

### WP-74 — Değişiklik Gözden Geçirme

Yayınlama öncesi diff LLM'e verilir; riskli desenler işaretlenir:
- Üretim etkisi yüksek değişiklikler (port, binding, sertifika)
- Diğer sube rolleriyle tutarsızlık
- Dosyalar arası kopan eşleşmeler

Çıktı **öneri niteliğindedir**; yayınlamayı engellemez (doğrulayıcılar engeller).

### WP-70/71/75 — Altyapı

| WP | İçerik |
|---|---|
| WP-70 | LLM soyutlama, timeout, retry, token bütçesi, istem (prompt) log'u |
| WP-71 | Bağlam üretici |
| WP-75 | Güvenlik bariyerleri ve denetim |

## 6. İstem (Prompt) Tasarımı

Sistem istemi şunları sabitler:
1. Rol — «Sen bu kurumun Ansible deposunu bilen bir yardımcısın.»
2. Kısıtlar — «Yalnızca sana verilen rolleri kullan. Yeni rol veya modül uydurma.»
3. Çıktı biçimi — JSON şeması, kesin.
4. Bilinen tuzaklar — «`createWebSiteApp` `@recursive` varyantında `appNames`
   nesne listesidir.» «`create_dir` listesi `appNames` listesini kapsamalıdır.»
5. Dil — «Açıklamalar Türkçe.»

Tüm istemler `app/ai/prompts/` altında **dosya olarak** tutulur; kod içinde gömülmez.
Bu, sürüm kontrolü ve gözden geçirmeyi mümkün kılar.

## 7. Denetim ve Şeffaflık

| Kayıt | Amaç |
|---|---|
| Kullanıcı isteği | Ne soruldu |
| Kullanılan bağlam özeti | Hangi roller/playbook'lar verildi |
| Model ve sürüm | Tekrarlanabilirlik |
| Token kullanımı ve süre | Maliyet takibi |
| Kullanıcı kararı | Kabul / kısmen kabul / ret |

Yapay zekâ üretimi taslaklar arayüzde **açıkça işaretlenir** ve commit mesajında belirtilir:

```
AnsibleUI-AI-Assisted: true
AnsibleUI-AI-Model: qwen-...
```

PR'ı inceleyen kişi, içeriğin yapay zekâ destekli olduğunu bilmelidir.

## 8. Başarısızlık Modları

| Mod | Önlem |
|---|---|
| Olmayan rol uydurma | Şema doğrulaması reddeder; kullanıcıya «bilinmeyen rol» denir |
| Yanlış parametre tipi | Şema doğrulaması reddeder |
| Geçersiz JSON | Ayrıştırma reddeder; bir kez düzeltme istenir, sonra vazgeçilir |
| Makul görünen ama yanlış yapılandırma | Doğrulayıcılar + insan onayı |
| Secret sızdırma girişimi | Secret bağlama hiç girmez; sızdıracak veri yok |
| İstem enjeksiyonu (playbook içeriğinden) | Depo içeriği **veri** olarak işaretlenir, talimat olarak değil; sistem istemi bunu açıkça belirtir |
| Model erişilemez | Özellik zarifçe devre dışı kalır; platformun geri kalanı çalışır |

## 9. Etkinleştirme

Yapay zekâ özellikleri varsayılan olarak **kapalıdır** (`ANSIBLEUI_AI_ENABLED=false`).
Etkinleştirmek için endpoint, model adı ve API anahtarı yapılandırılmalıdır.
Kapalıyken ilgili arayüz öğeleri hiç gösterilmez.

## 10. Başarı Ölçütü

Yapay zekâ özelliği şu koşulda başarılıdır:

> Kullanıcıların çoğu, yapay zekâ taslağını **düzenleyerek** kullanıyor —
> sıfırdan yazmak veya tamamen reddetmek yerine.

Ölçüm: kabul oranı, kabul sonrası düzenleme miktarı, taslaktan PR'a dönüşme oranı.
Bu metrikler denetim kayıtlarından hesaplanır.
