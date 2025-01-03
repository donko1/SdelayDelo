from django.test import TestCase
from django.urls import reverse


class HelloWorldViewTest(TestCase):
    def test_hello_world_returns_correct_json(self):
        response = self.client.get(reverse("hello_world"))

        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(response.content, {"content": "Hello world!"})
