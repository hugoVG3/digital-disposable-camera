# Disposable Camera

A web app that lets users upload photos like a disposable camera—max 24 photos per user, stored locally on a Raspberry Pi.

## Status

🚧 **Work in Progress** — Folder structure and setup only. Core functionality coming soon.

## Project Structure
```bash
├── app.py
├── config.py
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── camera.py
│   │   └── auth.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── photo_handler.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── camera.html
│   │   └── gallery.html
│   └── static/
│       ├── css/
│       ├── js/
│       └── images/
├── data/
│   ├── photos/
│   └── app.db (SQLite database)
├── tests/
└── docs/
```

## Tech Stack

- **Backend:** Python 3.9+, Flask
- **Database:** SQLite
- **Frontend:** HTML5, CSS3, vanilla JavaScript
- **Storage:** Local filesystem
- **Target:** Raspberry Pi Zero 2W

## Setup (Coming Soon)

Instructions for running on Raspberry Pi will be added as the project develops.

## Features (Planned)

- [ ] User sessions / authentication
- [ ] Photo upload (max 24 per user)
- [ ] Photo gallery view
- [ ] Photo deletion
- [ ] Responsive UI for mobile

## Development

```bash
git clone https://github.com/yourusername/disposable-camera.git
cd disposable-camera
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

More details coming as development progresses.
```
