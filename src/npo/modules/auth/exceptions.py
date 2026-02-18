from npo.core.exceptions import DomainError


class UnauthorizedUserError(DomainError):
    pass


class InactiveUserError(DomainError):
    pass
