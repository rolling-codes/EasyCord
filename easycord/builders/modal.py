"""Fluent builder for multi-field modals via ctx.ask_form."""
from __future__ import annotations


class ModalBuilder:
    """Fluent builder that sends a multi-field modal and returns submitted values.

    Delegates to ``ctx.ask_form()``. Returns a ``dict[str, str]`` of field
    values, or ``None`` on timeout / dismiss::

        result = await (ModalBuilder()
            .title("Feedback")
            .field("reason", "Why?", placeholder="Tell us…")
            .field("detail", "Details", required=False)
            .send(ctx))
        if result:
            await ctx.respond(result["reason"])
    """

    def __init__(self) -> None:
        self._title: str | None = None
        self._fields: list[dict] = []

    def title(self, text: str) -> ModalBuilder:
        self._title = text
        return self

    def field(
        self,
        key: str,
        label: str,
        *,
        placeholder: str | None = None,
        required: bool = True,
    ) -> ModalBuilder:
        entry: dict = {"key": key, "label": label, "required": required}
        if placeholder is not None:
            entry["placeholder"] = placeholder
        self._fields.append(entry)
        return self

    async def send(self, ctx) -> dict[str, str] | None:
        if self._title is None:
            raise ValueError("ModalBuilder requires a title")
        kwargs: dict = {}
        for f in self._fields:
            field_cfg: dict = {"label": f["label"], "required": f["required"]}
            if "placeholder" in f:
                field_cfg["placeholder"] = f["placeholder"]
            kwargs[f["key"]] = field_cfg
        return await ctx.ask_form(self._title, **kwargs)
