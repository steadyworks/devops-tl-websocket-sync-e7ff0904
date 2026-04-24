# type: ignore

from typing import Any, cast

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def _rewrite_nullable(schema: Any) -> None:
    """Recursively rewrite anyOf [X, null] → type: [X, "null"],
    and rewrite $ref cases to allOf + nullable=True.
    """
    if isinstance(schema, dict):
        if "anyOf" in schema:
            any_of = cast("Any", schema["anyOf"])

            if isinstance(any_of, list) and any(
                isinstance(fragment, dict) and fragment.get("type") == "null"
                for fragment in any_of
            ):
                non_null = [
                    fragment
                    for fragment in any_of
                    if not (
                        isinstance(fragment, dict) and fragment.get("type") == "null"
                    )
                ]
                if len(non_null) == 1 and isinstance(non_null[0], dict):
                    base = dict(non_null[0])  # shallow copy

                    if "$ref" in base:
                        # ✅ spec-compliant form: allOf + nullable
                        replacement: dict[str, Any] = {
                            "allOf": [{"$ref": base["$ref"]}],
                            "nullable": True,
                        }
                    else:
                        replacement = base
                        old_type = replacement.get("type")
                        if old_type is not None:
                            if isinstance(old_type, list):
                                if "null" not in old_type:
                                    replacement["type"] = old_type + ["null"]
                            else:
                                replacement["type"] = [old_type, "null"]

                    # merge metadata (title, description, etc.)
                    for key, value in schema.items():
                        if key != "anyOf":
                            replacement.setdefault(key, value)

                    schema.clear()
                    schema.update(replacement)

        # recurse
        for value in list(schema.values()):
            _rewrite_nullable(value)

    elif isinstance(schema, list):
        for fragment in schema:
            _rewrite_nullable(fragment)


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Generate OpenAPI schema but rewrite nullables for legacy generators."""
    if getattr(app, "openapi_schema", None):
        return app.openapi_schema  # type: ignore[return-value]

    openapi_schema: dict[str, Any] = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    _rewrite_nullable(openapi_schema)
    app.openapi_schema = openapi_schema  # type: ignore[attr-defined]
    return openapi_schema
