# ADR-0001 — YAML Tek Doğruluk Kaynağıdır

- **Durum:** Kabul edildi
- **Tarih:** 2026-09-30
- **Karar verenler:** Proje ekibi

## Bağlam

AnsibleUI, mevcut `Ansible.appAdminConfig` deposunun üzerine görsel bir katman ekler.
Temel soru: **doğruluk kaynağı ne olacak?**

İki seçenek vardı:

1. **Platform kendi modelini tutar**, YAML'ı ondan üretir.
2. **YAML doğruluk kaynağıdır**, platform bir görünüm sunar.

Depoda ~900 YAML dosyası var ve bunların tamamı elle yazılmış. İçlerinde
görselleştirilemeyen çok sayıda yapı bulunuyor: modül değeri içinde Jinja `if/elif/else`
blokları, gömülü PowerShell betikleri, host adına göre dallanan `set_fact` ifadeleri,
`register` üzerinden kurulan örtük bağımlılıklar.

## Karar

**YAML tek doğruluk kaynağıdır. Arayüz yalnızca bir görünümdür.**

Sonuçları:

- Bir dosya açılıp hiçbir değişiklik yapılmadan kaydedildiğinde, dosya
  **byte düzeyinde** değişmemelidir.
- Arayüzün temsil edemediği her yapı `RAW` node olarak korunur ve metin olarak
  düzenlenebilir — asla kaybolmaz veya yeniden üretilmez.
- Depoda elle yapılan değişiklikler arayüzde anında görünür; platform "sahiplik"
  iddia etmez.
- Platform herhangi bir anda devre dışı kalsa, depo tam olarak çalışır durumda kalır.

## Gerekçe

| Kriter | Seçenek 1 (kendi modeli) | Seçenek 2 (YAML) |
|---|---|---|
| Elle yazılmış YAML ile uyum | Bozar | Korur |
| Benimsenme riski | Yüksek — bir kez bozarsa ekip aracı bırakır | Düşük |
| Karmaşık yapıların ele alınması | Ya destekle ya kaybet | Ham olarak koru |
| Git geçmişinin okunabilirliği | Gürültülü diff'ler | Temiz, minimal diff'ler |
| Platform bağımlılığı | Yüksek — platform olmadan depo yönetilemez | Yok |
| Uygulama zorluğu | Düşük | **Yüksek** |

Seçenek 2 teknik olarak belirgin şekilde daha zordur. Fakat seçenek 1'in başarısızlık
modu **projeyi öldürür**: platform bir kez elle yazılmış bir dosyayı bozarsa, ekip
araca bir daha güvenmez.

Ek olarak: bu depo bankacılık üretim sistemlerini yapılandırıyor. Sessiz bir YAML
bozulması ciddi operasyonel sonuç doğurabilir.

## Sonuçlar

**Olumlu**
- Ekip aracı kademeli olarak benimseyebilir; "hepsi ya da hiçbiri" kararı gerekmez.
- Uzman kullanıcılar istedikleri an YAML'a inebilir.
- Diff'ler küçük ve incelenebilir kalır → PR incelemesi anlamlı olur.
- Platform kaldırılırsa depo etkilenmez.

**Olumsuz**
- Parser/serializer katmanı belirgin şekilde daha karmaşık (gölge ağaç yaklaşımı).
- `ruamel.yaml` zorunlu ([ADR-0002](ADR-0002-ruamel-roundtrip.md)).
- Her değişiklikte round-trip'in bozulmadığını kanıtlayan sürekli test gerekir.
- Arayüz bazı yapıları "ham metin" olarak göstermek zorunda — daha az parlak bir demo.

**Riskler**
- Byte düzeyinde koruma beklenenden zor çıkarsa MVP temeli sarsılır.
  Azaltım: WP-10 **ilk** iş paketidir; başarısız olursa yedek plan devreye girer
  (yalnızca platformun oluşturduğu dosyalar yazılabilir, elle yazılanlar salt-okunur).

## Uygulama

- `backend/tests/golden/test_roundtrip_golden.py` — referans depodaki tüm YAML dosyaları
  için byte-identical doğrulaması. **Bu test kırmızıysa hiçbir şey merge edilmez.**
- [docs/04-ansible-ir-spec.md](../04-ansible-ir-spec.md) — IR şartnamesi ve gölge ağaç
  mimarisi.
