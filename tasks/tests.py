from django.test import TestCase
from django.urls import reverse


class HelloWorldViewTest(TestCase):
    def test_hello_world_returns_correct_json(self):
        """
        Check if GET to hello_world returns correct JSON.
        """
        response = self.client.get(reverse("hello_world"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"content": "Hello world!"})

    def test_hello_world_rejects_post(self):
        """
        Check if POST to hello_world return error 405 (Method Not Allowed).
        """
        response = self.client.post(reverse("hello_world"))
        self.assertEqual(response.status_code, 405)
