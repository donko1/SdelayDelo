from django.urls import path, include
from django.conf import settings

from rest_framework import routers

from . import views

router = routers.DefaultRouter()

router.register(r"v1/note", views.NoteViewSet, basename="note_v1")
router.register(r"v2/note", views.NoteViewSetV2, basename="note_v2")
router.register(r"v3/note", views.NoteViewSetV3, basename="note_v3")

router.register(r"note", views.NoteViewSet, basename="note_default")
router.register(r"tag", views.TagViewSet, basename="tag")
router.register(r"icons", views.IconViewSet, basename="icon")


urlpatterns = [
    path("hello_world/", views.hello_world, name="hello_world"),
    path(
        "api/check_if_email_registered/",
        views.check_if_email_registered,
        name="check_if_email_registered",
    ),
    path("api/send_code/", views.send_verification_code, name="send_code"),
    path("api/check_code/", views.verify_code, name="check_code"),
    path("api/register/", views.register_user, name="register"),
    path("api/whoami", views.who_am_i, name="whoami"),
    path("api/reset_password", views.reset_password, name="reset_password"),
    path("api/login", views.login, name="login"),
    path("api/change-userinfo/", views.change_userinfo, name="change-userinfo"),
    path("api/logout", views.logout, name="logout"),
    path("api/get_email_by_username", views.get_email_by_username, name="get_email_by_username"),
    path("api/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns.append(path("api/fast_create_user", views.fast_create_user_for_test, name="fast_create_user_for_test"),)

