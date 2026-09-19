# Промпты для фото персонажа · NC//NET · 2070

Паспорт героя (общий для обоих кадров) — чтобы один и тот же человек получился и в досье, и на улице.

## Паспорт (вставляй в оба промпта, если генератор не держит контекст)

- Мужчина **~30 лет**, худощавый, подтянутый, спортивный — без качка и лишней массы
- **Короткие тёмные волосы**, ёжик / военный полубокс, аккуратная щетина 2 дня
- Сломанный нос (сросся чуть криво), **шрам через левую бровь**, следы химического ожога на правой кисти
- Взгляд холодный, спокойный, «протокольный»; поза ровная, руки спокойны
- Одежда: поношенная тёмная куртка поверх простой футболки; на плече полуоторванный патч NCPD
- Fashionware: тонкие **светящиеся красные линии** (EMP Threading) на левом предплечье, выцветшая татуировка-значок NCPD
- Один seed на оба кадра, чтобы лицо совпадало: `207701`

---

## Промпт №1 — под лист (досье, чёрно-красный HUD)

Кадр «полицейское фото при оформлении»: чёрный фон, красный ключевой свет, янтарная подсветка — попадает в палитру листа.

**EN**
```
Photorealistic police intake photograph, waist-up, front view. A lean, wiry 30-year-old man
with close-cropped dark hair (short buzz cut), high cheekbones, a crooked broken nose,
a thin scar through his left eyebrow, light two-day stubble and a faint chemical burn scar
across the knuckles of his right hand. He stares straight into the lens, calm and unreadable,
jaw set, shoulders square. Wearing a worn dark tactical jacket over a plain grey shirt and
a half-ripped NCPD patch on the shoulder. Background: flat matte black wall with a faint red
technical grid. Lighting: hard crimson key light from the left edge, thin amber rim light on
the right, cool white frontal flash on the face. Shot on 35mm, f/2.8, shallow depth of field,
fine film grain, high contrast, deep blacks, restrained palette of black, red, white and amber,
municipal database aesthetic.
```
**Negative**
```
text, letters, numbers, watermark, signature, logo, UI, cartoon, illustration, anime, 3d render,
plastic skin, oversaturated colors, pink or purple lighting, deformed hands, extra fingers,
extra limbs, blurred, low-res, jpeg artifacts, smiling, wrinkles, grey hair, full beard, elderly,
bulky muscles, bodybuilder
```
**Настройки:** Midjourney `--ar 16:9 --style raw --seed 207701` · SDXL/Flux: шаги 30, CFG 6, seed 207701

---

## Промпт №2 — обычный (улица Найт-Сити, ночь)

Тот же человек, тот же seed — «живой» кадр для портфолио, аватарки или поста.

**EN**
```
Photorealistic cinematic three-quarter portrait of a lean, athletic 30-year-old man standing
in a rain-slick Night City street at night. Short dark buzz-cut hair, crooked broken nose,
thin scar through his left eyebrow, light stubble; the same faded burn scar on his right hand
holding a cigarette. Worn black carbon-weave jacket, collar up, thin glowing red lines tattooed
along his left forearm, faded NCPD tattoo. Behind him: wet asphalt, blurred neon signage in
red, amber and white, steam from a vent, distant police drone strobe. Cinematic anamorphic look,
35mm, f/2, shallow depth of field, volumetric haze, rain in the air, hard rim light, deep blacks,
fine film grain. He looks slightly past the camera, jaw set, unbothered.
```
**Negative**
```
text, letters, numbers, watermark, signature, logo, cartoon, illustration, anime, 3d render,
plastic skin, oversaturated colors, neon pink and cyan overload, deformed hands, extra fingers,
extra limbs, blurred, low-res, jpeg artifacts, smiling, wrinkles, grey hair, full beard, elderly,
bulky muscles, bodybuilder, crowd in focus
```
**Настройки:** Midjourney `--ar 16:9 --style raw --seed 207701` · SDXL/Flux: шаги 30, CFG 6, seed 207701

---

## Как вставить в лист

1. Генерируй в **16:9** (или 2:1) — рамка фото в досье широкая, **460×250** (~1.84:1).
2. Обрежь по центру лица, чтобы глаза были в верхней трети кадра.
3. В Google Таблицах: правый клик по заглушке «ФОТО ОБЪЕКТА» → **Заменить изображение** → выбрать файл.
4. Если хочешь оба кадра: №1 — в самый лист (он в палитре досье), №2 — в лог дел или в пост про персонажа.

## Если генератор промахивается

| Что не так | Что добавить в промпт |
| --- | --- |
| Вышел старик | `30 years old, youthful sharp features, no wrinkles, no grey hair` |
| Вышел качок | `slim wiry build, lean, narrow shoulders, no heavy muscles` |
| Длинные волосы | `very short buzz cut, cropped hair, military haircut` |
| Лицо «пластиковое» | `natural skin texture, pores, photojournalism, documentary photo` |
| Слишком неоново | `muted palette, black white red amber only, low saturation, no cyan, no magenta` |
| Руки сломаны | убрать руки из кадра: `hands out of frame, waist-up crop` |

---

## Проверенные примеры (лежат рядом в папке `sheets/`)

| Файл | Что это |
| --- | --- |
| `demo-photo-01-dose.png` | Промпт №1 как есть — фото «при оформлении», чёрно-красный HUD |
| `demo-photo-02-street.png` | Промпт №2 как есть — улица, ночь, дождь |
| `demo-photo-02-street-v2.png` | Вариант 2 в режиме **image-to-image**: за основу взят кадр из досье, поэтому это тот же человек |
| `photo-dose-crop.png` / `photo-street-crop.png` | те же кадры, обрезанные ровно под рамку досье **460×250** — можно вставлять как есть |

**Как получить «того же человека»** (важнее, чем текст промпта):

- Midjourney: сделать кадр №1, затем №2 с `--cref <ссылка на кадр №1> --cw 20 --seed 207701 --ar 16:9 --style raw`;
- Stable Diffusion / Flux / ComfyUI: image-to-image с кадром №1, denoise 0.45–0.6, либо тот же seed + ControlNet/IP-Adapter по лицу;
- фотошоп-путь: тот же seed в текстовом режиме даёт похожий типаж, но лицо всё равно уедет — надёжнее перечисленные выше способы.

---

## Досье без плашки (итоговый кадр)

Первый кадр понравился, но плашка с именем/делом в кадре не нужна — данные и так подписаны в самом листе. Промпт-правка (image-to-image от `demo-photo-01-dose.png`):

```
Edit this exact photograph. Remove the identification placard with the name and case numbers
from the background completely, and remove every printed text, barcode, height marker and
measuring marking from the walls and frame edges. Keep the man absolutely identical: same face,
same buzz-cut hair, same crooked nose, scar through left eyebrow, same stubble, same pose, same
worn dark tactical jacket over grey shirt, same NCPD patch on his shoulder, same lighting —
hard crimson key light from the left, thin amber rim light on the right, cool white frontal flash.
The background must become a clean matte black wall with only a very faint dark red technical grid,
no letters and no numbers anywhere. Photorealistic, 35mm, fine film grain, deep blacks, high
contrast, black-red-white-amber palette. Absolutely no text, no watermark, no logos.
```
→ результат: `photo-dossier-full.png`, он же обрезан под рамку листа (`photo-dose-fit.jpg`, 509×338 px) и **вставлен в 01 ДОСЬЕ**.

## Не в форме: три комплекта (лицо то же — все сделаны от `photo-dossier-full.png`)

### №3 — улица, гражданское
```
Keep exactly this man's face and features: lean, wiry 30-year-old, short dark buzz-cut hair,
crooked broken nose, thin scar through the left eyebrow, two-day stubble. Show him out of uniform,
in civilian street clothes: worn black leather jacket over a dark grey hoodie, matte black t-shirt,
worn dark jeans, a plain wristwatch, no police patches, no insignia, no badges anywhere.
Rain-slick Night City street at night, three-quarter portrait, thin glowing red lines tattooed
along his left forearm. Background: wet asphalt reflecting blurred neon in red, amber and white,
steam from a vent, distant passing cars. Cinematic anamorphic, 35mm, f/2, volumetric haze, rain,
hard rim light, deep blacks, film grain, black-red-white-amber, no cyan.
```
→ `photo-civ-street.png` — «по улице, но не на службе»

### №4 — дома, в контейнере
```
Keep exactly this man's face and features: lean, wiry 30-year-old, short dark buzz-cut hair,
crooked broken nose, thin scar through the left eyebrow, two-day stubble. Scene: at home in a
repurposed cargo container apartment in the combat zone, warm amber work lamp as the only light,
a kettle and a folding table with scattered papers and an old case folder. He is out of uniform:
plain dark grey t-shirt, open olive-grey canvas work jacket, worn jeans, dog tags, no police
patches. He sits on a crate, elbows on knees, looking off frame, weary but composed, mug of coffee
in hand. Thin glowing red lines along his left forearm. 35mm, f/2, deep blacks, amber and red
palette, film grain, documentary mood.
```
→ `photo-civ-home.png` — «жильё — грузовой контейнер», совпадает с E11 в досье

### №5 — корпоративный район (undercover)
```
Keep exactly this man's face and features: lean, wiry 30-year-old, short dark buzz-cut hair,
crooked broken nose, thin scar through the left eyebrow, two-day stubble. He is working undercover,
out of uniform: dark charcoal blazer over a plain black t-shirt, no tie, no police patches, no
insignia, no badges. Corporate plaza at night, three-quarter portrait, hands in pockets, calm and
watchful, thin glowing red lines along his left forearm peeking from the sleeve. Background: glass
and dark steel towers, blurred amber and red accent lighting, faint holographic glow, wet pavement,
a few out-of-focus pedestrians. Cinematic, 35mm, f/2, deep blacks, black-red-white-amber, film grain.
```
→ `photo-civ-suit.png` — «по делу в корпоративном районе»

Общее для №3–№5: в negative добавляй `NCPD patch, police badge, uniform, insignia, text, letters, numbers, watermark, logo`.
