from django.urls import path, include

from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r"note", views.NoteViewSet, basename="note")
router.register(r"tag", views.TagViewSet, basename="tag")

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
    path("api/", include(router.urls)),
]
