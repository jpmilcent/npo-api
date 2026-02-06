from pydantic import BaseModel, Field

from npo.core.i18n import _


class Version(BaseModel):
    version: str = Field(description=_("App version number using semantic versioning."))
    commit_sha: str = Field(description=_("SHA hash of the last commit."))
    commit_date: str = Field(description=_("Date of the last commit."))
    environment: str = Field(description=_("Current environment."))
