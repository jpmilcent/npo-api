from enum import Enum


class UserPermission(str, Enum):
    READ = "user:read"
    WRITE = "user:write"
    DELETE = "user:delete"
