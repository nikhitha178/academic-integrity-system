from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from backend.app.api.auth import get_current_user
from backend.app.models import User


def require_roles(*allowed_roles: str) -> Callable:
    """
    Return a FastAPI dependency that allows only specified roles.
    Authentication is handled by get_current_user.
    """

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return role_checker
