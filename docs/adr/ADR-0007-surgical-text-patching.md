# ADR-0007 — Yeniden Üretim Yerine Cerrahi Metin Yaması

- **Durum:** Kabul edildi
- **Tarih:** 2026-09-30
- **İlgili:** [ADR-0001](ADR-0001-yaml-source-of-truth.md) ·
  [ADR-0002](ADR-0002-ruamel-roundtrip.md) (bu ADR ile daraltıldı)

## Bağlam

[ADR-0002](ADR-0002-ruamel-roundtrip.md), `ruamel.yaml` round-trip modunun dosyaları
byte düzeyinde koruyacağını **varsayıyordu**. Bu varsayım WP-10 başlangıcında
referans deponun tamamına karşı ölçüldü.

### Ölçüm (2026-09-30, `Ansible.appAdminConfig`, 477 YAML dosyası)

`parse → dump` (tam yeniden üretim) sonucu:

| Girinti ayarı | Birebir aynı | Oran |
|---|---|---|
| `mapping=2, sequence=4, offset=2` | 0 / 477 | **%0,0** |
| `mapping=2, sequence=2, offset=0` | 5 / 477 | **%1,0** |
| `mapping=2, sequence=4, offset=0` | 0 / 477 | **%0,0** |

Başlıca kayıp nedenleri:

1. **`---` belge başlangıç işareti düşüyor.** Depodaki dosyaların çoğu `---` ile başlıyor.
2. **Kök seviyesindeki diziler içeri giriyor.** `- name: ...` → `  - name: ...`
3. **Dosya içinde karma girinti.** Aynı dosyada bir liste 2, diğeri 4 boşluk girintili:
   ```yaml
     vars:
       state: present
       appList:
           - product_id: "Notepad++"     # 4 boşluk offset
       paths:
         - 'D:\WebSites'                 # 2 boşluk offset
   ```
   `ruamel.yaml` girintiyi **koleksiyon başına değil, belge genelinde** tek ayarla
   uygular. Karma girintili bir dosya hiçbir global ayarla yeniden üretilemez.
4. Satır sonu boşlukları ve yorum hizalamaları.

Bu, bir ayar meselesi değil; tam yeniden üretim yaklaşımının **yapısal sınırıdır**.

### İkinci ölçüm: konum bilgisi

`ruamel.yaml`'ın `compose()` API'si, her düğüm için kaynak metindeki tam karakter
aralığını (`start_mark.index`, `end_mark.index`) veriyor:

| Ölçüt | Sonuç |
|---|---|
| Ayrıştırılan dosya | 474 / 477 |
| Çıkarılan düğüm | 18.981 |
| Geçersiz/tutarsız aralık | **0** |

Ayrıştırılamayan 3 dosya, referans depodaki **gerçekten bozuk** dosyalardır
(bkz. aşağıdaki "Yan Bulgular").

## Değerlendirilen Seçenekler

| # | Seçenek | Sonuç |
|---|---|---|
| A | Tam yeniden üretim (ADR-0002'nin varsaydığı) | **Reddedildi** — %0-1 başarı |
| B | Girinti ayarını dosya başına tespit et | **Reddedildi** — karma girintili dosyalarda yine imkânsız |
| C | Yalnızca platformun ürettiği dosyalar yazılabilir, geri kalanı salt-okunur | **Reddedildi** — mevcut 477 dosyanın hiçbiri düzenlenemezdi; ürünün ana vaadi kaybolurdu |
| D | **Cerrahi metin yaması** | **Seçildi** |

## Karar

**Gerçeğin kaynağı orijinal metnin kendisidir. `ruamel.yaml` yalnızca *okuma* ve
*konum tespiti* için kullanılır; yazma işlemi orijinal metin üzerinde hedefli
karakter aralığı değişimiyle yapılır.**

```
okuma:   metin --ruamel.compose()--> düğüm ağacı + karakter aralıkları --> IR
yazma:   IR değişikliği --> TextEdit(start, end, yeni_metin) --> orijinal metne uygula
```

Bunun doğrudan sonuçları:

1. **Değiştirilmemiş dosya için gidiş-dönüş tanım gereği birebirdir.** Hiçbir
   düzenleme yoksa uygulanacak yama yoktur; çıktı girdinin aynısıdır.
2. **Diff her zaman minimaldir.** Yalnızca dokunulan aralık değişir; dosyanın
   geri kalanı — yorumlar, girinti, tırnaklar, boş satırlar — hiç işlenmez bile.
3. **Anlaşılmayan yapı zarar görmez.** Bir düğüm ayrıştırılamıyorsa üzerine yama
   yazılmaz; metinde olduğu gibi kalır.

### Yazma sonrası doğrulama (değişmedi)

Yama uygulandıktan sonra üretilen metin **yeniden ayrıştırılır** ve şunlar kontrol edilir:

- Metin geçerli YAML mi?
- Yalnızca hedeflenen düğümün değeri mi değişti? (diğer tüm düğümler anlamsal olarak aynı)

Doğrulama başarısızsa yazma iptal edilir ve `RoundTripError` fırlatılır.

### ADR-0002'de neyin geçerli kaldığı

| Kural | Durum |
|---|---|
| PyYAML yasak | ✓ Geçerli |
| `typ="safe"` / `typ="unsafe"` yasak | ✓ Geçerli |
| `typ="rt"` + `preserve_quotes` kullanılır | ✓ Geçerli — okuma ve değer üretimi için |
| Elle string birleştirerek YAML üretme | ✓ Hâlâ yasak — değer üretimi `ruamel` ile yapılır |
| **`yaml.dump` ile tüm dosyayı yeniden yazma** | ✗ **Artık yasak** — yerine `TextEdit` |

Yani `ruamel.yaml` kaldırılmıyor; **görev alanı daraltılıyor**. Yeni bir YAML
parçası (örneğin bir liste öğesi) üretilirken yine `ruamel` kullanılır, ancak
üretilen parça dosyanın tamamının yerine değil, yalnızca hedef aralığın yerine geçer.

## Gerekçe

Ölçüm, A seçeneğinin çalışmadığını kesin olarak gösterdi. D seçeneği aynı hedefe
(kayıpsızlık) daha güçlü bir garantiyle ulaşıyor: koruma artık bir kütüphanenin
yeniden üretim sadakatine değil, **dokunmama** ilkesine dayanıyor.

Bu aynı zamanda [docs/14](../14-testing-strategy.md) bölüm 2.2'deki yama
sözleşmesini (`len(added) == 1, removed == []`) doğal olarak sağlar.

## Sonuçlar

**Olumlu**
- Kayıpsızlık garantisi kütüphaneye değil, yaklaşımın kendisine bağlı.
- Diff gürültüsü sıfır.
- Ayrıştırılamayan dosyalar bile kısmen görüntülenebilir (salt-okunur).
- Daha hızlı: yazma işlemi tüm ağacı serileştirmiyor.

**Olumsuz**
- Yeni içerik **ekleme** daha zor: girinti ve konum elle hesaplanmalı. Bir liste
  öğesi eklerken komşu öğelerin girintisi ölçülüp taklit edilir.
- Aynı anda birden fazla düzenleme yapılırken aralıklar çakışabilir. Çözüm: yamalar
  konuma göre **tersten** uygulanır ve çakışanlar reddedilir.
- Düğüm kimliklerinin (pointer) değişiklikten sonra yeniden hesaplanması gerekir.

**Riskler**
- Aralık hesabında bir hata dosyayı bozabilir. Azaltım: yazma sonrası doğrulama
  zorunlu, altın testler bloklayıcı.

## Yan Bulgular

Ölçüm sırasında referans deponun kendisinde **3 bozuk YAML dosyası** tespit edildi:

| Dosya | Hata |
|---|---|
| `playbooks/PowerFactoreCore/prod-dmz.yml` | `mapping values are not allowed here` |
| `playbooks/PowerFactoreCore/test-dmz.yml` | `mapping values are not allowed here` |
| `playbooks/winservices/install_FileBeat.yml` | `found undefined alias 'card_hsm'` |

Bunlar bir kusur değil, **platformun ilk somut faydasıdır**: bu dosyalar
`ansible-lint` veya bir CI adımı olmadığı için fark edilmemiş. Platform bu
dosyaları "ayrıştırılamadı" olarak işaretler, salt-okunur gösterir ve depo sağlık
panosunda (WP-86) listeler.

## Uygulama

- `backend/app/ansible/roundtrip.py` — `parse_document`, `TextEdit`, `apply_edits`
- Altın testler: `backend/tests/golden/test_roundtrip.py`
- Etkilenen dokümanlar: [04-ansible-ir-spec.md](../04-ansible-ir-spec.md),
  [14-testing-strategy.md](../14-testing-strategy.md)
