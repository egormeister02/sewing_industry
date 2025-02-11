data: sqlLite + google sheet\
application: quart + hypercorn + nginx

structure:\
project\
├── app\
│   ├── __init__.py\
│   ├── main.py\
│   ├── database/\
│   │   ├── __init__.py\
│   │   ├── crud.py\
│   │   └── models.py\
│   ├── handlers/\
│   │   ├── __init__.py\
│   │   ├── start.py\
│   │   ├── managers.py\
│   │   └── qr_codes.py\
│   ├── keyboards/\
│   │   ├── __init__.py\
│   │   └── inline.py\
│   ├── services/\
│   │   ├── __init__.py\
│   │   └── qr_processing.py\
│   └── states/\
│       ├── __init__.py\
│       └── managers.py\
├── credentials.py\
├── schema.sql\
└── requirements.txt

database:

![documents/db_schema.jpg](documents/db_schema.jpg)


