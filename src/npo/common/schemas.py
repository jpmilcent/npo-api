from pydantic import BaseModel, Field

from npo.core.i18n import _


class Pagination(BaseModel):
    """Pagination details."""

    total_items: int = Field(description=_("Total number of items"))
    total_pages: int = Field(description=_("Total number of pages"))
    current_page: int = Field(description=_("Current page number"))
    items_per_page: int = Field(description=_("Number of items per page"))


class PaginationMeta(BaseModel):
    """Metadata for a paginated response."""

    pagination: Pagination


class PaginatedResponse[DataType](BaseModel):
    """Generic schema for a paginated response."""

    meta: PaginationMeta
    data: list[DataType]
