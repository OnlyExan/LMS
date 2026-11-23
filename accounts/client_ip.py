"""Client IP for django-axes lockouts."""
import os


def client_ip(request):
    # On Vercel every request comes through its proxy, so REMOTE_ADDR isn't the visitor.
    # Vercel overwrites X-Forwarded-For with the real client IP (clients can't spoof it there),
    # so trust it only when running on Vercel; anywhere else the header is user-controlled.
    if os.environ.get("VERCEL"):
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if ip:
            return ip
    return request.META.get("REMOTE_ADDR")
