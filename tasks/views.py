from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.response import Response
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.exceptions import PermissionDenied

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.timezone import now
from django.conf import settings

import uuid

from .models import TokenToEmail
from .serializers import RegisterSerializer
from .throttles import WhoAmIRateThrottle


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
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def check_if_email_registered(request):
    """
    Check if the provided email is registered in the system.

    This function is intended **only** for testing and development purposes.
    It allows quick verification of whether an email is registered in the database.

    This endpoint is disabled in production environments (when DEBUG = False).

    Arguments:
    - `email` (str): The email address to check. This should be provided as a query parameter.

    Returns:
    - 200 OK: If the request is valid, the response contains a boolean indicating
      whether the email is registered.
    - 400 Bad Request: If the `email` parameter is missing.
    - 403 Forbidden: If the endpoint is accessed in production.

    Example usage:
    ```
    GET /api/check_if_email_registered?email=test@example.com
    Response: { "email_is_registered": true }
    ```

    """
    if not settings.DEBUG:
        raise PermissionDenied("This endpoint is disabled in production.")
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
@throttle_classes([AnonRateThrottle, UserRateThrottle])
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
        print(e)
        return Response(
            {"detail": "An error occurred."}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["POST"])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
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

        if token_obj.validate_email(code) and not token_obj.is_verified:
            # Generate a new registration token
            raw_token = str(uuid.uuid4())
            token_obj.token_hash = TokenToEmail.hash_token(raw_token)
            token_obj.is_verified = True
            token_obj.save(update_fields=["token_hash", "is_verified"])

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
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def reset_password(request):
    """
    Reset password using token
    """

    token = request.data.get("token")
    password = request.data.get("new_password")

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

        user = User.objects.filter(email=token_obj.email)[0]
        try:
            if validate_password(password=password) is None:
                user.password = password
                user.save()
                token_obj.delete()
                return Response(
                    {"detail": "new password had set"}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"detail": "password is not valid"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValidationError:
            return Response(
                {"detail": "password is not valid"}, status=status.HTTP_400_BAD_REQUEST
            )
    except TokenToEmail.DoesNotExist:
        return Response(
            {"detail": "Invalid registration token."},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
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


@api_view(["POST"])
@throttle_classes([UserRateThrottle, AnonRateThrottle])
def login(request):
    """
    view to login by username and password
    """
    password = request.data.get("password")
    username = request.data.get("username")
    if not username:
        email = request.data.get("email")

    if not password or (username is None and email is None):
        return Response({"detail": "Ur data is not correct"}, status=400)

    if username:
        user = User.objects.filter(username=username)[0]
    else:
        user = User.objects.filter(email=email)[0]
    if user.password != password:
        return Response({"detail": "Not correct username or password"}, status=400)

    else:
        try:
            access_token = Token.objects.get(user=user)

        except Token.DoesNotExist:
            access_token = Token.objects.create(user=user)
        return Response(
            {"access_token": access_token.key},
            status=200,
        )


@api_view(["GET"])
@throttle_classes([WhoAmIRateThrottle])
def who_am_i(request):

    if request.user.is_authenticated:
        return Response(
            {"user": {"email": request.user.email, "username": request.user.username}},
            status=status.HTTP_200_OK,
        )
    else:
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
