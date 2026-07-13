"""Request-scoped context via contextvars."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("awatch_request_id", default=None)
consumer_var: ContextVar[dict[str, Any] | None] = ContextVar("awatch_consumer", default=None)
categories_var: ContextVar[list[str]] = ContextVar("awatch_categories", default=[])
spans_var: ContextVar[list[dict[str, Any]]] = ContextVar("awatch_spans", default=[])


@dataclass
class ConsumerInfo:
    identifier: str
    name: str | None = None
    group: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "name": self.name,
            "group": self.group,
        }


@dataclass
class RequestContext:
    request_id: str
    consumer: ConsumerInfo | None = None
    categories: list[str] = field(default_factory=list)
    spans: list[dict[str, Any]] = field(default_factory=list)


def get_request_id() -> str | None:
    return request_id_var.get()


def set_request_id(value: str) -> None:
    request_id_var.set(value)


def get_consumer() -> dict[str, Any] | None:
    return consumer_var.get()


def set_consumer_ctx(consumer: ConsumerInfo | dict[str, Any]) -> None:
    if isinstance(consumer, ConsumerInfo):
        consumer_var.set(consumer.to_dict())
    else:
        consumer_var.set(consumer)


def get_categories() -> list[str]:
    return list(categories_var.get() or [])


def set_categories(cats: list[str]) -> None:
    categories_var.set(list(cats))


def add_span(span: dict[str, Any]) -> None:
    spans = list(spans_var.get() or [])
    spans.append(span)
    spans_var.set(spans)


def get_spans() -> list[dict[str, Any]]:
    return list(spans_var.get() or [])


def reset_request_context() -> None:
    request_id_var.set(None)
    consumer_var.set(None)
    categories_var.set([])
    spans_var.set([])
