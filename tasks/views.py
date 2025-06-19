from rest_framework.decorators import (
    api_view,
    throttle_classes,
    permission_classes,
    action,
)
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.exceptions import PermissionDenied
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.utils.timezone import now
from django.conf import settings

import uuid
import logging
from datetime import date
from datetime import datetime 
from dateutil.parser import isoparse

from .models import TokenToEmail, Note, Tag
from .serializers import (
    RegisterSerializer,
    NoteSerializer,
    TagSerializer,
    UserUpdateSerializer,
    IconUploadSerializer,
)
from .throttles import (
    WhoAmIRateThrottle,
    NoteAndTagThrottleRead,
    NoteAndTagThrottleWrite,
    IconThrottle,
)

from .paginators import NotePagination

User = get_user_model()

logger = logging.getLogger(__name__)


def format_email(email):
    """format email to fa2 login"""
    email_1_part = email.split("@")[0]
    email_1_part = email_1_part[0] + "*" * (len(email_1_part) - 2) + email_1_part[-1]
    return email_1_part + "@" + email.split("@")[-1]


@api_view(["GET"])
def hello_world(request):
    """
    API endpoint that returns a simple "Hello world!" message.

    Returns:
        Response: JSON object with a "content" key.
    """
    logger.info("hello_world endpoint called")
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
        logger.warning("check_if_email_registered endpoint called in production")
        raise PermissionDenied("This endpoint is disabled in production.")
    email = request.query_params.get("email")
    if not email:
        logger.error("Email parameter is required for check_if_email_registered")
        return Response(
            {"detail": "Email parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email_exists = User.objects.filter(email=email).exists()
    logger.info(f"Email {email} is registered: {email_exists}")
    return Response({"email_is_registered": email_exists}, status=status.HTTP_200_OK)


# Send verification code to the provided email
@api_view(["POST"])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def send_verification_code(request):
    email = request.data.get("email")
    if settings.EMAIL_EXISTS:
        if not email:
            logger.error("Email is required for send_verification_code")
            return Response(
                {"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = TokenToEmail.objects.create(email=email)
            token.send_verification_email()
            logger.info(f"Verification code sent to {email}")
            return Response(
                {"detail": "Verification code sent."}, status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error sending verification code to {email}: {e}")
            return Response(
                {"detail": "An error occurred."}, status=status.HTTP_400_BAD_REQUEST
            )
    return Response(
        {"detail": "Server need an email configuration. Check local settings"},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def verify_code(request):
    """
    Verifies the email with the provided 6-digit code and returns a registration token.
    """
    if settings.EMAIL_EXISTS:
        email = request.data.get("email")
        code = request.data.get("code")

        if not email or not code:
            logger.error("Email and code are required for verify_code")
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
                token_obj.is_verified = True
                token_obj.save(update_fields=["token_hash", "is_verified"])

                logger.info(f"Email {email} successfully verified")
                return Response(
                    {"message": "Email successfully verified.", "token": raw_token},
                    status=status.HTTP_200_OK,
                )
            elif token_obj.is_verified:
                logger.info("Code is verified")
                return Response(
                    {"detail":"Code is verified"},
                    status=status.HTTP_200_OK)
            else:
                logger.warning(f"Invalid code or expired token for email {email}")
                return Response(
                    {"detail": "Invalid code or expired token."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except TokenToEmail.DoesNotExist:
            logger.error(f"No token found for email {email}")
            return Response(
                {"detail": "No token found for this email."},
                status=status.HTTP_404_NOT_FOUND,
            )

    logger.error("Trying verify code but email settings are not correct")
    return Response(
        {"detail": "Server need an email configuration. Check local settings"},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def reset_password(request):
    """
    Reset password using token
    """

    if settings.EMAIL_EXISTS:

        token = request.data.get("token")
        password = request.data.get("new_password")

        if not token:
            logger.error("Registration token is required for reset_password")
            return Response(
                {"detail": "Registration token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Find the token object
            token_obj = TokenToEmail.objects.get(
                token_hash=TokenToEmail.hash_token(token)
            )

            # Ensure the token is verified and not expired
            if not token_obj.is_verified:
                logger.warning(f"Email {token_obj.email} is not verified")
                return Response(
                    {"detail": "Email is not verified."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if token_obj.expires_at < now():
                logger.warning(
                    f"Registration token for email {token_obj.email} has expired"
                )
                return Response(
                    {"detail": "Registration token has expired."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.filter(email=token_obj.email).first()

            if not user:
                logger.error(f"User with email {token_obj.email} was not found")
                return Response(
                    {"detail": "User with this email was not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                if validate_password(password=password) is None:
                    user.password = make_password(password)  # Хешируем пароль
                    user.save()
                    token_obj.delete()
                    logger.info(f"Password reset for user {user.username}")
                    return Response(
                        {"detail": "New password has been set"},
                        status=status.HTTP_200_OK,
                    )
                else:
                    logger.warning(f"Password is not valid for user {user.username}")
                    return Response(
                        {"detail": "Password is not valid"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except ValidationError:
                logger.warning(f"Password validation failed for user {user.username}")
                return Response(
                    {"detail": "Password is not valid"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except TokenToEmail.DoesNotExist:
            logger.error(f"Invalid registration token for reset_password")
            return Response(
                {"detail": "Invalid registration token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    return Response(
        {"detail": "Server need an email configuration. Check local settings"},
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
        logger.error("Registration token is required for register_user")
        return Response(
            {"detail": "Registration token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Find the token object
        token_obj = TokenToEmail.objects.get(token_hash=TokenToEmail.hash_token(token))

        # Ensure the token is verified and not expired
        if not token_obj.is_verified:
            logger.warning(f"Email {token_obj.email} is not verified")
            return Response(
                {"detail": "Email is not verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if token_obj.expires_at < now():
            logger.warning(
                f"Registration token for email {token_obj.email} has expired"
            )
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

            logger.info(f"User {user.username} registered successfully")
            return Response(
                {"access_token": user_token.key}, status=status.HTTP_201_CREATED
            )
        else:
            errors = serializer.errors
            logger.error(f"Registration failed for user with token {token}")
            if "{'password': [ErrorDetail(string='Убедитесь, что это значение содержит не менее 8 символов.', code='min_length')]}" in str(errors):
                logger.error(f"Password less than 8 symbols")
                return Response({"detail":"password_8_symbols"}, status=status.HTTP_400_BAD_REQUEST)
            if "This username is already registered" in str(errors):
                logger.error(f"Username isnt uniq")
                return Response({"detail":"username_isnt_uniq"}, status=status.HTTP_400_BAD_REQUEST)
            logger.error(f"UnknownError: {errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except TokenToEmail.DoesNotExist:
        logger.error(f"Invalid registration token for register_user")
        return Response(
            {"detail": "Invalid registration token."},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle, AnonRateThrottle])
def change_userinfo(request) -> Response:
    """
    Updates user info (telegram_id, fa_2).  Accepts PATCH requests.
    """
    user = request.user  # Get the authenticated user

    serializer = UserUpdateSerializer(
        instance=user, data=request.data, partial=True
    )  # partial=True allows partial updates

    if serializer.is_valid():
        serializer.save()  # Calls the `update` method in the serializer
        logger.info(f"User information updated for {user.username}")
        logger.info(f"Was updated: {serializer.data}")
        return Response(
            {"detail": "User information updated successfully."},
            status=status.HTTP_200_OK,
        )
    else:
        logger.error(
            f"Failed to update user information for {user.username}\n Validation errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@throttle_classes([UserRateThrottle, AnonRateThrottle])
def login(request):
    """
    view to login by username/email and password
    """
    password = request.data.get("password")
    username = request.data.get("username")
    token = request.data.get("token")

    if not username:
        email = request.data.get("email")

    if username:
        user = User.objects.filter(username=username)[0]
        email = user.email
    else:
        user = User.objects.filter(email=email)[0]

    if token:
        token_obj = TokenToEmail.objects.get(token_hash=TokenToEmail.hash_token(token))
        if not token_obj.is_verified:
            logger.warning(f"Email {token_obj.email} is not verified")
            return Response(
                {"detail": "Email is not verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if token_obj.expires_at < now():
            logger.warning(
                f"Registration token for email {token_obj.email} has expired"
            )
            return Response(
                {"detail": "Registration token has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_by_token = User.objects.filter(email=token_obj.email)[0]
        if user_by_token == user:

            try:
                access_token = Token.objects.get(user=user)

            except Token.DoesNotExist:
                access_token = Token.objects.create(user=user)

            logger.info(f"User {user.username} logged in successfully with token")
            return Response(
                {"access_token": access_token.key}, status=status.HTTP_200_OK
            )
        else:
            logger.error(f"Token is not correct for user {user.username}")
            return Response(
                {"detail": "token is not correct"}, status=status.HTTP_400_BAD_REQUEST
            )

    if not password or (username is None and email is None):
        logger.error("Invalid login data provided")
        return Response({"detail": "Ur data is not correct"}, status=400)

    if not check_password(password, user.password):
        logger.warning(f"Invalid password for user {user.username}")
        return Response({"detail": "Not correct username or password"}, status=400)

    if not user.fa_2:
        access_token = Token.objects.get_or_create(user=user)[0]
        logger.info(f"User {user.username} logged in successfully")

        return Response(
            {"access_token": access_token.key},
            status=200,
        )

    if settings.EMAIL_EXISTS:
        token = TokenToEmail.objects.create(email=email)
        token.send_verification_email()
        url_check_code = reverse("check_code")
        email = format_email(email)
        logger.info(f"2FA initiated for user {user.username}")
        return Response(
            {"detail": f"Now visit {url_check_code} to continue", "email": email},
            status=202,
        )

    return Response(
        {"detail": "Server need an email configuration. Check local settings"},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["GET"])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def get_email_by_username(request):
    """
    This function returns email by username
    """
    try:
        username = request.GET.get("username")
        logger.debug(f"Getting email by username: {username}")
        assert username is not None
    except AssertionError:
        return Response({"detail":"No username in request"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(username=username)
    if user:
        return Response({"email":user[0].email}, status=status.HTTP_200_OK)
    return Response({"detail":"No user with this username"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@throttle_classes([WhoAmIRateThrottle])
def who_am_i(request):
    """
    This function returns information about the authenticated user.

    Parameters:
    request: The request object containing user information.

    Returns:
    A JSON response with user information if the user is authenticated.
    If the user is not authenticated, a JSON response with an error message is returned.

    Example:
    {
        "user": {
            "email": "user@example.com",
            "username": "user123",
            "telegram_id": "123456789",
            "fa_2": true,
            "theme": "dark",
            "language": "en",
            "timezone": "America/New_York"
        }
    }
    """
    user = request.user
    if request.user.is_authenticated:
        logger.info(f"who_am_i called by authenticated user {user.username}")
        if settings.DEBUG or settings.TESTING:
            logger.info("Returns debug information")
            return Response(
                {
                    "user": {
                        "email": user.email,
                        "username": user.username,
                        "telegram_id": user.telegram_id,
                        "fa_2": user.fa_2,
                        "theme": user.theme,
                        "language": user.language,
                        "timezone": user.timezone,
                        "mode": "DEBUG",
                    }
                },
                status=status.HTTP_200_OK,
            )

        logger.info("Returns production information")
        return Response(
            {
                "user": {
                    "theme": user.theme,
                    "language": user.language,
                    "timezone": user.timezone,
                    "mode": "PRODUCTION",
                    "username": user.username,

                }
            }
        )

    else:
        logger.warning("who_am_i called by unauthenticated user")
        return Response(
            {"user": {
            "usernme":"Guest"
            }},
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Logout the authenticated user and returns a success message.
    """
    user = request.user
    if user.is_authenticated:
        logger.info(f"User {user.username} logged out")
        user.auth_token.delete()  # Deletes the authentication token for the user
        return Response({"detail": "User logged out successfully."}, status=200)
    else:
        logger.warning("User tried to log out but was not authenticated")
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED,
        )


if settings.DEBUG:
    @api_view(["POST"])
    def fast_create_user_for_test(request):
        """
        Fast create user and return key to access. Need to testing next part
        """
        password = request.data.get("password")
        username = request.data.get("username")
        email = request.data.get("email")
        logger.info(f"Fast creating user with {email} for {username}")

        user = User.objects.create(
            username=username, email=email
        )

        user.set_password(password) 
        user.save()
 

        access_token_user = Token.objects.create(user=user).key

        return Response({"detail":"Access token created", "token":access_token_user}, status=status.HTTP_200_OK)

class NoteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the Note model.
    Provides CRUD operations (Create, Retrieve, Update, Delete) for notes.
    Only authenticated users can access this ViewSet.
    Users can only view and modify their own notes.
    Methods:
        get_queryset(): Returns a queryset of notes that belong to the current user.
        perform_create(serializer): Saves a new note, setting the owner to the current user.
        perform_update(serializer): Updates an existing note, verifying that the current user is the owner.
        perform_destroy(instance): Deletes a note, verifying that the current user is the owner.
    """

    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [NoteAndTagThrottleRead, NoteAndTagThrottleWrite]

    def get_queryset(self):
        """
        Returns a queryset of notes that belong to the current user.
        """
        user = self.request.user
        logger.debug(f"Fetching notes for user {user.username}")
        
        if self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            return Note.objects.get_all().filter(user=user)
        
        return Note.objects.filter(user=user)

    def perform_create(self, serializer):
        """
        Saves a new note, setting the owner to the current user.
        """
        try:
            serializer.save(user=self.request.user)
            logger.info(f"Note created for user {self.request.user.username}")
        except Exception as e:
            logger.error(
                f"Error creating note for user {self.request.user.username}: {e}"
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        """
        Updates an existing note, verifying that the current user is the owner.
        Raises PermissionDenied if the current user is not the owner.
        """
        try:
            instance = self.get_object()  
            logger.debug(f"Updating {instance.id}")
            serializer.save()
            logger.info(f"Note updated for user {self.request.user.username}")
        
        except ObjectDoesNotExist:
            logger.error(f"Note not found for user {self.request.user.username}")
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Update error: {e}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_destroy(self, instance):
        """
        Deletes a note, verifying that the current user is the owner.
        Raises PermissionDenied if the current user is not the owner.
        """
        try:
            if instance.user != self.request.user:
                logger.warning(
                    f"User {self.request.user.username} tried to delete a note they do not own"
                )
                raise PermissionDenied("You can't delete this object, it is not yours!")
            instance.delete()
            logger.info(f"Note deleted for user {self.request.user.username}")
        except PermissionDenied as e:
            logger.error(
                f"Permission denied for user {self.request.user.username}: {e}"
            )
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            logger.error(f"Note not found for user {self.request.user.username}")
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(
                f"Error deleting note for user {self.request.user.username}: {e}"
            )
            return Response(
                {"detail": "An error occurred"}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], url_path="unarchived")
    def shows_unarchived(self, request):
        return Response(
            {"detail": "This method is only in v3+ versions"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class NoteViewSetV2(NoteViewSet):
    """
    ViewSet for the Note model, version 2.
    Inherits from NoteViewSet and adds additional functionality.
    """

    pagination_class = NotePagination

    def get_queryset(self):
        """
        Returns a queryset of notes that belong to the current user and are not archived.
        """
        queryset = super().get_queryset()
        
        if self.action == 'list':
            queryset = queryset.filter(is_archived=False)
            logger.debug("Applied V2 filter: is_archived=False")
        
        return queryset



class NoteViewSetV3(NoteViewSetV2):
    """
    ViewSet for the Note model, version 3.
    Inherits from NoteViewSetV2 and adds additional functionality.
    """

    @action(detail=False, methods=["get"], url_path="archived")
    def shows_archived(self, request):
        """
        Shows only archived notes
        """
        user = request.user
        logger.debug(f"Fetching archived notes for user {user.username}")

        queryset = Note.objects.archived(user=user)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"], url_path="my_day")
    def show_my_day(self, request):
        """
        Shows only unarchived and my_day notes
        """
        user = self.request.user
        today = date.today()
        logger.debug(f"Fetching my day for user {user.username}")

        queryset = Note.objects.filter(user=user, is_archived=False, date_of_note=today)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)

        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["delete"], url_path="clear_archive")
    def clear_archive(self, request):
        """
        Clear archive
        """
        user = self.request.user
        logger.debug(f"Clearing archive for user {user.username}")

        try:
            count = Note.objects.clear_archive(user=user)
            return Response({"detail": f"{count} notes from archive were deleted"}, status=status.HTTP_200_OK)
        except Exception as _ex:
            logger.error(
                f"Error while clear archive for user {user.username}: {_ex}"
            )
            return Response({"detail":"Error on server side"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["get"], url_path="by_date")
    def by_date(self, request):
        """
        Return all notes by user and date
        """
        user = self.request.user

        date_str = request.query_params.get('date')
        if date_str is None:
            return Response({"detail":"No date in data"}, status=status.HTTP_400_BAD_REQUEST)
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        logger.debug(f"Fetching notes for {user.username} for date {target_date}")
        try:
            notes = Note.objects.filter(user=user, is_archived=False, date_of_note=target_date)
            if len(notes) == 0:
                return Response({"detail":"No notes found on this date"}, status=status.HTTP_200_OK)
            serializer = self.get_serializer(notes, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as _ex:
            logger.error(
                f"Error while clear archive for user {user.username}: {_ex}"
            )
            return Response({"detail":"Error on server side"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the Tag model.
    Provides CRUD operations (Create, Retrieve, Update, Delete) for tags.
    Only authenticated users can access this ViewSet.
    Users can only view and modify their own tags.
    Methods:
        get_queryset(): Returns a queryset of tags that belong to the current user.
        perform_create(serializer): Saves a new tag, setting the owner to the current user.
        perform_update(serializer): Updates an existing tag, verifying that the current user is the owner.
        perform_destroy(instance): Deletes a tag, verifying that the current user is the owner.
    """

    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [NoteAndTagThrottleRead, NoteAndTagThrottleWrite]

    def get_queryset(self):
        """
        Returns a queryset of tags that belong to the current user.
        """
        user = self.request.user
        logger.debug(f"Fetching tags for user {user.username}")
        return Tag.objects.filter(user=user)

    def perform_create(self, serializer):
        """
        Saves a new tag, setting the owner to the current user.
        """
        try:
            serializer.save(user=self.request.user)
            logger.info(f"Tag created for user {self.request.user.username}")
        except Exception as e:
            logger.error(
                f"Error creating tag for user {self.request.user.username}: {e}"
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        """
        Updates an existing tag, verifying that the current user is the owner.
        Raises PermissionDenied if the current user is not the owner.
        """
        try:
            instance = self.get_object()
            if instance.user != self.request.user:
                logger.warning(
                    f"User {self.request.user.username} tried to update a tag they do not own"
                )
                raise PermissionDenied("You can't update this object, it is not yours!")
            serializer.save()
            logger.info(f"Tag updated for user {self.request.user.username}")
        except PermissionDenied as e:
            logger.error(
                f"Permission denied for user {self.request.user.username}: {e}"
            )
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            logger.error(f"Tag not found for user {self.request.user.username}")
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(
                f"Error updating tag for user {self.request.user.username}: {e}"
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_destroy(self, instance):
        """
        Deletes a tag, verifying that the current user is the owner.
        Raises PermissionDenied if the current user is not the owner.
        """
        try:
            if instance.user != self.request.user:
                logger.warning(
                    f"User {self.request.user.username} tried to delete a tag they do not own"
                )
                raise PermissionDenied("You can't delete this object, it is not yours!")
            instance.delete()
            logger.info(f"Tag deleted for user {self.request.user.username}")
        except PermissionDenied as e:
            logger.error(
                f"Permission denied for user {self.request.user.username}: {e}"
            )
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            logger.error(f"Tag not found for user {self.request.user.username}")
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(
                f"Error deleting tag for user {self.request.user.username}: {e}"
            )
            return Response(
                {"detail": "An error occurred"}, status=status.HTTP_400_BAD_REQUEST
            )


class IconViewSet(viewsets.ViewSet):
    """
    API endpoint for managing tag icons

    Actions:
    - upload: Create new icon for a tag
    - update: Replace existing icon content
    - delete: Remove icon from tag
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [IconThrottle]

    @action(detail=False, methods=["POST"], url_name="upload", url_path="upload")
    def upload_icon(self, request):
        """
        Create new icon association

        Parameters:
        - tag_id: string, required
        - icon: file, required

        Returns:
        - 201 Created: Returns tag data with new icon path
        - 400 Bad Request: Validation errors
        """
        serializer = IconUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        tag = serializer.save()
        logger.info(f"Icon uploaded for tag {tag.pk} by user {request.user.username}")
        return Response(
            {"tag_id": tag.pk, "icon": tag.icon}, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["PUT"], url_name="update", url_path="update")
    def update_icon(self, request):
        """
        Update existing icon content

        Requirements:
        - Tag must already have an icon

        Parameters:
        - tag_id: string, required
        - icon: file, required

        Returns:
        - 200 OK: Success message with path
        - 400 Bad Request: Validation errors
        - 404 Not Found: No icon exists to update
        """
        serializer = IconUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated_tag = serializer.update_icon()
        logger.info(
            f"Icon updated for tag {updated_tag.pk} by user {request.user.username}"
        )
        return Response(
            {"detail": "Icon content updated", "icon_path": updated_tag.icon},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["DELETE"], url_name="delete", url_path="delete")
    def delete_icon(self, request):
        """
        Remove icon association

        Parameters:
        - tag_id: string, required

        Returns:
        - 204 No Content: Successful deletion
        - 400 Bad Request: Validation errors
        """
        serializer = IconUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.delete()
        logger.info(f"Icon deleted for tag by user {request.user.username}")
        return Response(status=status.HTTP_204_NO_CONTENT)

