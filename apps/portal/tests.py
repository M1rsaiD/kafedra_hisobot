"""
Сквозные проверки личного кабинета и панели заведующего (заменяют
прежний ручной скрипт e2e_portal_test.py): python manage.py test
"""

import datetime
import shutil
import tempfile

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from apps.exporter.tests import add_teacher, make_department
from apps.reports.models import Funding, Publication
from apps.staff.admin import TeacherAdmin
from apps.staff.models import Teacher
from apps.workflow.models import ReportingPeriod

TMP = tempfile.mkdtemp()
User = get_user_model()


@override_settings(MEDIA_ROOT=TMP + "/media", EXPORTS_DIR=TMP + "/exports")
class PortalTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        dept = make_department()
        self.period = ReportingPeriod.objects.create(
            department=dept, period_label="2026-iyun", period_date=datetime.date(2026, 6, 25))
        self.t1 = add_teacher(self.period, "Aliyev Anvar", degree="phd")
        self.t2 = add_teacher(self.period, "Botirov Bobur")
        self.t3 = add_teacher(self.period, "Valiyev Vali")
        for i, t in enumerate([self.t1, self.t2, self.t3], start=1):
            t.user = User.objects.create_user(f"t{i}", password="pass-12345")
            t.save()
        self.c1, self.c2, self.c3 = self.client_class(), self.client_class(), self.client_class()
        self.c1.login(username="t1", password="pass-12345")
        self.c2.login(username="t2", password="pass-12345")
        self.c3.login(username="t3", password="pass-12345")

    def add_publication(self, client=None, **extra):
        data = {
            "reporting_period": self.period.id, "article_title": "Shared article",
            "journal_name": "J", "publish_year": 2026, "citations_count": 0,
            "authors_total": 3, "coauthors": [self.t2.id],
            "article_file": SimpleUploadedFile("a.pdf", b"%PDF-1.4", content_type="application/pdf"),
        }
        data.update(extra)
        return (client or self.c1).post("/kabinet/publications/add/", data, follow=True)

    def test_create_login_admin_action(self):
        t = Teacher.objects.create(department=self.t1.department, full_name="Yangi Xodim")
        request = RequestFactory().post("/admin/staff/teacher/")
        request.session = {}
        request._messages = FallbackStorage(request)
        TeacherAdmin(Teacher, AdminSite()).create_login(request, Teacher.objects.filter(pk=t.pk))
        t.refresh_from_db()
        self.assertIsNotNone(t.user)

    def test_coauthored_publication_visible_to_both_with_share(self):
        r = self.add_publication()
        self.assertEqual(r.status_code, 200)
        pub = Publication.objects.get(article_title="Shared article")
        self.assertEqual(set(pub.authors.all()), {self.t1, self.t2})
        self.assertEqual(str(pub.author_share_display()), "0.33")
        self.assertTrue(pub.article_file)
        self.assertContains(self.c2.get("/kabinet/publications/"), "Shared article")
        self.assertNotContains(self.c3.get("/kabinet/publications/"), "Shared article")
        # соавтор может редактировать, посторонний — нет
        self.assertEqual(self.c2.get(f"/kabinet/publications/{pub.id}/edit/").status_code, 200)
        self.assertEqual(self.c3.get(f"/kabinet/publications/{pub.id}/edit/").status_code, 404)

    def test_total_authors_cannot_be_less_than_department_authors(self):
        r = self.add_publication(authors_total=1)
        self.assertFalse(Publication.objects.exists())
        self.assertContains(r, "id_authors_total")
        self.assertTrue(r.context["form"].errors["authors_total"])

    def test_coauthor_delete_removes_only_self(self):
        self.add_publication()
        pub = Publication.objects.get()
        self.c2.post(f"/kabinet/publications/{pub.id}/delete/")
        self.assertEqual(list(pub.authors.all()), [self.t1])
        self.c1.post(f"/kabinet/publications/{pub.id}/delete/")
        self.assertFalse(Publication.objects.exists())

    def test_closed_period_is_read_only(self):
        self.c1.post("/kabinet/fundings/add/", {
            "reporting_period": self.period.id, "source_type": "business_contract", "amount": "2500000",
        })
        funding = Funding.objects.get(teacher=self.t1)
        self.period.status = ReportingPeriod.Status.SUBMITTED
        self.period.save()
        r = self.c1.get(f"/kabinet/fundings/{funding.id}/edit/")
        self.assertRedirects(r, "/kabinet/fundings/")
        r = self.c1.post(f"/kabinet/fundings/{funding.id}/delete/")
        self.assertTrue(Funding.objects.filter(pk=funding.pk).exists())
        self.assertRedirects(self.c1.get("/kabinet/fundings/add/"), "/kabinet/fundings/")

    def test_hindex_once_per_period(self):
        data = {"reporting_period": self.period.id, "h_index": 3}
        self.c1.post("/kabinet/hindex/add/", data)
        r = self.c1.post("/kabinet/hindex/add/", {**data, "h_index": 4})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.t1.hindex_records.get().h_index, 3)

    def test_profile_saves_own_card_only(self):
        r = self.c1.post("/kabinet/profile/", {
            "birth_date": "1980-05-01", "specialty_name": "01.01.02", "diploma_series": "01",
            "diploma_number": "123456", "hire_order_number": "45-k", "hire_order_date": "2019-09-01",
            "foreign_degree_rank": "", "foreign_master_rank": "",
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(self.t1.hire_order_display, "45-k, 01.09.2019")
        self.assertEqual(self.t2.hire_order_number, "")

    def test_rejects_disallowed_file_type(self):
        r = self.add_publication(article_file=SimpleUploadedFile("x.exe", b"MZ"))
        self.assertFalse(Publication.objects.exists())
        self.assertTrue(r.context["form"].errors["article_file"])

    def test_reports_are_staff_only(self):
        r = self.c1.get(f"/hisobot/{self.period.id}/fayllar/")
        self.assertRedirects(r, "/kabinet/")
        boss = User.objects.create_user("boss", password="x", is_staff=True)
        self.client.force_login(boss)
        self.assertEqual(self.client.get(f"/hisobot/{self.period.id}/").status_code, 200)
        r = self.client.get(f"/hisobot/{self.period.id}/excel/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(".xlsx", r["Content-Disposition"])
        r = self.client.get(f"/hisobot/{self.period.id}/fayllar/")
        self.assertIn("_fayllar.zip", r["Content-Disposition"])

    def test_interface_in_both_languages(self):
        self.client.cookies.load({"django_language": "uz"})
        self.assertContains(self.client.get("/login/"), "<h1>Kirish</h1>", html=False)
        self.client.cookies.load({"django_language": "ru"})
        self.assertContains(self.client.get("/login/"), "<h1>Вход</h1>", html=False)
        self.c1.cookies.load({"django_language": "uz"})
        self.assertContains(self.c1.get("/kabinet/"), "Maqolalar (Scopus)")
