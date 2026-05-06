import re

from flut.dart.ui import (
    FontStyle,
    FontWeight,
    PlaceholderAlignment,
    TextAlign,
    TextDecoration,
)
from flut.dart.io import File
from flut.flutter.material import (
    Colors,
    Icons,
    InkWell,
    Material,
    SelectionArea,
    Theme,
)
from flut.flutter.gestures import TapGestureRecognizer
from flut.flutter.painting import (
    Alignment,
    Border,
    BorderRadius,
    BorderSide,
    BoxDecoration,
    BoxFit,
    EdgeInsets,
    TextSpan,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisSize
from flut.flutter.services import (
    SystemMouseCursors,
)
from flut.flutter.widgets import (
    ClipRRect,
    Column,
    Container,
    Expanded,
    Icon,
    Image,
    MouseRegion,
    Row,
    SelectionContainer,
    SizedBox,
    StatelessWidget,
    Text,
    WidgetSpan,
)

from rocky.system import RockySystem

_HEADING_SIZES = {1: 20, 2: 18, 3: 16, 4: 15, 5: 14, 6: 14}
_INLINE_IMAGE_MAX = 128.0
_LIST_MARKER_CHAR_WIDTH = 6.0
_LIST_BLOCK_KINDS = frozenset({"bullet", "numbered", "task"})
_LIST_SIBLING_GAP = 4
_DEFAULT_BLOCK_GAP = 12

_FENCE_PATTERN = re.compile(r"^\s*```(.*)$")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_PATTERN = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_TASK_PATTERN = re.compile(r"^\[([ xX])\]\s+(.*)$")
_NUMBERED_PATTERN = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_QUOTE_PATTERN = re.compile(r"^\s*>\s?(.*)$")
_RULE_PATTERN = re.compile(r"^\s*(?:[-*_])(?:\s*[-*_]){2,}\s*$")
_TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR_PATTERN = re.compile(
    r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$"
)

_INLINE_PATTERN = re.compile(
    r"\\(?P<escape>[\\`*_{}\[\]()#+\-.!>~|])"
    r"|(?P<code_ticks>`+)(?P<code_body>.+?)(?P=code_ticks)"
    r"|\*\*\*(?P<bolditalic>[^*\n]+?)\*\*\*"
    r"|___(?P<bolditalic_u>[^_\n]+?)___"
    r"|\*\*(?P<bold>[^*\n]+?)\*\*"
    r"|__(?P<bold_u>[^_\n]+?)__"
    r"|~~(?P<strike>[^~\n]+?)~~"
    r"|\*(?P<italic_a>[^*\n]+?)\*"
    r"|(?<![A-Za-z0-9])_(?P<italic_u>[^_\n]+?)_(?![A-Za-z0-9])"
    r"|!\[(?P<image_alt>[^\]\n]*)\]\((?P<image_url>[^)\s]+)\)"
    r"|\[(?P<link_text>[^\]\n]+)\]\((?P<link_url>[^)\s]+)\)"
)


class RockyMarkdown(StatelessWidget):
    def __init__(
        self,
        *,
        content: str,
        base_style: TextStyle,
        selectable: bool = True,
        trailing_cursor: bool = False,
        key=None,
    ):
        super().__init__(key=key)
        self.content = content or ""
        self.base_style = base_style
        self.selectable = selectable
        self.trailing_cursor = trailing_cursor

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        blocks = _RockyMarkdownParser(self.content).parse()
        selection_color = color_scheme.primary.withOpacity(0.28)
        renderer = _RockyMarkdownRenderer(
            base_style=self.base_style,
            color_scheme=color_scheme,
            selectable=self.selectable,
            selection_color=selection_color,
        )
        children = []
        previous_block = None
        for index, block in enumerate(blocks):
            if previous_block is not None:
                children.append(SizedBox(height=_block_gap(previous_block, block)))
            is_last = index == len(blocks) - 1
            attach_cursor = self.trailing_cursor and is_last
            if attach_cursor:
                children.append(
                    Row(
                        crossAxisAlignment=CrossAxisAlignment.end,
                        mainAxisSize=MainAxisSize.min,
                        children=[
                            Expanded(child=renderer.render(block)),
                            renderer.cursor_widget(),
                        ],
                    )
                )
            else:
                children.append(renderer.render(block))
            previous_block = block
        if self.trailing_cursor and not blocks:
            children.append(renderer.cursor_widget())
        if not children:
            return SizedBox(width=0, height=0)
        column = Column(
            crossAxisAlignment=CrossAxisAlignment.start,
            mainAxisSize=MainAxisSize.min,
            children=children,
        )
        if self.selectable:
            return SelectionArea(child=column)
        return column


def _block_gap(prev, curr):
    if curr.kind in _LIST_BLOCK_KINDS:
        return _LIST_SIBLING_GAP
    return _DEFAULT_BLOCK_GAP


class _Block:
    __slots__ = (
        "kind",
        "lines",
        "level",
        "ordinals",
        "rows",
        "alignments",
        "checked",
        "children",
    )

    def __init__(
        self,
        kind,
        *,
        lines=None,
        level=0,
        ordinals=None,
        rows=None,
        alignments=None,
        checked=False,
        children=None,
    ):
        self.kind = kind
        self.lines = lines if lines is not None else []
        self.level = level
        self.ordinals = ordinals if ordinals is not None else []
        self.rows = rows if rows is not None else []
        self.alignments = alignments if alignments is not None else []
        self.checked = checked
        self.children = children if children is not None else []


class _RockyMarkdownParser:
    def __init__(self, content):
        self.content = content

    def parse(self):
        return _parse_blocks(self.content.split("\n"))


def _parse_blocks(lines):
    blocks = []
    current_paragraph = None
    in_code = False
    code_block = None

    def flush_paragraph():
        nonlocal current_paragraph
        if current_paragraph is not None:
            blocks.append(current_paragraph)
            current_paragraph = None

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        if in_code:
            if _FENCE_PATTERN.match(raw_line):
                blocks.append(code_block)
                in_code = False
            else:
                code_block.lines.append(raw_line)
            index += 1
            continue

        fence = _FENCE_PATTERN.match(raw_line)
        if fence:
            flush_paragraph()
            in_code = True
            code_block = _Block("code")
            index += 1
            continue

        stripped = raw_line.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if _RULE_PATTERN.match(raw_line):
            flush_paragraph()
            blocks.append(_Block("rule"))
            index += 1
            continue

        if (
            _TABLE_ROW_PATTERN.match(raw_line)
            and index + 1 < len(lines)
            and _TABLE_SEPARATOR_PATTERN.match(lines[index + 1])
        ):
            flush_paragraph()
            table_block, consumed = _consume_table(lines, index)
            blocks.append(table_block)
            index += consumed
            continue

        heading = _HEADING_PATTERN.match(raw_line)
        if heading:
            flush_paragraph()
            blocks.append(
                _Block(
                    "heading",
                    lines=[heading.group(2)],
                    level=len(heading.group(1)),
                )
            )
            index += 1
            continue

        bullet = _BULLET_PATTERN.match(raw_line)
        numbered = None if bullet else _NUMBERED_PATTERN.match(raw_line)
        if bullet or numbered:
            flush_paragraph()
            if bullet:
                leading = len(bullet.group(1))
                marker_len = 2  # marker char + single space
                first_body = bullet.group(3)
                task = _TASK_PATTERN.match(first_body)
                if task:
                    kind = "task"
                    checked = task.group(1) in ("x", "X")
                    first_body = task.group(2)
                else:
                    kind = "bullet"
                    checked = False
                ordinals = []
            else:
                leading = len(numbered.group(1))
                num_str = numbered.group(2)
                marker_len = len(num_str) + 2  # digits + ". "
                first_body = numbered.group(3)
                kind = "numbered"
                checked = False
                ordinals = [int(num_str)]

            content_column = leading + marker_len
            item_lines = [first_body]
            next_index = index + 1
            while next_index < len(lines):
                nxt = lines[next_index]
                if not nxt.strip():
                    item_lines.append("")
                    next_index += 1
                    continue
                lead = len(nxt) - len(nxt.lstrip(" "))
                if lead >= content_column:
                    item_lines.append(nxt[content_column:])
                    next_index += 1
                    continue
                break
            while item_lines and not item_lines[-1].strip():
                item_lines.pop()
            blocks.append(
                _Block(
                    kind,
                    children=_parse_blocks(item_lines),
                    ordinals=ordinals,
                    checked=checked,
                )
            )
            index = next_index
            continue

        quote = _QUOTE_PATTERN.match(raw_line)
        if quote:
            if blocks and blocks[-1].kind == "quote" and current_paragraph is None:
                blocks[-1].lines.append(quote.group(1))
            else:
                flush_paragraph()
                blocks.append(_Block("quote", lines=[quote.group(1)]))
            index += 1
            continue

        if current_paragraph is None:
            current_paragraph = _Block("paragraph", lines=[stripped])
        else:
            current_paragraph.lines.append(stripped)
        index += 1

    flush_paragraph()
    if in_code:
        blocks.append(code_block)
    return blocks


def _consume_table(lines, start):
    header_cells = _split_table_row(lines[start])
    alignments = _parse_alignment_row(lines[start + 1], len(header_cells))
    rows = [header_cells]
    cursor = start + 2
    while cursor < len(lines) and _TABLE_ROW_PATTERN.match(lines[cursor]):
        row_cells = _split_table_row(lines[cursor])
        if len(row_cells) < len(header_cells):
            row_cells = row_cells + [""] * (len(header_cells) - len(row_cells))
        elif len(row_cells) > len(header_cells):
            row_cells = row_cells[: len(header_cells)]
        rows.append(row_cells)
        cursor += 1
    return _Block("table", rows=rows, alignments=alignments), cursor - start


def _split_table_row(line):
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _build_image(url):
    if not url:
        return None
    lowered = url.lower()
    if lowered.startswith(("http://", "https://")):
        return Image.network(
            url,
            width=_INLINE_IMAGE_MAX,
            height=_INLINE_IMAGE_MAX,
            fit=BoxFit.contain,
        )
    if lowered.startswith("file://"):
        path = url[7:]
    elif "://" in lowered:
        return None
    else:
        path = url
    return Image.file(
        File(path),
        width=_INLINE_IMAGE_MAX,
        height=_INLINE_IMAGE_MAX,
        fit=BoxFit.contain,
    )


def _parse_alignment_row(line, expected_count):
    cells = _split_table_row(line)
    alignments = []
    for cell in cells:
        cleaned = cell.strip()
        starts = cleaned.startswith(":")
        ends = cleaned.endswith(":")
        if starts and ends:
            alignments.append("center")
        elif ends:
            alignments.append("right")
        else:
            alignments.append("left")
    while len(alignments) < expected_count:
        alignments.append("left")
    return alignments[:expected_count]


def _list_marker_width(block):
    if block.kind == "numbered":
        ordinal = block.ordinals[0] if block.ordinals else 1
        return max(3, len(f"{ordinal}."))
    return 3


def _line_height(style):
    font_size = style.fontSize or 14
    return max(font_size * (style.height or 1.0), font_size + 2)


class _RockyMarkdownRenderer:
    def __init__(
        self, *, base_style: TextStyle, color_scheme, selectable: bool, selection_color
    ):
        self.base_style = base_style
        self.color_scheme = color_scheme
        self.selectable = selectable
        self.selection_color = selection_color

    def render(self, block):
        if block.kind == "heading":
            return self._render_heading(block)
        if block.kind == "bullet":
            return self._render_list_item(
                block, marker=Text("\u2022", style=self.base_style)
            )
        if block.kind == "task":
            return self._render_list_item(
                block, marker=self._task_checkbox_widget(block.checked)
            )
        if block.kind == "numbered":
            ordinal = block.ordinals[0] if block.ordinals else 1
            return self._render_list_item(
                block, marker=Text(f"{ordinal}.", style=self.base_style)
            )
        if block.kind == "code":
            return self._render_code_block(block)
        if block.kind == "quote":
            return self._render_quote(block)
        if block.kind == "rule":
            return self._render_rule()
        if block.kind == "table":
            return self._render_table(block)
        return self._render_paragraph(block)

    def cursor_widget(self):
        height = self.base_style.fontSize
        return Container(
            width=1.5,
            height=height,
            margin=EdgeInsets.only(left=2),
            color=self.color_scheme.primary,
        )

    def _render_paragraph(self, block):
        text = "\n".join(line.strip() for line in block.lines)
        return self._rich_text(self._inline_spans(text), style=self.base_style)

    def _render_heading(self, block):
        style = TextStyle(
            color=self.base_style.color,
            fontSize=_HEADING_SIZES.get(block.level, 14),
            fontWeight=FontWeight.w700,
        )
        return self._rich_text(self._inline_spans(block.lines[0]), style=style)

    def _render_list_item(self, block, *, marker):
        marker_column = Container(
            width=_list_marker_width(block) * _LIST_MARKER_CHAR_WIDTH,
            height=_line_height(self.base_style),
            alignment=Alignment.centerLeft,
            child=marker,
        )
        body_children = []
        for index, child in enumerate(block.children):
            if index > 0:
                body_children.append(SizedBox(height=_LIST_SIBLING_GAP))
            body_children.append(self.render(child))
        if not body_children:
            return marker_column
        return Row(
            crossAxisAlignment=CrossAxisAlignment.start,
            children=[
                marker_column,
                Expanded(
                    child=Column(
                        crossAxisAlignment=CrossAxisAlignment.start,
                        mainAxisSize=MainAxisSize.min,
                        children=body_children,
                    )
                ),
            ],
        )

    def _task_checkbox_span(self, checked):
        return WidgetSpan(
            alignment=PlaceholderAlignment.middle,
            child=self._task_checkbox_widget(checked),
        )

    def _task_checkbox_widget(self, checked):
        icon_data = Icons.check_box if checked else Icons.check_box_outline_blank
        size = (self.base_style.fontSize or 14) + 2
        return SelectionContainer.disabled(
            child=Icon(
                icon_data,
                size=size,
                color=(
                    self.color_scheme.primary if checked else self.color_scheme.outline
                ),
            ),
        )

    def _render_code_block(self, block):
        body = "\n".join(block.lines)
        style = TextStyle(
            color=self.base_style.color,
            fontSize=self.base_style.fontSize,
            fontFamily=RockySystem.monospace_font_family(),
            fontFamilyFallback=RockySystem.monospace_font_family_fallback(),
        )
        text_widget = Text(body, style=style, selectionColor=self.selection_color)
        return Container(
            padding=EdgeInsets.symmetric(horizontal=10, vertical=8),
            decoration=BoxDecoration(
                color=self.color_scheme.surfaceContainerHighest,
                borderRadius=BorderRadius.circular(6),
                border=Border.all(width=1, color=self.color_scheme.outlineVariant),
            ),
            child=text_widget,
        )

    def _render_quote(self, block):
        text = "\n".join(line for line in block.lines)
        quoted_style = TextStyle(
            color=self.color_scheme.onSurfaceVariant,
            fontSize=self.base_style.fontSize,
            fontStyle=FontStyle.italic,
        )
        spans = self._inline_spans(text, style_override=quoted_style)
        rich = self._rich_text(spans, style=quoted_style)
        return Container(
            padding=EdgeInsets.fromLTRB(10, 6, 10, 6),
            decoration=BoxDecoration(
                color=self.color_scheme.surfaceContainerHigh,
                borderRadius=BorderRadius.circular(4),
                border=Border(
                    left=BorderSide(
                        width=3,
                        color=self.color_scheme.primary.withOpacity(0.6),
                    ),
                ),
            ),
            child=rich,
        )

    def _rich_text(self, children, *, style):
        root = TextSpan(style=style, children=children)
        return Text.rich(root, style=style, selectionColor=self.selection_color)

    def _inline_spans(self, text, *, style_override=None):
        spans = []
        cursor = 0
        for match in _INLINE_PATTERN.finditer(text):
            if match.start() > cursor:
                spans.append(TextSpan(text=text[cursor : match.start()]))
            if match.group("escape") is not None:
                spans.append(TextSpan(text=match.group("escape")))
            elif match.group("code_body") is not None:
                spans.append(self._inline_code_span(match.group("code_body")))
            elif (
                match.group("bolditalic") is not None
                or match.group("bolditalic_u") is not None
            ):
                spans.append(
                    TextSpan(
                        text=match.group("bolditalic") or match.group("bolditalic_u"),
                        style=TextStyle(
                            fontWeight=FontWeight.w700,
                            fontStyle=FontStyle.italic,
                        ),
                    )
                )
            elif match.group("bold") is not None or match.group("bold_u") is not None:
                spans.append(
                    TextSpan(
                        text=match.group("bold") or match.group("bold_u"),
                        style=TextStyle(fontWeight=FontWeight.w700),
                    )
                )
            elif match.group("strike") is not None:
                spans.append(
                    TextSpan(
                        text=match.group("strike"),
                        style=TextStyle(
                            decoration=TextDecoration.lineThrough,
                            decorationThickness=2.0,
                            decorationColor=self.base_style.color,
                        ),
                    )
                )
            elif (
                match.group("italic_a") is not None
                or match.group("italic_u") is not None
            ):
                spans.append(
                    TextSpan(
                        text=match.group("italic_a") or match.group("italic_u"),
                        style=TextStyle(fontStyle=FontStyle.italic),
                    )
                )
            elif match.group("link_text") is not None:
                spans.append(
                    self._link_span(
                        text=match.group("link_text"),
                        url=match.group("link_url"),
                    )
                )
            elif match.group("image_alt") is not None:
                spans.append(
                    self._image_span(
                        alt=match.group("image_alt") or "",
                        url=match.group("image_url"),
                    )
                )
            cursor = match.end()
        if cursor < len(text):
            spans.append(TextSpan(text=text[cursor:]))
        if style_override is not None and not spans:
            spans.append(TextSpan(text=text, style=style_override))
        return spans

    def _inline_code_span(self, body):
        code_style = TextStyle(
            color=self.base_style.color,
            fontSize=self.base_style.fontSize,
            fontFamily=RockySystem.monospace_font_family(),
            fontFamilyFallback=RockySystem.monospace_font_family_fallback(),
            height=self.base_style.height,
        )
        return WidgetSpan(
            alignment=PlaceholderAlignment.middle,
            child=Container(
                padding=EdgeInsets.symmetric(horizontal=5, vertical=1),
                decoration=BoxDecoration(
                    color=self.color_scheme.surfaceContainerHighest.withOpacity(0.72),
                    borderRadius=BorderRadius.circular(4),
                ),
                child=Text(body, style=code_style),
            ),
        )

    def _link_span(self, *, text, url):
        recognizer = TapGestureRecognizer()
        recognizer.onTap = lambda: RockySystem.open_url(url)
        link_style = TextStyle(
            color=self.color_scheme.primary,
            decoration=TextDecoration.underline,
            fontSize=self.base_style.fontSize,
        )
        return TextSpan(
            text=text,
            style=link_style,
            recognizer=recognizer,
            mouseCursor=SystemMouseCursors.click,
        )

    def _image_span(self, *, alt, url):
        image_widget = _build_image(url)
        if image_widget is None:
            return self._link_span(text=f"\U0001f5bc {alt or url}", url=url)
        return WidgetSpan(
            alignment=PlaceholderAlignment.middle,
            child=SelectionContainer.disabled(
                child=MouseRegion(
                    cursor=SystemMouseCursors.click,
                    child=Material(
                        color=Colors.transparent,
                        child=InkWell(
                            onTap=lambda: RockySystem.open_url(url),
                            borderRadius=BorderRadius.circular(4),
                            child=Container(
                                margin=EdgeInsets.symmetric(horizontal=2, vertical=2),
                                decoration=BoxDecoration(
                                    borderRadius=BorderRadius.circular(4),
                                    border=Border.all(
                                        width=1,
                                        color=self.color_scheme.outlineVariant,
                                    ),
                                ),
                                child=ClipRRect(
                                    borderRadius=BorderRadius.circular(3),
                                    child=image_widget,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )

    def _render_rule(self):
        return Container(
            margin=EdgeInsets.symmetric(vertical=4),
            height=1,
            color=self.color_scheme.outlineVariant,
        )

    def _render_table(self, block):
        if not block.rows:
            return SizedBox(width=0, height=0)
        column_count = len(block.rows[0])
        alignments = list(block.alignments)
        while len(alignments) < column_count:
            alignments.append("left")

        rows = []
        for row_index, cells in enumerate(block.rows):
            is_header = row_index == 0
            row_children = []
            for column_index in range(column_count):
                cell_text = cells[column_index] if column_index < len(cells) else ""
                row_children.append(
                    Expanded(
                        child=Container(
                            padding=EdgeInsets.symmetric(horizontal=8, vertical=6),
                            decoration=BoxDecoration(
                                border=Border(
                                    left=(
                                        BorderSide(
                                            width=1,
                                            color=self.color_scheme.outlineVariant,
                                        )
                                        if column_index > 0
                                        else BorderSide(
                                            width=0, color=Colors.transparent
                                        )
                                    ),
                                ),
                            ),
                            child=self._render_table_cell(
                                cell_text,
                                alignment=alignments[column_index],
                                is_header=is_header,
                            ),
                        ),
                    )
                )
            row_container = Container(
                decoration=BoxDecoration(
                    color=(
                        self.color_scheme.surfaceContainerHigh if is_header else None
                    ),
                    border=(
                        Border(
                            bottom=BorderSide(
                                width=1,
                                color=self.color_scheme.outlineVariant,
                            )
                        )
                        if row_index < len(block.rows) - 1
                        else None
                    ),
                ),
                child=Row(
                    crossAxisAlignment=CrossAxisAlignment.start,
                    children=row_children,
                ),
            )
            rows.append(row_container)

        return Container(
            decoration=BoxDecoration(
                color=self.color_scheme.surface,
                borderRadius=BorderRadius.circular(6),
                border=Border.all(width=1, color=self.color_scheme.outlineVariant),
            ),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                mainAxisSize=MainAxisSize.min,
                children=rows,
            ),
        )

    def _render_table_cell(self, text, *, alignment, is_header):
        cell_style = TextStyle(
            color=self.base_style.color,
            fontSize=self.base_style.fontSize,
            fontWeight=FontWeight.w700 if is_header else None,
        )
        text_align = {
            "left": TextAlign.left,
            "center": TextAlign.center,
            "right": TextAlign.right,
        }.get(alignment, TextAlign.left)
        spans = self._inline_spans(text)
        root = TextSpan(style=cell_style, children=spans)
        return Text.rich(
            root,
            style=cell_style,
            textAlign=text_align,
            selectionColor=self.selection_color,
        )
