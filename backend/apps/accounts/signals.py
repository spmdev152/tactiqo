import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.application.services import revoke_sessions
from apps.accounts.models import AuthSession, User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User, dispatch_uid="accounts.revoke_sessions_of_a_new_password")
def revoke_sessions_of_a_new_password(
    *, instance: User, created: bool, raw: bool, **_kwargs: object
) -> None:
    """
    Revoke the sessions of an account whose password was just replaced.

    Hanging the revocation on the write rather than on a caller is what makes it
    unavoidable: the admin, ``changepassword``, and a bare ``set_password``
    followed by a save all reach the database through the same signal, so setting
    a new password is what ends the sessions issued under the old one. It fires
    after the row is written, so a failed write revokes nothing.

    Parameters
    ----------
    instance : User
        Account whose row was just written.
    created : bool
        Whether the row was inserted, in which case no session can exist yet.
    raw : bool
        Whether a fixture is being loaded, where application invariants are not
        the loader's to enforce.
    **_kwargs : object
        Further signal arguments, unused.
    """

    if created or raw or not instance.has_new_password():
        return

    revoked_count = revoke_sessions(AuthSession.objects.filter(user=instance))

    logger.info(
        "Revoked %d authentication session(s) of account %s after a password change.",
        revoked_count,
        instance.pk,
    )
