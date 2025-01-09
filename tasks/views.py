from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.throttling import AnonRateThrottle

from django.contrib.auth import get_user_model
from django.utils.timezone import now


import uuid

from .models import TokenToEmail
from .serializers import RegisterSerializer


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
@throttle_classes([AnonRateThrottle])
def check_if_email_registered(request):
    email = request.query_params.get("email")
    if not email:
        return Response(
            {"detail": "Email parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email_exists = User.objects.filter(email=email).exists()
    return Response({"email_is_registered": email_exists}, status=status.HTTP_200_OK)


# Send verification code to the provided email
@api_view(["POST"])
@throttle_classes([AnonRateThrottle])
def send_verification_code(request):
    email = request.data.get("email")
    if not email:
        return Response(
            {"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        token = TokenToEmail.objects.create(email=email)
        token.send_verification_email()
        return Response(
            {"detail": "Verification code sent."}, status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@throttle_classes([AnonRateThrottle])
def verify_code(request):
    """
    Verifies the email with the provided 6-digit code and returns a registration token.
    """
    email = request.data.get("email")
    code = request.data.get("code")

    if not email or not code:
        return Response(
            {"detail": "Email and code are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token_obj = TokenToEmail.objects.get(email=email)

        if token_obj.validate_email(code):
            # Generate a new registration token
            raw_token = str(uuid.uuid4())
            token_obj.token_hash = TokenToEmail.hash_token(raw_token)
            token_obj.save(update_fields=["token_hash"])

            return Response(
                {"message": "Email successfully verified.", "token": raw_token},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"detail": "Invalid code or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except TokenToEmail.DoesNotExist:
        return Response(
            {"detail": "No token found for this email."},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["POST"])
@throttle_classes([AnonRateThrottle])
def register_user(request):
    """
    Register a new user using the provided registration token.
    """
    token = request.data.get("token")

    if not token:
        return Response(
            {"detail": "Registration token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Find the token object
        token_obj = TokenToEmail.objects.get(token_hash=TokenToEmail.hash_token(token))

        # Ensure the token is verified and not expired
        if not token_obj.is_verified:
            return Response(
                {"detail": "Email is not verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if token_obj.expires_at < now():
            return Response(
                {"detail": "Registration token has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create a new user
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Remove the token after successful registration
            token_obj.delete()

            # Generate an access token for the user
            user_token = Token.objects.create(user=user)

            return Response(
                {"access_token": user_token.key}, status=status.HTTP_201_CREATED
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except TokenToEmail.DoesNotExist:
        return Response(
            {"detail": "Invalid registration token."},
            status=status.HTTP_400_BAD_REQUEST,
        )
