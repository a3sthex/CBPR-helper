# 📤 Сюда заливаем книги

**Зачем:** встраиваемый в чат аплоад файлов в агента сломан, а Яндекс.Диск из
агентской песочницы недоступен. GitHub — доступен. Поэтому книги кладём сюда,
обычной загрузкой через браузер.

## Как (2 минуты)

1. На GitHub откройте репозиторий **a3sthex/CBPR-helper** и переключите ветку
   (кнопка выбора ветки слева сверху) на **`arena/01a045ac-cbpr-helper`**.
2. Откройте папку **`uploads/`** → кнопка **Add file → Upload files**.
3. Перетащите PDF-файлы (можно пачкой). Лимит веб-загрузки GitHub —
   **25 МБ на файл**.
4. Внизу нажмите зелёное **Commit changes** (прямо в эту же ветку).

## Какие книги можно залить как есть (≤ 25 МБ)

- CEMK Rule Book.pdf (2,6 МБ)
- CEMK Edgerunners Handbook.pdf (3,7 МБ)
- RTG-CPR-CharacterSheet-Fillable.pdf (1,3 МБ)
- RTG-CPR-DLC-NightMarketIndexv1.24.pdf (4,9 МБ)
- IR1 / IR2 Interface RED (≈6 МБ)
- IR4 Interface RED Vol.4 (17,9 МБ)

## Большие книги (> 25 МБ): IR3, BC Black Chrome, IR5, Corebook

Их GitHub через браузер не примет. Варианты:

- **Если есть git:** положите PDF в эту папку, `git add . && git commit &&
  git push origin arena/01a045ac-cbpr-helper` — командная строка принимает до
  100 МБ на файл (подойдут IR3, BC, IR5; Corebook 145 МБ — нет).
- **Corebook (и всё остальное > 25/100 МБ):** разбейте файл на части по 20 МБ.

  Windows (PowerShell, одна команда, подставьте имя файла):

  ```powershell
  $f="CPR Cyberpunk RED Corebook.pdf"; $fs=[IO.File]::OpenRead($f); $buf=New-Object byte[] 20MB; $i=1; while(($n=$fs.Read($buf,0,$buf.Length)) -gt 0){[IO.File]::WriteAllBytes("$f.part{0:d2}" -f $i, ($n -eq $buf.Length ? $buf : $buf[0..($n-1)])); $i++}; $fs.Close()
  ```

  macOS/Linux:

  ```bash
  split -b 20m "CPR Cyberpunk RED Corebook.pdf" "CPR Cyberpunk RED Corebook.pdf.part"
  ```

  и залейте все полученные `*.partNN` сюда же. Агент сам склеит части обратно.

> После заливки просто напишите в чат «залил» — агент стянет файлы и запустит
> извлечение текста и картинок. Папка `uploads/` намеренно исключена из
> LFS (см. `.gitattributes`), чтобы PDF не превращались в указатели.
