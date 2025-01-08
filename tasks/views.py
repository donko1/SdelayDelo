from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import TokenToEmail
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model

User = get_user_model()


@api_view(["GET"])
def hello_world(request):
    """
    API endpoint that returns a simple "Hello world!" message.

    Returns:
        Response: JSON object with a "content" key.
    """
    return Response({"content": "Hello world!"})


@api_view(["GET"])
def check_if_email_registered(request):
    """
    API endpoint that return false if email had an account
    """  #
    email = request.query_params.get("email")
    if not email:
        return Response(
            {"error": "Email parameter is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    email_is_registered = User.objects.filter(email=email).exists()
    return Response(
        {"email_is_registered": email_is_registered}, status=status.HTTP_200_OK
    )


class SendCodeView(APIView):
    """
    API endpoint to send a verification code to the user's email.
    """

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        token_obj, created = TokenToEmail.objects.get_or_create(email=email)
        if created:
            token_obj.send_verification_email()
        return Response(
            {"message": "Verification code sent."}, status=status.HTTP_200_OK
        )


class CheckCodeView(APIView):
    """
    API endpoint to verify the code and return a token.
    """

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        token_obj = get_object_or_404(TokenToEmail, email=email, code=code)
        return Response({"token": token_obj.token}, status=status.HTTP_200_OK)


class RegisterView(APIView):
    """
    API endpoint to register a user and provide an access token.
    """

    def post(self, request, token):
        token_obj = get_object_or_404(TokenToEmail, token=token)
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create a user
        user = User.objects.create_user(
            username=username, email=token_obj.email, password=password
        )
        token_obj.delete()
        access_token, created = Token.objects.get_or_create(user=user)
        return Response(
            {"access_key": access_token.key}, status=status.HTTP_201_CREATED
        )
