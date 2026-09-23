# Arkeon

A self-hosted private cloud storage server built with FastAPI and vanilla HTML/CSS/JS.

---

## Tech Stack

- **Backend** — FastAPI, SQLAlchemy, SQLite, Alembic
- **Auth** — JWT (python-jose), bcrypt
- **Email** — SendGrid
- **Frontend** — Vanilla HTML / CSS / JavaScript
- **Reverse proxy** — Nginx
- **Process manager** — systemd
- **Security** — fail2ban, SELinux

---

## Features

- File upload, download, preview (images, video, PDF, text)
- Folder creation and renaming
- Starred files and trash bin (30-day auto-delete)
- Shareable links with expiry
- Email-based login with account lockout and dormant detection
- Profile picture upload
- Admin panel with per-user storage limits
- Dark / light theme

---

## Project Structure

```
arkeon/
├── main.py               Entry point
├── config.py             App configuration
├── auth.py               JWT authentication
├── db.py                 Database session
├── models.py             SQLAlchemy models
├── process.py            File operations router
├── mailer.py             SendGrid email sender
├── .env                  Secrets (not committed)
├── modules.txt           Python dependencies
├── migrations/           Alembic migration files
├── domain/user/
│   ├── user_router.py    User API endpoints
│   ├── user_crud.py      User database operations
│   └── user_schema.py    Pydantic schemas
└── frontend/
    ├── index.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── admin.html
    ├── reset-password.html
    ├── css/style.css
    └── js/api.js
```

---

## Configuration

Create a `.env` file in the project root before running.

```env
SECRET_KEY=your_random_secret_key
DATABASE_URL=sqlite:////absolute/path/to/data/account_info.db
SENDGRID_API_KEY=SG.your_sendgrid_key
ADMIN_PASSWORD=your_admin_password
ADMIN_EMAIL=admin@example.com
MAIL_FROM=noreply@example.com
```

Non-secret settings such as `MAX_ACCOUNT`, `UPLOAD_DIR`, `LOCKOUT_MINUTES`, and `DORMANT_DAYS` are managed in `config.py`.

---

## Installation

```bash
# 1. Clone and enter the project directory
cd /home/haruki/arkeon

# 2. Set correct ownership on the database directory
sudo chown haruki:haruki data/

# 3. Run the setup script (installs packages and runs migrations)
sudo bash setup1.sh
```

The admin account is created automatically on first startup using the credentials in `.env`.

---

## Running with systemd

Create `/etc/systemd/system/arkeon.service`:

```ini
[Unit]
Description=Arkeon FastAPI
After=network.target

[Service]
User=haruki
WorkingDirectory=/home/haruki/arkeon
ExecStart=/usr/local/bin/uvicorn main:app --host 127.0.0.1 --port 2926
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable arkeon
sudo systemctl start arkeon
```

---

## Nginx Configuration

```nginx
server {
    listen 80;
    server_name arkeon.duckdns.org;

    client_max_body_size 2G;

    location / {
        proxy_pass http://127.0.0.1:2926;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
```

Enable Nginx to connect to local ports on Rocky Linux (SELinux):

```bash
sudo setsebool -P httpd_can_network_connect 1
sudo systemctl restart nginx
```

---

## HTTPS

```bash
sudo dnf install certbot python3-certbot-nginx -y
sudo certbot --nginx -d arkeon.duckdns.org
```

---

## Security

fail2ban is configured to automatically ban IPs that repeatedly scan for vulnerabilities.

```bash
# Check ban status
sudo fail2ban-client status nginx-botscan

# Manually unban an IP
sudo fail2ban-client set nginx-botscan unbanip 1.2.3.4
```

---

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/user/login | Sign in with email and password |
| GET | /api/user/me | Get current user info |
| POST | /api/file/upload | Upload a file |
| GET | /api/file/list | List files in a folder |
| GET | /api/file/stats | Storage usage and file count |
| GET | /api/file/starred | List starred files |
| GET | /api/file/trash | List trashed files |
| PATCH | /api/file/star/{id} | Toggle star on a file |
| DELETE | /api/file/delete/{id} | Move file to trash |
| PATCH | /api/file/trash/restore/{id} | Restore file from trash |
| DELETE | /api/file/trash/permanent/{id} | Permanently delete a file |
| DELETE | /api/file/trash/empty | Empty all trash |
| GET | /api/user/admin/users | List all users (admin only) |
| PATCH | /api/user/admin/users/{id}/storage-limit | Set per-user storage limit |

Full interactive API docs are available at `/docs` when the server is running.
