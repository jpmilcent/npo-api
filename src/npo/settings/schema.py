from pydantic import BaseModel


class Version(BaseModel):
    version: str
    commit_sha: str
    commit_date: str
    environment: str
