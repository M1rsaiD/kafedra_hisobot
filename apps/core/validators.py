"""
Общие валидаторы загружаемых файлов. Подтверждающие документы (дипломы,
статьи, договоры, приказы) уходят в итоговый архив отчёта, поэтому
принимаем только «документные» форматы и ограничиваем размер — иначе один
случайно загруженный видеофайл раздует архив всей кафедры.
"""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

ALLOWED_DOCUMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx", "zip", "rar"]
MAX_UPLOAD_MB = 25

validate_document_extension = FileExtensionValidator(ALLOWED_DOCUMENT_EXTENSIONS)


def validate_document_size(value):
    if value and value.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(
            _("Файл слишком большой (максимум %(mb)s МБ).") % {"mb": MAX_UPLOAD_MB}
        )


DOCUMENT_VALIDATORS = [validate_document_extension, validate_document_size]
