# Kafedra hisoboti / Отчётность кафедры

Платформа для сбора рейтинговой отчётности кафедры по форме
**«Umumiy kafedra reytingi» (редакция 2026, 20 листов: 1,1 … 4,3 и 5)**.

- Каждый преподаватель в **личном кабинете** сам вносит свои данные и
  прикладывает подтверждающие файлы к каждой записи (диплом, приказ, PDF
  статьи, патент, договор, приказ о командировке и т.д.).
- Заведующий кафедрой видит **ход заполнения** (у кого что внесено и каких
  файлов не хватает) и скачивает **отдельно**:
  - **Excel** — готовый отчёт по официальной форме, все 20 листов;
  - **ZIP** — все загруженные преподавателями файлы, разложенные по папкам
    разделов, плюс реестр `_fayllar_royxati.xlsx` (что приложено, чего нет).
- Статьи и патенты/свидетельства — **общие записи с соавторами**: каждому
  автору кафедры засчитывается доля **1/N**, где N — общее число авторов
  работы (2 автора → по 0.5, 3 → по 0.33). Доли идут в своды 2,1 / 2,4 / 2,5.
- Интерфейс **на двух языках — узбекском (латиница) и русском**,
  переключатель в шапке; по умолчанию узбекский.

## O‘zbekcha qisqacha

**Kafedra hisoboti** — «Umumiy kafedra reytingi» (2026-yil tahriri, 20 ta varaq)
shakli bo‘yicha kafedra hisobotini yig‘ish platformasi.

- Har bir o‘qituvchi **shaxsiy kabinetida** (`/kabinet/`) o‘z ma’lumotlarini
  kiritadi va har bir yozuvga tasdiqlovchi faylni ilova qiladi (diplom,
  buyruq, maqola PDF, patent, shartnoma, xizmat safari buyrug‘i va h.k.).
- Kafedra mudiri (`/hisobot/`) kim nimani kiritganini va qaysi fayllar
  yetishmayotganini ko‘radi hamda **alohida** yuklab oladi:
  - **Excel** — rasmiy shakl bo‘yicha tayyor hisobot, barcha 20 varaq;
  - **ZIP** — o‘qituvchilar yuklagan barcha fayllar bo‘limlar bo‘yicha
    papkalarda va `_fayllar_royxati.xlsx` ro‘yxati (nima bor, nima yo‘q).
- Maqola va patentlar — **hammualliflar bilan umumiy yozuv**: kafedraning har
  bir muallifiga **1/N** ulush hisoblanadi (N — mualliflarning umumiy soni):
  2 muallif — 0.5 dan, 3 muallif — 0.33 dan. Ulushlar 2,1 / 2,4 / 2,5-varaqlarga
  tushadi.
- Interfeys **o‘zbek (lotin) va rus tillarida**, sahifa yuqorisida
  almashtirgich bor; standart til — o‘zbekcha.
- Hisobot davri «Qoralama» holatida bo‘lganda kiritish ochiq; «Kelishuvga
  yuborildi» deb belgilangach, o‘qituvchilar yozuvlarni o‘zgartira olmaydi.
- Qo‘lda to‘ldirilgan Excel faylni `python manage.py import_report ...`
  buyrug‘i bilan yuklash mumkin (batafsil — quyida, rus tilida).

Ishga tushirish:

```bash
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## Роли

| Кто | Где | Что делает |
|---|---|---|
| Преподаватель | `/kabinet/` | Профиль (листы 1,1–1,4: дата рождения, диплом, приказ о приёме, зарубежные дипломы, гражданство) и разделы: статьи (2,1–2,2), h-индекс (2,3), патенты/DGU (2,4–2,5), средства (2,6), защиты (2,7), репутация (3,1), мобильность (3,4). Видит и правит только свои записи (и общие — где он соавтор). |
| Заведующий / сотрудник кафедры (`is_staff`) | `/hisobot/` | Ход заполнения по преподавателям, проверка перед сдачей, кнопки **Excel** и **Файлы (ZIP)**. |
| Заведующий | `/admin/` | Отчётные периоды, штатная ведомость (лист 5), логины преподавателей, студенты/выпускники (листы 3,2 / 3,3 / 3,5 / 4,x), справочники. |

### Отчётный период

Ввод открыт, пока период в статусе «Черновик». Действие «Отправить на
согласование» в админке закрывает ввод: преподаватели видят записи, но не
могут их менять. «Вернуть в черновик» снова открывает ввод.

### Как преподаватель получает доступ

1. `/admin/staff/teacher/` → отметить преподавателей → действие
   «Создать логин в личном кабинете».
2. Логин и одноразовый пароль показываются **один раз** — передайте их лично.
3. Преподаватель входит на сайт (`/login/`) и попадает в свой кабинет.

## Быстрый старт

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # по умолчанию SQLite

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Перенос уже заполненной таблицы

Если отчёт за период уже набран вручную в Excel по форме 2026, его можно
загрузить — преподавателям останется проверить свои записи и приложить файлы:

```bash
python manage.py import_report "Umumiy kafedra reytingi 2026.xlsx" \
    --department "Amaliy matematika va informatika kafedrasi" \
    --period 2026-iyun --date 2026-06-25 \
    --faculty "…" --university "…"          # нужны, только если кафедры ещё нет в БД
```

Переносятся: штатная ведомость (5), дипломы и приказы (1,1), даты рождения
(1,2), статьи с цитированиями (2,2; одна статья у нескольких преподавателей
становится одной записью с соавторами), h-индекс (2,3), средства (2,6),
репутация (3,1), мобильность студентов (3,3) и ППС (3,4). Из листов 2,4 / 2,6
/ 3,1 / 3,4, где в форме только числа, создаются записи-заготовки с пометкой
«Exceldan import — aniqlang / импорт из Excel — уточните». Квартили (2,1)
преподаватель указывает у каждой статьи сам — свод пересчитается с долями.
ФИО сопоставляются между листами нечётко (кириллица/латиница, q/k, x/h).
`--replace` перезаписывает данные периода при повторном импорте.

### Выгрузка из командной строки

```bash
python manage.py export_report <id_кафедры> 2026-iyun --with-files
# exports/<кафедра>_<период>.xlsx и exports/<кафедра>_<период>_fayllar.zip
```

## Как устроен экспорт

- `apps/exporter/templates_store/kafedra_hisobot_template.xlsx` — **чистый
  бланк** формы 2026 (без персональных данных). Для каждого листа: шапка,
  строка-прототип заголовка секции (если есть), строка-прототип данных,
  строка-прототип итога «Jami», подвал (примечание «*…ilova qilinadi»,
  подпись «Rektor»). В шапке — подстановки `{kafedra}`, `{sana}`, `{shtat}`.
- `apps/exporter/layout.py` — собирает тело листа заново: строк столько,
  сколько людей/статей (без ограничения шаблоном), стиль и объединения
  ячеек копируются из прототипов, подвал переносится под последнюю строку.
- `apps/exporter/sheets.py` — заполнение всех 20 листов (`SHEET_FILLERS`,
  колонки описаны у каждой функции). Показатели листов 1–3 считаются для
  основного штата и внутренних совместителей; записи преподавателей, которых
  нет в штатной ведомости периода, не теряются молча — попадают в
  «Проверку перед сдачей» на странице хода заполнения.
- `apps/exporter/archive.py` — ZIP с файлами по разделам и реестр.

Показатели уровня кафедры (выделенные штатные единицы, общее число
студентов и выпускников) задаются в карточке отчётного периода.

## Переводы

Строки в коде — на русском, узбекский перевод — `locale/uz/LC_MESSAGES/django.po`.
После изменения строк:

```bash
python scripts/i18n_extract.py            # добавить новые строки в .po
# перевести пустые msgstr в locale/uz/LC_MESSAGES/django.po
python scripts/i18n_extract.py --compile  # собрать .mo (GNU gettext не нужен)
```

## Тесты

```bash
python manage.py test
```

Проверяются доли 1/N, все 20 листов, перенос подвала при любом числе строк,
архив файлов, импорт (экспорт → импорт даёт те же данные), изоляция
кабинетов, закрытые периоды, доступ к отчётам только для сотрудников,
оба языка интерфейса.

## Переход на MySQL (сервер)

В `.env`: `DB_ENGINE=mysql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`,
`DB_PORT`; `DEBUG=False`, свой `SECRET_KEY` и `ALLOWED_HOSTS`. Схема не
меняется, `mysqlclient` уже в `requirements.txt`.

## Что важно знать при эксплуатации

- **Файлы преподавателей** (`media/`) при `DEBUG=False` Django не отдаёт —
  на сервере их нужно раздавать через nginx. Ссылки на файлы не защищены
  паролем: тот, кто знает точный URL, сможет открыть файл. Если это важно
  (сканы дипломов), закройте `media/` в nginx и отдавайте файлы через
  проверку прав (X-Accel-Redirect).
- **Права по кафедрам**: все сотрудники с `is_staff` видят все кафедры. Для
  нескольких кафедр на одном сервере нужна фильтрация по кафедре пользователя.
- **Свидетельства DGU** хранятся и уходят в архив, но в лист 2,4 не
  засчитываются (в заголовке формы их нет) — это одна строка
  `Patent.SHEET_2_4_TYPES`, если методика скажет иначе.
