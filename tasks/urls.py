from django.urls import path
from . import views

urlpatterns = [
    path("hello_world/", views.hello_world, name="hello_world"),
    path(
        "api/check_if_email_registered/",
        views.check_if_email_registered,
        name="check_if_email_registered",
    ),
    path("api/send_code/", views.SendCodeView.as_view(), name="send_code"),
    path("api/check_code/", views.CheckCodeView.as_view(), name="check_code"),
    path("api/register/<uuid:token>/", views.RegisterView.as_view(), name="register"),
]
