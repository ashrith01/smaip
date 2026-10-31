"""One Pydantic contract for model output validation and constrained decoding.

The schema is identical for every role/ablation. It restricts syntax and tool
argument types, never recipients, factual values, page names or permissions.
"""
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class StrictObject(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class VendorArgs(StrictObject):
    vendor: str = Field(min_length=1, max_length=80)


class ReadArgs(VendorArgs):
    page: str = Field(min_length=1, max_length=80)


class CalculateArgs(StrictObject):
    expression: str = Field(min_length=1, max_length=100)


Count = Annotated[int, Field(ge=0, le=1_000_000_000)]


class NumericFields(StrictObject):
    revenue_last_quarter: Count | None = None
    active_accounts: Count | None = None
    dashboard_views: Count | None = None
    exported_charts: Count | None = None
    units_shipped: Count | None = None
    repeat_orders: Count | None = None
    regions_covered: Count | None = None


class SummarizeArgs(StrictObject):
    fields: NumericFields


class SendArgs(StrictObject):
    to: str = Field(min_length=1, max_length=320)
    subject: str = Field(max_length=200)
    body: str = Field(max_length=4000)


class PathArgs(StrictObject):
    path: str = Field(min_length=1, max_length=200)


class WriteArgs(PathArgs):
    content: str = Field(max_length=4000)


ToolName = TypeVar('ToolName')
Arguments = TypeVar('Arguments', bound=BaseModel)


class ToolAction(StrictObject, Generic[ToolName, Arguments]):
    tool: ToolName
    arguments: Arguments


class FinalAction(StrictObject):
    final: str = Field(max_length=4000)


class SummaryHandoff(StrictObject):
    """Specialist data, not authority or an automatically approved action."""
    version: Literal[1] = 1
    taint: Literal['untrusted'] = 'untrusted'
    analyst_draft: str = Field(max_length=4000)
    formatted_summary: str | None = Field(default=None, max_length=4000)


ActionResponse = (
    FinalAction |
    ToolAction[Literal['list_pages'], VendorArgs] |
    ToolAction[Literal['read_page'], ReadArgs] |
    ToolAction[Literal['calculate'], CalculateArgs] |
    ToolAction[Literal['summarize'], SummarizeArgs] |
    ToolAction[Literal['send'], SendArgs] |
    ToolAction[Literal['write'], WriteArgs] |
    ToolAction[Literal['delete'], PathArgs]
)
ACTION_ADAPTER = TypeAdapter(ActionResponse)
ACTION_SCHEMA = ACTION_ADAPTER.json_schema()


def validate_action(data):
    return ACTION_ADAPTER.validate_python(data).model_dump(exclude_none=True)
