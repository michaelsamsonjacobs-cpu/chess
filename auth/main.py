import uvicorn

from .config import get_settings


def main():
    settings = get_settings()
    kwargs = {
        "host": "0.0.0.0",
        "port": 8001,
    }
    if settings.tls_cert_path and settings.tls_key_path:
        kwargs.update({"ssl_certfile": settings.tls_cert_path, "ssl_keyfile": settings.tls_key_path})

    uvicorn.run("auth.app:app", **kwargs)


if __name__ == "__main__":
    main()
