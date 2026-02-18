from pydantic import BaseModel, ConfigDict, Field, computed_field

from npo.core.types import Email, Password


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sub: str = Field(validation_alias="uid")
    firstname: str | None = None
    lastname: str | None = None
    email: Email | None = None
    email_verified: bool | None = None
    picture_url: str | None = None
    is_active: bool | None = None
    is_superadmin: bool | None = None

    @computed_field(title="Full Name", description="The full name of the user")
    @property
    def full_name(self) -> str:
        return " ".join(filter(None, [self.firstname, self.lastname]))


class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: Password


class UserProfileUpdate(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    email: Email | None = None
    picture_url: str | None = None


class UserCreate(BaseModel):
    email: Email
    password: Password
    firstname: str | None = None
    lastname: str | None = None
    is_active: bool = True
    is_superadmin: bool = False


class UserUpdate(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    email: Email | None = None
    password: Password | None = None
    is_active: bool | None = None
    is_superadmin: bool | None = None
