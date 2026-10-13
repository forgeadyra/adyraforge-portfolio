from django.conf import settings
from django.core.mail import send_mail

from .models import User
from .tokens import make_invite_token, make_reset_pair


def send_invite(user: User) -> None:
    link = f"{settings.FRONTEND_URL}/invite/{make_invite_token(user)}"
    hours = settings.INVITE_MAX_AGE // 3600
    send_mail(
        subject="Your AdyraForge client portal",
        message=(
            f"Hi{(' ' + user.full_name) if user.full_name else ''},\n\n"
            "Forge has set up a client portal for your project. Choose a password to "
            f"activate your account:\n\n{link}\n\n"
            f"This link works once and expires in {hours} hours. If you weren't expecting "
            "it, you can ignore this email.\n\n— AdyraForge"
        ),
        from_email=None,
        recipient_list=[user.email],
    )


def send_password_reset(user: User) -> None:
    uid, token = make_reset_pair(user)
    link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"
    minutes = settings.PASSWORD_RESET_TIMEOUT // 60
    send_mail(
        subject="Reset your AdyraForge password",
        message=(
            "Someone (hopefully you) asked to reset the password for this account.\n\n"
            f"{link}\n\nThis link works once and expires in {minutes} minutes. If you "
            "didn't ask for this, ignore this email; your password is unchanged.\n\n— AdyraForge"
        ),
        from_email=None,
        recipient_list=[user.email],
    )
