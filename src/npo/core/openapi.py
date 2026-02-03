from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def translate_schema(schema: dict[str, Any], translator: Callable[[str], str]) -> None:
    """
    Recursively traverses the OpenAPI schema to translate text fields.
    Modifies the dictionary in place.
    """
    # List of JSON schema keys containing text displayed to the user
    target_keys = {"summary", "description", "title", "response_description"}

    def _walk(obj: Any):
        if isinstance(obj, dict):
            for key, value in obj.items():
                # If the key is a target and the value is a string, translate it
                if key in target_keys and isinstance(value, str):
                    obj[key] = translator(value)
                else:
                    # Otherwise continue exploration
                    _walk(value)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(schema)


def register_custom_openapi(app: FastAPI, translator: Callable[[str], str]) -> None:
    """
    Overrides the FastAPI application openapi method to inject translations.
    """

    def custom_openapi():
        # 1. Generate the original schema (based on source code, so in English)
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # 2. Translate the schema
        translate_schema(openapi_schema, translator)

        # 3. Return the schema without caching to allow dynamic translation
        return openapi_schema

    app.openapi = custom_openapi
