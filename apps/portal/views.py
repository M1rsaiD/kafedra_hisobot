from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.exporter.archive import collect_documents
from .forms import TeacherProfileForm, build_form_class, open_periods
from .registry import REGISTRY, teacher_queryset


def _teacher_or_none(request):
    return getattr(request.user, "teacher_profile", None)


def _require_teacher(view):
    """Пускает только пользователей, у которых есть привязанная карточка
    Teacher (её создаёт кафедра действием «Создать логин» в admin)."""

    @login_required
    def wrapped(request, *args, **kwargs):
        teacher = _teacher_or_none(request)
        if teacher is None:
            if request.user.is_staff:
                return redirect("dashboard:index")
            return render(request, "portal/no_profile.html", status=403)
        request.teacher = teacher
        return view(request, *args, **kwargs)

    return wrapped


def _cfg_or_404(slug):
    cfg = REGISTRY.get(slug)
    if cfg is None:
        raise Http404
    return cfg


@_require_teacher
def index(request):
    teacher = request.teacher
    periods = open_periods(teacher)
    current = periods.first()

    missing_by_section = {}
    if current:
        for doc in collect_documents(current):
            if teacher.id in doc.teacher_ids and not doc.present:
                missing_by_section[doc.section] = missing_by_section.get(doc.section, 0) + 1

    sections = []
    for slug, cfg in REGISTRY.items():
        qs = teacher_queryset(cfg, teacher)
        sections.append({
            "slug": slug, "title": cfg["title"], "sheet": cfg["sheet"],
            "count": qs.filter(reporting_period=current).count() if current else 0,
            "no_file": qs.filter(Q(**{cfg["file_field"]: ""}) | Q(**{f'{cfg["file_field"]}__isnull': True}),
                                 reporting_period=current).count() if current else 0,
        })

    profile_missing = [
        label for label, ok in [
            (_("дата рождения"), teacher.birth_date),
            (_("скан приказа о приёме"), teacher.hire_order_file),
        ] if not ok
    ]
    snapshot = teacher.period_snapshots.filter(reporting_period=current).first() if current else None
    if snapshot and (snapshot.academic_degree_id or snapshot.academic_title_id) and not teacher.diploma_file:
        profile_missing.append(_("скан диплома"))

    return render(request, "portal/index.html", {
        "teacher": teacher, "sections": sections, "current": current,
        "all_periods": teacher.department.reporting_periods.order_by("-period_date"),
        "profile_missing": profile_missing, "snapshot": snapshot,
    })


@_require_teacher
def profile(request):
    teacher = request.teacher
    if request.method == "POST":
        form = TeacherProfileForm(request.POST, request.FILES, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, _("Данные профиля сохранены."))
            return redirect("portal:index")
    else:
        form = TeacherProfileForm(instance=teacher)
    return render(request, "portal/profile.html", {"form": form})


@_require_teacher
def generic_list(request, slug):
    cfg = _cfg_or_404(slug)
    objects = (teacher_queryset(cfg, request.teacher)
               .select_related("reporting_period").order_by("-reporting_period__period_date", "-id"))
    if cfg.get("authors"):
        objects = objects.prefetch_related("authors")
    model = cfg["model"]
    columns = [(name, model._meta.get_field(name).verbose_name) for name in cfg["list_columns"]]
    return render(request, "portal/list.html", {
        "cfg": cfg, "slug": slug, "objects": objects, "columns": columns,
        "has_open_period": open_periods(request.teacher).exists(),
    })


@_require_teacher
def generic_form(request, slug, pk=None):
    cfg = _cfg_or_404(slug)
    teacher = request.teacher
    periods = open_periods(teacher)

    instance = None
    if pk is not None:
        instance = get_object_or_404(teacher_queryset(cfg, teacher), pk=pk)
        if not instance.reporting_period.is_open:
            messages.error(request, _("Период «%(p)s» уже закрыт — изменения невозможны. "
                                      "Обратитесь к заведующему кафедрой.") % {"p": instance.reporting_period.period_label})
            return redirect("portal:list", slug=slug)
    elif not periods.exists():
        messages.error(request, _("Нет открытого отчётного периода — добавлять записи пока нельзя."))
        return redirect("portal:list", slug=slug)

    FormClass = build_form_class(cfg)

    def make_form(*args):
        form = FormClass(*args, instance=instance,
                         initial=None if instance else {"reporting_period": periods.first()})
        form.fields["reporting_period"].queryset = periods
        form.fields["reporting_period"].empty_label = None
        if cfg.get("authors"):
            form.setup_coauthors(teacher)
        return form

    if request.method == "POST":
        form = make_form(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    if cfg.get("authors"):
                        if cfg.get("creator_field") and not obj.pk:
                            setattr(obj, cfg["creator_field"], teacher)
                        obj.save()
                        form.save_authors(obj)
                    else:
                        setattr(obj, cfg["teacher_field"], teacher)
                        obj.save()
            except IntegrityError:
                form.add_error(None, _("Такая запись за этот период уже есть — отредактируйте её."))
            else:
                messages.success(request, _("Сохранено."))
                return redirect("portal:list", slug=slug)
    else:
        form = make_form()

    return render(request, "portal/form.html", {
        "form": form, "cfg": cfg, "slug": slug, "object": instance,
        "file_field": cfg.get("file_field"),
    })


@_require_teacher
@require_POST
def generic_delete(request, slug, pk):
    cfg = _cfg_or_404(slug)
    teacher = request.teacher
    obj = get_object_or_404(teacher_queryset(cfg, teacher), pk=pk)
    if not obj.reporting_period.is_open:
        messages.error(request, _("Период уже закрыт — удаление невозможно."))
        return redirect("portal:list", slug=slug)
    if cfg.get("authors") and obj.authors.exclude(pk=teacher.pk).exists():
        # у общей записи остаются другие авторы кафедры — убираем только себя
        obj.authors.remove(teacher)
        messages.success(request, _("Вы убраны из авторов; у соавторов запись сохранилась."))
    else:
        obj.delete()
        messages.success(request, _("Запись удалена."))
    return redirect("portal:list", slug=slug)
