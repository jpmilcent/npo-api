from collections.abc import Sequence


def create_paginated_response[T](*, data: Sequence[T], total: int, page: int, size: int) -> dict:
    """
    Creates a paginated response dictionary that matches the PaginatedResponse schema.
    """
    return {
        "meta": {
            "pagination": {
                "total_items": total,
                "total_pages": (total + size - 1) // size if size > 0 else 0,
                "current_page": page,
                "items_per_page": size,
            }
        },
        "data": data,
    }
