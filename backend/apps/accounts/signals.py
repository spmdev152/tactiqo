import logging
from collections.abc import Collection

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.application.services import revoke_sessions
from apps.accounts.models import AuthSession, User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User, dispatch_uid="accounts.revoke_sessions_of_a_replaced_credential")
def revoke_sessions_of_a_replaced_credential(
    *,
    instance: User,
    created: bool,
    raw: bool,
    using: str,
    update_fields: Collection[str] | None,
    **_kwargs: object,
) -> None:
    """
    Revoke the sessions of an account whose credential was just replaced.

    Hanging the revocation on the write rather than on a caller is what makes it
    unavoidable for every caller that saves the row: the admin, ``changepassword``
    and a bare ``set_password`` followed by a save all reach the database through
    this receiver, and so does the admin submit that destroys the credential
    instead of rotating it. ``User.save`` wraps the write in a transaction and
    this receiver runs inside it, so the new credential and the revocation of the
    sessions it invalidates commit together or not at all.

    Parameters
    ----------
    instance : User
        Account whose row was just written.
    created : bool
        Whether the row was inserted, in which case no session can exist yet.
    raw : bool
        Whether a fixture is being loaded, where application invariants are not
        the loader's to enforce.
    using : str
        Database alias the row was written to, so the sessions are revoked where
        the credential changed.
    update_fields : collection of str or None
        Columns the save wrote, ``None`` when it wrote every column. A save that
        left the password column alone cannot have replaced the credential.
    **_kwargs : object
        Further signal arguments, unused.
    """

    wrote_password = update_fields is None or "password" in update_fields

    if created or raw or not wrote_password or not instance.has_new_password():
        return

    revoked_count = revoke_sessions(AuthSession.objects.using(using).filter(user=instance))

    logger.info(
        "Revoked %d authentication session(s) of account %s after a credential change.",
        revoked_count,
        instance.pk,
    )
