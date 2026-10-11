---
description: "Use when working on the AI assistant feature (Phase 7): local Qwen LLM integration, prompt building, context assembly, output validation and audit trail."
applyTo: "backend/app/ai/**,frontend/src/features/ai/**"
---

# Yapay Zekâ Asistanı Kuralları

> Faz 7 özelliğidir; önceki fazlar tamamlanmadan geliştirilmez.
> Tasarım: [docs/12-ai-assistant.md](../../docs/12-ai-assistant.md)

## Değişmez Güvenlik İlkesi

**Model hiçbir şeyi doğrudan yazmaz ve çalıştırmaz.**

```
model cevabi → IR'e ayristir → dogrulayicilar → kullaniciya fark ekrani → insan onayi → taslak
```

Bu zincirin herhangi bir adımını atlayan kod yazılmaz. Model çıktısı,
kullanıcı girdisiyle **aynı** doğrulama yolundan geçer; ayrıcalığı yoktur.

## Kurallar

1. **Varsayılan kapalı.** `ANSIBLEUI_AI_ENABLED=false`. Kapalıyken hiçbir
   LLM çağrısı yapılmaz ve arayüzde özellik görünmez.

2. **Yalnızca kurum içi model.** OpenAI uyumlu protokolle yerel Qwen uç noktası.
   Dış servise (api.openai.com vb.) giden çağrı **yasak**.

3. **Sağlayıcı soyutlaması.** Tüm çağrılar `LLMProvider` protokolü üzerinden.
   İş mantığının içine doğrudan HTTP istemcisi gömülmez.

4. **Bağlama asla girmeyecekler:**
   - Vault dosyası içeriği veya herhangi bir sır
   - Gerçek parolalar, PAT, sertifika parolası
   - Tam envanter (sunucu adları ve IP'ler) — yalnızca grup adları
   - Kullanıcı kimlik bilgileri

5. **Bağlam deterministik üretilir.** Vektör veritabanı yok. İlgili rol şemaları
   ve benzer playbook örnekleri kural tabanlı seçilir; seçim mantığı test edilebilir.

6. **Çıktı ayrıştırılamıyorsa gösterilmez.** Serbest metin YAML kullanıcıya
   sunulmaz; yalnızca doğrulanmış IR yamaları önerilir.

7. **Şeffaflık zorunlu.** AI üretimi içerik arayüzde açıkça işaretlenir ve
   commit'e trailer eklenir:
   ```
   AnsibleUI-AI-Assisted: true
   AnsibleUI-AI-Model: qwen2.5-coder-32b
   ```

8. **Prompt enjeksiyonu varsayılır.** Depodaki YAML yorumları bağlama girer ve
   talimat içerebilir. Sistem prompt'u, bağlam içeriğinin talimat olmadığını
   açıkça belirtir; model çıktısı yine de doğrulayıcılara tabidir.

9. **Zaman aşımı ve geri çekilme.** LLM çağrısı zaman aşımına uğrarsa özellik
   sessizce devre dışı kalır; uygulamanın geri kalanı etkilenmez.

10. **Denetim kaydı.** Her çağrı `audit_log`'a yazılır: kullanıcı, istem özeti,
    model, süre, kabul edildi mi. İstem tam metni saklanmaz (boyut bütçesi).

## Bitti Tanımı

- [ ] Özellik bayrağı kapalıyken hiçbir yan etki yok (test edildi)
- [ ] Model çıktısının doğrulayıcılardan geçtiğini kanıtlayan test
- [ ] Bağlama sır sızmadığını doğrulayan test
- [ ] Prompt enjeksiyonu senaryosu için test
- [ ] Dış uç noktaya çağrı olmadığını doğrulayan test
