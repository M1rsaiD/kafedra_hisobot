"""
Извлечение строк для перевода и сборка .po/.mo без GNU gettext.

Django-команды makemessages/compilemessages требуют установленного GNU
gettext (xgettext/msgfmt), которого обычно нет на Windows-машинах кафедры.
Этот скрипт делает то же самое на чистом Python (нужен только polib):

    python scripts/i18n_extract.py          # обновить locale/uz/LC_MESSAGES/django.po
    python scripts/i18n_extract.py --compile # + собрать django.mo

Строки в коде — на русском (msgid), узбекский перевод — в django.po.
Русский каталог (locale/ru) собирается автоматически с msgstr = msgid:
без него Django для непереведённых строк подставлял бы язык по
умолчанию (узбекский) даже при выбранном русском.
Существующие переводы при обновлении сохраняются, новые строки
добавляются пустыми — их нужно перевести и снова запустить с --compile.
"""

import ast
import re
import sys
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parent.parent
PO_PATH = ROOT / "locale" / "uz" / "LC_MESSAGES" / "django.po"
RU_PATH = ROOT / "locale" / "ru" / "LC_MESSAGES" / "django.po"
GETTEXT_NAMES = {"_", "_g", "gettext", "gettext_lazy", "pgettext"}


def from_python(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in GETTEXT_NAMES and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                yield arg.value, f"{path.relative_to(ROOT)}:{node.lineno}"


TRANS_RE = re.compile(r'{%\s*(?:translate|trans)\s+"((?:[^"\\]|\\.)*)"')
BLOCK_RE = re.compile(r"{%\s*blocktrans(?:late)?\b[^%]*%}(.*?){%\s*endblocktrans(?:late)?\s*%}", re.S)
VAR_RE = re.compile(r"{{\s*(\w+)\s*}}")


def from_template(path):
    text = path.read_text(encoding="utf-8")
    for m in TRANS_RE.finditer(text):
        yield m.group(1), f"{path.relative_to(ROOT)}:{text[:m.start()].count(chr(10)) + 1}"
    for m in BLOCK_RE.finditer(text):
        msgid = VAR_RE.sub(lambda v: f"%({v.group(1)})s", m.group(1))
        yield msgid, f"{path.relative_to(ROOT)}:{text[:m.start()].count(chr(10)) + 1}"


def collect():
    found = {}
    for path in sorted(ROOT.glob("apps/**/*.py")) + sorted(ROOT.glob("config/*.py")):
        if "migrations" in path.parts:
            continue
        for msgid, where in from_python(path):
            found.setdefault(msgid, []).append(where)
    for path in sorted(ROOT.glob("**/templates/**/*.html")):
        for msgid, where in from_template(path):
            found.setdefault(msgid, []).append(where)
    return found


def main():
    found = collect()
    old = polib.pofile(str(PO_PATH)) if PO_PATH.exists() else None
    old_tr = {e.msgid: e.msgstr for e in old} if old else {}

    po = polib.POFile()
    po.metadata = {
        "Project-Id-Version": "kafedra_hisobot",
        "Language": "uz",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
        "Plural-Forms": "nplurals=1; plural=0;",
    }
    for msgid, places in found.items():
        entry = polib.POEntry(msgid=msgid, msgstr=old_tr.get(msgid, ""),
                              occurrences=[tuple(p.rsplit(":", 1)) for p in places])
        if "%(" in msgid:
            entry.flags.append("python-format")
        po.append(entry)
    PO_PATH.parent.mkdir(parents=True, exist_ok=True)
    po.save(str(PO_PATH))
    missing = [e.msgid for e in po if not e.msgstr]
    print(f"{len(po)} строк, без перевода: {len(missing)} → {PO_PATH.relative_to(ROOT)}")
    ru = polib.POFile()
    ru.metadata = dict(po.metadata, Language="ru",
                       **{"Plural-Forms": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : "
                                          "n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"})
    for e in po:
        ru.append(polib.POEntry(msgid=e.msgid, msgstr=e.msgid, flags=list(e.flags)))
    RU_PATH.parent.mkdir(parents=True, exist_ok=True)
    ru.save(str(RU_PATH))

    if "--compile" in sys.argv:
        po.save_as_mofile(str(PO_PATH.with_suffix(".mo")))
        ru.save_as_mofile(str(RU_PATH.with_suffix(".mo")))
        print("django.mo собраны (uz, ru)")
    return missing


if __name__ == "__main__":
    main()
