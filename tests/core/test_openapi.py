from fastapi import FastAPI

from npo.core.openapi import register_custom_openapi, translate_schema


def test_translate_schema_recursive():
    """
    Verifies that the translate_schema function recursively traverses
    the dictionary and translates target fields.
    """
    schema = {
        "openapi": "3.1.0",
        "info": {
            "title": "My API",
            "description": "This is a description",
            "version": "1.0.0",
        },
        "paths": {
            "/items": {
                "get": {
                    "summary": "Get Items",
                    "description": "Retrieve items",
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": {
                                "application/json": {"schema": {"title": "Item", "type": "object"}}
                            },
                        }
                    },
                }
            }
        },
    }

    # Mock translator that reverses strings to prove the function is called
    def reverse_translator(text: str) -> str:
        return text[::-1]

    translate_schema(schema, reverse_translator)

    # Check translated fields
    assert schema["info"]["title"] == "IPA yM"
    assert schema["info"]["description"] == "noitpircsed a si sihT"

    # Nested check (paths -> verb -> summary/description)
    path_op = schema["paths"]["/items"]["get"]
    assert path_op["summary"] == "smetI teG"
    assert path_op["description"] == "smeti eveirteR"
    assert path_op["responses"]["200"]["description"] == "esnopseR lufsseccuS"

    # Check that non-targeted fields (version, openapi) are not touched
    assert schema["openapi"] == "3.1.0"
    assert schema["info"]["version"] == "1.0.0"


def test_register_custom_openapi_integration():
    """
    Verifies that register_custom_openapi correctly overrides the application's
    .openapi() method and applies translation.
    """
    app = FastAPI(title="Original Title", description="Original Description")

    @app.get("/route", summary="Original Summary")
    def route():
        return {"message": "Hello"}

    def mock_translator(text: str) -> str:
        return f"Translated {text}"

    # Register the hook
    register_custom_openapi(app, mock_translator)

    # Generate schema via standard FastAPI call
    schema = app.openapi()

    # Checks
    assert schema["info"]["title"] == "Translated Original Title"
    assert schema["info"]["description"] == "Translated Original Description"
    assert schema["paths"]["/route"]["get"]["summary"] == "Translated Original Summary"
