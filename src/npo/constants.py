from enum import StrEnum


# Error Codes
class ErrorCode(StrEnum):
    DUPLICATE_PERCEPTUAL_HASH = (
        "DUPLICATE_PERCEPTUAL_HASH",
        "File {filename} with perceptual hash {perceptual_hash} already exists.",
    )
    FILE_NOT_FOUND = "FILE_NOT_FOUND", "File {pixel_hash} not found."
    FILES_WEBSERVICE_NOT_FOUND = (
        "FILES_WEBSERVICE_NOT_FOUND",
        "Webservice /files/{path} requested not found.",
    )
    RAW_METADATA_NOT_FOUND = (
        "RAW_METADATA_NOT_FOUND",
        "Raw metadata for file {pixel_hash} not found.",
    )
    PHOTOGRAPHY_METADATA_NOT_FOUND = (
        "PHOTOGRAPHY_METADATA_NOT_FOUND",
        "Photography metadata for file {pixel_hash} not found.",
    )
    METADATA_WEBSERVICE_NOT_FOUND = (
        "METADATA_WEBSERVICE_NOT_FOUND",
        "Webservice /metadata/{path} requested not found.",
    )

    def __new__(cls, value, message):
        member = str.__new__(cls, value)
        member._value_ = value
        member.message = message
        return member

    def formatMsg(self, **kwargs) -> str:
        return self.message.format(**kwargs)
