from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def hello_world(request):
    """
    API endpoint that returns a simple "Hello world!" message.

    Returns:
        Response: JSON object with a "content" key.
    """
    return Response({"content": "Hello world!"})
