def gettext_noop(message: str) -> str:
    """
    Marks a string for translation but returns it unchanged.

    This function serves as a placeholder for translation functions. It's used
    by tools like pybabel to extract strings from the source code. The actual
    translation will be performed at runtime by a real gettext implementation,
    like the one provided by fastapi-babel.
    """
    return message


# By convention, N_ is an alias for gettext_noop. It's used to mark strings
# in contexts where they cannot be translated immediately (e.g., module-level constants).
# Use this when _ is alryeady taken by the real translation function.
N_ = gettext_noop

# By convention, _ is the main alias for the translation function.
# Here, we alias it to our no-op function so that strings in OpenAPI schemas
# or other module-level definitions can be marked for extraction without
# causing errors outside of a request context. The real translation function
# from fastapi-babel will override this behavior during a request.
_ = gettext_noop
