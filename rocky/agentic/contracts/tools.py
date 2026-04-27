from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel

from rocky.agentic.contracts.message import MessageContent


class JsonSchema(BaseModel):
    type: Optional[Union[str, List[str]]] = None
    items: Optional[Union["JsonSchema", List["JsonSchema"]]] = None
    anyOf: Optional[List["JsonSchema"]] = None
    additionalProperties: Optional[Union[bool, "JsonSchema"]] = None
    properties: Optional[Dict[str, "JsonSchema"]] = None
    title: Optional[str] = None
    description: Optional[str] = None
    default: Optional[Any] = None
    required: Optional[List[str]] = None
    enum: Optional[List[Any]] = None


class FunctionDefinition:
    name: str
    description: str
    parameters: Optional[JsonSchema]
    strict: bool

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Optional[JsonSchema] = None,
        strict: bool = False,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.strict = strict


class ToolDefinition:
    name: Optional[str]
    description: Optional[str]
    channel: Optional[str]
    unconstrained: bool
    functions: List[FunctionDefinition]

    def __init__(
        self,
        functions: List[FunctionDefinition],
        name: Optional[str] = None,
        description: Optional[str] = None,
        channel: Optional[str] = None,
        unconstrained: bool = False,
    ):
        self.functions = functions
        self.name = name
        self.description = description
        self.channel = channel
        self.unconstrained = unconstrained


class ToolCall:
    id: str
    namespace: str
    function: str
    arguments: Dict | str

    def __init__(
        self, call_id: str, namespace: str, function: str, arguments: Dict | str
    ):
        self.id = call_id
        self.namespace = namespace
        self.function = function
        self.arguments = arguments


class ToolResult:
    call_id: str
    type: Optional[str]
    output: Optional[Union[List[MessageContent], str, Dict[str, Any]]]

    def __init__(
        self,
        call_id: str,
        output: Optional[Union[List[MessageContent], str, Dict[str, Any]]],
        type: Optional[str] = None,
    ):
        self.call_id = call_id
        self.type = type
        self.output = output


class ApiToolCall(BaseModel):
    id: Optional[str] = None
    type: str


class ApiToolCallComputerAction(BaseModel):
    type: str


class ApiToolCallComputerActionClick(ApiToolCallComputerAction):
    type: Literal["click"] = "click"
    button: Literal["left", "right", "wheel", "back", "forward"]
    x: int
    y: int


class ApiToolCallComputerActionDoubleClick(ApiToolCallComputerAction):
    type: Literal["double_click"] = "double_click"
    x: int
    y: int


class ApiToolCallComputerActionDragPath(BaseModel):
    x: int
    y: int


class ApiToolCallComputerActionDrag(ApiToolCallComputerAction):
    type: Literal["drag"] = "drag"
    path: List[ApiToolCallComputerActionDragPath]


class ApiToolCallComputerActionKeypress(ApiToolCallComputerAction):
    type: Literal["keypress"] = "keypress"
    keys: List[str]


class ApiToolCallComputerActionMove(ApiToolCallComputerAction):
    type: Literal["move"] = "move"
    x: int
    y: int


class ApiToolCallComputerActionScreenshot(ApiToolCallComputerAction):
    type: Literal["screenshot"] = "screenshot"


class ApiToolCallComputerActionScroll(ApiToolCallComputerAction):
    type: Literal["scroll"] = "scroll"
    scroll_x: int
    scroll_y: int
    x: int
    y: int


class ApiToolCallComputerActionType(ApiToolCallComputerAction):
    type: Literal["type"] = "type"
    text: str


class ApiToolCallComputerActionWait(ApiToolCallComputerAction):
    type: Literal["wait"] = "wait"


class ApiToolCallComputerPendingSafetyCheck(BaseModel):
    id: str
    code: Optional[str] = None
    message: Optional[str] = None


class ApiToolCallComputer(ApiToolCall):
    type: Literal["computer_call"] = "computer_call"
    actions: List[ApiToolCallComputerAction]
