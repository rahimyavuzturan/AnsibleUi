---
description: "Use when writing React, TypeScript or Tailwind code in the frontend: components, hooks, data fetching with TanStack Query, forms with Zod, state management and accessibility."
applyTo: "frontend/**"
---

# Frontend React Kuralları

> Ekran tasarımları ve Türkçe terim sözlüğü:
> [docs/10-ui-ux-spec.md](../../docs/10-ui-ux-spec.md)

## Klasör Düzeni

```
src/
  app/            # kok bilesen, router, saglayicilar
  features/       # dikey dilimler: catalog, inventory, editor, publish, runs, admin
    <feature>/
      api/        # bu ozellige ait sorgu/mutasyon hook'lari
      components/
      hooks/
      types.ts
  components/ui/  # shadcn tabanli paylasilan bilesenler
  lib/            # api istemcisi, yardimcilar
```

Bir özellik dilimi başka bir dilimin `components/` klasöründen import etmez.
Paylaşım gerekiyorsa `components/ui/` veya `lib/` altına taşınır.

## Durum Yönetimi

| Durum türü | Araç |
|---|---|
| Sunucu verisi | TanStack Query — `useState` + `useEffect` ile veri çekme **yok** |
| Canvas / editör durumu | Zustand store |
| Form durumu | react-hook-form + Zod |
| URL durumu | React Router arama parametreleri |

```tsx
// DOGRU
const { data, isLoading, error } = useRoleSchema(roleName);

// YANLIS
const [data, setData] = useState(null);
useEffect(() => { fetch(...).then(r => r.json()).then(setData); }, []);
```

## TypeScript

- `strict: true`; `any` yasak, kaçınılmazsa `unknown` + daraltma.
- API tipleri `src/lib/api.ts` içinde tek yerde tanımlı; kopyalanmaz.
- Bileşen prop'ları açıkça tiplenir; `React.FC` kullanılmaz.

## Bileşen Kuralları

1. Her veri gösteren bileşen **dört durumu** karşılar: yükleniyor, boş, hata, dolu.
2. İskelet (skeleton) tercih edilir; sayfa boyu spinner kullanılmaz.
3. Yıkıcı işlemler onay diyaloğu ister ve sonucu açıkça söyler.
4. `dangerouslySetInnerHTML` yasak.
5. Kullanıcıya görünen tüm metin **Türkçe**; kod ve değişken adları İngilizce.
6. Ham hata gövdesi ekrana basılmaz; `error.code` Türkçe mesaja eşlenir.

## Erişilebilirlik

- Etkileşimli öğeler gerçek `button` / `a` etiketleri.
- Tüm form alanlarında `label` bağlantısı.
- Odak halkası kaldırılmaz.
- Renk tek başına anlam taşımaz; ikon veya metin eşlik eder.

## Performans

- Rol kataloğu ve envanter listeleri sanallaştırılır.
- Monaco ve canvas görünümleri `React.lazy` ile bölünür.
- Ağır hesaplar `useMemo`; ama her şeyi ezbere memoize etme.

## Bitti Tanımı

- [ ] `npm run lint && npm run typecheck` temiz
- [ ] `npm run test` yeşil; yeni bileşen için Testing Library testi var
- [ ] Dört durum (yükleniyor/boş/hata/dolu) karşılanıyor
- [ ] Yeni metinler Türkçe ve [docs/10](../../docs/10-ui-ux-spec.md) sözlüğüyle uyumlu
- [ ] Klavye ile kullanılabiliyor
