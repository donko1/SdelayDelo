# SdelayDelo - Your Personal Note-Taking App

SdelayDelo is a Django-based application that allows you to easily create, manage, and organize your notes. It features tagging, different API versions.

## Features

- **Note Creation and Management:** Create, edit, and delete your notes with ease.
- **Tagging:** Organize your notes using tags.
- **Multiple API Versions:** Different versions of the Note API for flexibility and feature evolution.
- **User Authentication:** Secure user registration, login, and password management.
- **Archiving:** Archive notes to keep your main list clean.
- **Tag Icons:** Associate custom icons with your tags for visual organization.

## API Endpoints

The following API endpoints are available:

### General Endpoints

- **`GET /hello_world/`**: A simple "Hello, World!" endpoint.
- **`POST /api/check_if_email_registered/`**: Checks if an email address is already registered.
- **`POST /api/send_code/`**: Sends a verification code to the provided email address.
- **`POST /api/check_code/`**: Verifies the provided verification code.
- **`POST /api/register/`**: Registers a new user.
- **`GET /api/whoami`**: Returns information about the currently logged-in user. In debug mode returns all user information, if not returns only theme and other non-sensitive information.
- **`POST /api/reset_password`**: Resets the user's password.
- **`POST /api/login`**: Logs in an existing user.
- **`PATCH /api/change-userinfo/`**: Updates user information.

### Notes Endpoints

- **`GET /api/v1/note/`**: List all notes (API v1).
- **`POST /api/v1/note/`**: Create a new note (API v1).
- **`GET /api/v1/note/{id}/`**: Retrieve a specific note (API v1).
- **`PUT /api/v1/note/{id}/`**: Update a specific note (API v1).
- **`DELETE /api/v1/note/{id}/`**: Delete a specific note (API v1).
- The same endpoints exist for `/api/v2/note/` and `/api/v3/note/` using API versions 2 and 3.
- **`GET /api/note/`**: List all notes (Default Version).
- **`POST /api/note/`**: Create a new note (Default Version).
- **`GET /api/note/{id}/`**: Retrieve a specific note (Default Version).
- **`PUT /api/note/{id}/`**: Update a specific note (Default Version).
- **`DELETE /api/note/{id}/`**: Delete a specific note (Default Version).

### Tags Endpoints

- **`GET /api/tag/`**: List all tags.
- **`POST /api/tag/`**: Create a new tag.
- **`GET /api/tag/{id}/`**: Retrieve a specific tag.
- **`PUT /api/tag/{id}/`**: Update a specific tag.
- **`DELETE /api/tag/{id}/`**: Delete a specific tag.

### Icons Endpoints

- **`POST /api/icons/upload/`**: Upload a new icon for a tag. Requires `tag_id` and `icon` as form data.
- **`PUT /api/icons/update/`**: Update an existing icon for a tag. Requires `tag_id` and `icon` as form data. Tag must already have an icon.
- **`DELETE /api/icons/delete/`**: Delete an icon association. Requires `tag_id` in the request data.
- **NOTE:** The Icon API uses authentication and throttling.

## API Version Differences

- **v1:** Basic Note API functionality.
- **v2:** Inherits from v1. Filters the notes queryset to only return notes belonging to the current user that are *not* archived. Includes pagination.
- **v3:** Inherits from v2. Includes an extra endpoint `/api/v3/note/archived/` which shows only the archived notes of the current user.

## Installation

Follow these steps to install and run SdelayDelo locally.

### Prerequisites

- Python 3.10+
- git
- pip (Python package installer)
- Redis

### Linux

1. Install Redis:
   ```bash
   sudo apt update && sudo apt install -y redis-server
   sudo systemctl enable redis
   sudo systemctl start redis 
   ```
2. Clone the repository:
   ```bash
   git clone https://github.com/donko1/SdelayDelo.git
   cd SdelayDelo
   ```
3. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
4. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Apply migrations:
   ```bash
   python3 manage.py migrate
   ```
7. Create a superuser (admin account):
   ```bash
   python3 manage.py createsuperuser
   ```
8. Create local settings and **configure it**(optionally):
   ```bash
   cp SdelayDelo/local_settings.py.example SdelayDelo/local_settings.py
   ```
9. Start Redis:
   ```bash
   sudo systemctl restart redis
   ```
10. Fill the email fields in local_settings.py to make them working. (optionally)
11. Run the development server:
   ```bash
   python3 manage.py runserver
   ```
   The server will start at http://127.0.0.1:8000/.

### Windows

1. Install [Redis](https://github.com/microsoft/redis) and start it  

2. Clone the repository:
   ```bash
   git clone https://github.com/donko1/SdelayDelo.git
   cd SdelayDelo
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
4. Activate the virtual environment:
   ```bash
   .\venv\Scripts\activate
   ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Apply migrations:
   ```bash
   python manage.py migrate
   ```
7. Create a superuser (admin account):
   ```bash
   python manage.py createsuperuser
   ```
8. Create local settings (rename `SdelayDelo/local_settings.py.example` to `SdelayDelo/local_settings.py`) and **configure it**(optionally).
9. Run the development server:
   ```bash
   python manage.py runserver
   ```
   The server will start at http://127.0.0.1:8000/.

10. Fill the email fields in local_settings.py to make them working. (optionally)

## Usage

1. **Access the application:** Open your web browser and navigate to http://127.0.0.1:8000/.
2. **Admin Panel:** Access the admin panel at http://127.0.0.1:8000/admin/ and log in with the superuser credentials you created during installation.
3. **Explore the API:** Use tools like Postman or `curl` to interact with the API endpoints. Pay attention to the required data formats for each endpoint. The icon API expects data as form data. You can see examples of usage in [this file](https://github.com/donko1/SdelayDelo/blob/main/tasks/tests.py). To run SdelayDelo test cases, run `python3 manage.py test`. If you need to run slow test to check if unban ip after ban run `python3 manage.py test --tag=redis-unban-after-timeout`.