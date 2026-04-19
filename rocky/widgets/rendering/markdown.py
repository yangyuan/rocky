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
    SelectableText,
    Theme,
)
from flut.flutter.painting import (
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
from flut.flutter.services import SystemMouseCursors
from flut.flutter.widgets import (
    ClipRRect,
    Column,
    Container,
    Expanded,
    Icon,
    Image,
    MouseRegion,
    Row,
    SizedBox,
    StatelessWidget,
    Text,
    WidgetSpan,
)

from rocky.system import RockySystem

_HEADING_SIZES = {1: 20, 2: 18, 3: 16, 4: 15, 5: 14, 6: 14}
_INLINE_IMAGE_MAX = 128.0
_RUN_BLOCK_KINDS = frozenset({"paragraph", "heading", "bullet", "numbered", "task"})

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
        renderer = _RockyMarkdownRenderer(
            base_style=self.base_style,
            color_scheme=color_scheme,
            selectable=self.selectable,
        )
        groups = _group_blocks(blocks)
        children = []
        previous_last_block = None
        for index, group in enumerate(groups):
            first_block = group[0]
            if previous_last_block is not None:
                children.append(
                    SizedBox(height=_block_gap(previous_last_block, first_block))
                )
            is_last = index == len(groups) - 1
            attach_cursor = self.trailing_cursor and is_last
            if first_block.kind in _RUN_BLOCK_KINDS:
                children.append(
                    renderer.render_run(group, trailing_cursor=attach_cursor)
                )
            elif attach_cursor:
                children.append(
                    Row(
                        crossAxisAlignment=CrossAxisAlignment.end,
                        mainAxisSize=MainAxisSize.min,
                        children=[
                            Expanded(child=renderer.render(first_block)),
                            renderer.cursor_widget(),
                        ],
                    )
                )
            else:
                children.append(renderer.render(first_block))
            previous_last_block = group[-1]
        if self.trailing_cursor and not groups:
            children.append(renderer.cursor_widget())
        if not children:
            return SizedBox(width=0, height=0)
        return Column(
            crossAxisAlignment=CrossAxisAlignment.start,
            mainAxisSize=MainAxisSize.min,
            children=children,
        )


def _group_blocks(blocks):
    groups = []
    run = []
    for block in blocks:
        if block.kind in _RUN_BLOCK_KINDS:
            run.append(block)
            continue
        if run:
            groups.append(run)
            run = []
        groups.append([block])
    if run:
        groups.append(run)
    return groups


def _block_gap(prev, curr):
    tight_kinds = ("bullet", "numbered", "quote", "task")
    if prev.kind in tight_kinds and curr.kind == prev.kind:
        return 2
    return 8


class _Block:
    __slots__ = (
        "kind",
        "lines",
        "level",
        "indent",
        "ordinals",
        "rows",
        "alignments",
        "checked",
    )

    def __init__(
        self,
        kind,
        *,
        lines=None,
        level=0,
        indent=0,
        ordinals=None,
        rows=None,
        alignments=None,
        checked=False,
    ):
        self.kind = kind
        self.lines = lines if lines is not None else []
        self.level = level
        self.indent = indent
        self.ordinals = ordinals if ordinals is not None else []
        self.rows = rows if rows is not None else []
        self.alignments = alignments if alignments is not None else []
        self.checked = checked


class _RockyMarkdownParser:
    def __init__(self, content):
        self.content = content

    def parse(self):
        blocks = []
        current_paragraph = None
        in_code = False
        code_block = None

        def flush_paragraph():
            nonlocal current_paragraph
            if current_paragraph is not None:
                blocks.append(current_paragraph)
                current_paragraph = None

        lines = self.content.split("\n")
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
                table_block, consumed = self._consume_table(lines, index)
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
            if bullet:
                flush_paragraph()
                body = bullet.group(3)
                indent = len(bullet.group(1)) // 2
                task = _TASK_PATTERN.match(body)
                if task:
                    blocks.append(
                        _Block(
                            "task",
                            lines=[task.group(2)],
                            indent=indent,
                            checked=task.group(1) in ("x", "X"),
                        )
                    )
                else:
                    blocks.append(
                        _Block(
                            "bullet",
                            lines=[body],
                            indent=indent,
                        )
                    )
                index += 1
                continue

            numbered = _NUMBERED_PATTERN.match(raw_line)
            if numbered:
                flush_paragraph()
                blocks.append(
                    _Block(
                        "numbered",
                        lines=[numbered.group(3)],
                        indent=len(numbered.group(1)) // 2,
                        ordinals=[int(numbered.group(2))],
                    )
                )
                index += 1
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

    @staticmethod
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


class _RockyMarkdownRenderer:
    def __init__(self, *, base_style: TextStyle, color_scheme, selectable: bool):
        self.base_style = base_style
        self.color_scheme = color_scheme
        self.selectable = selectable

    def render(self, block):
        if block.kind == "heading":
            return self._render_heading(block)
        if block.kind == "bullet":
            return self._render_list_item(
                block, marker=TextSpan(text="\u2022  ", style=self.base_style)
            )
        if block.kind == "task":
            return self._render_list_item(
                block, marker=self._task_checkbox_span(block.checked)
            )
        if block.kind == "numbered":
            ordinal = block.ordinals[0] if block.ordinals else 1
            return self._render_list_item(
                block, marker=TextSpan(text=f"{ordinal}.  ", style=self.base_style)
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

    def render_run(self, blocks, *, trailing_cursor: bool = False):
        children = []
        for index, block in enumerate(blocks):
            if index > 0:
                previous = blocks[index - 1]
                tight = (
                    previous.kind in ("bullet", "numbered", "task")
                    and block.kind == previous.kind
                )
                children.append(TextSpan(text="\n" if tight else "\n\n"))
            children.append(self._block_span(block))
        if trailing_cursor:
            children.append(self.cursor_span())
        root = TextSpan(style=self.base_style, children=children)
        if self.selectable:
            return SelectableText.rich(root, style=self.base_style)
        return Text.rich(root, style=self.base_style)

    def cursor_widget(self):
        height = self.base_style.fontSize
        return Container(
            width=1.5,
            height=height,
            margin=EdgeInsets.only(left=2),
            color=self.color_scheme.primary,
        )

    def cursor_span(self):
        return WidgetSpan(
            alignment=PlaceholderAlignment.middle,
            child=self.cursor_widget(),
        )

    def _block_span(self, block):
        if block.kind == "heading":
            text = block.lines[0] if block.lines else ""
            return TextSpan(
                style=TextStyle(
                    color=self.base_style.color,
                    fontSize=_HEADING_SIZES.get(block.level, 14),
                    fontWeight=FontWeight.w700,
                ),
                children=self._inline_spans(text),
            )
        if block.kind in ("bullet", "numbered", "task"):
            text = " ".join(line.strip() for line in block.lines)
            indent_prefix = "    " * max(0, block.indent)
            children = []
            if indent_prefix:
                children.append(TextSpan(text=indent_prefix))
            if block.kind == "task":
                children.append(self._task_checkbox_span(block.checked))
                children.append(TextSpan(text=" "))
            elif block.kind == "bullet":
                children.append(TextSpan(text="\u2022  "))
            else:
                ordinal = block.ordinals[0] if block.ordinals else 1
                children.append(TextSpan(text=f"{ordinal}.  "))
            children.extend(self._inline_spans(text))
            return TextSpan(style=self.base_style, children=children)
        text = " ".join(line.strip() for line in block.lines)
        return TextSpan(style=self.base_style, children=self._inline_spans(text))

    def _render_paragraph(self, block):
        text = " ".join(line.strip() for line in block.lines)
        return self._rich_text(self._inline_spans(text), style=self.base_style)

    def _render_heading(self, block):
        style = TextStyle(
            color=self.base_style.color,
            fontSize=_HEADING_SIZES.get(block.level, 14),
            fontWeight=FontWeight.w700,
        )
        return self._rich_text(self._inline_spans(block.lines[0]), style=style)

    def _render_list_item(self, block, *, marker):
        text = " ".join(line.strip() for line in block.lines)
        spans = [marker] + self._inline_spans(text)
        rich = self._rich_text(spans, style=self.base_style)
        if block.indent <= 0:
            return rich
        return Container(
            padding=EdgeInsets.only(left=16.0 * block.indent),
            child=rich,
        )

    def _task_checkbox_span(self, checked):
        icon_data = Icons.check_box if checked else Icons.check_box_outline_blank
        size = (self.base_style.fontSize or 14) + 2
        return WidgetSpan(
            alignment=PlaceholderAlignment.middle,
            child=Container(
                margin=EdgeInsets.only(right=6),
                child=Icon(
                    icon_data,
                    size=size,
                    color=(
                        self.color_scheme.primary
                        if checked
                        else self.color_scheme.outline
                    ),
                ),
            ),
        )

    def _render_code_block(self, block):
        body = "\n".join(block.lines)
        style = TextStyle(
            color=self.base_style.color,
            fontSize=12.5,
            fontFamily=RockySystem.monospace_font_family(),
            fontFamilyFallback=RockySystem.monospace_font_family_fallback(),
            height=1.35,
        )
        text_widget = (
            SelectableText(body, style=style)
            if self.selectable
            else Text(body, style=style)
        )
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
        if self.selectable:
            return SelectableText.rich(root, style=style)
        return Text.rich(root, style=style)

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
        mono_style = TextStyle(
            color=self.base_style.color,
            fontSize=(self.base_style.fontSize or 14) - 1,
            fontFamily=RockySystem.monospace_font_family(),
            fontFamilyFallback=RockySystem.monospace_font_family_fallback(),
        )
        return WidgetSpan(
            alignment=PlaceholderAlignment.middle,
            child=Container(
                padding=EdgeInsets.symmetric(horizontal=4, vertical=1),
                margin=EdgeInsets.symmetric(horizontal=1),
                decoration=BoxDecoration(
                    color=self.color_scheme.surfaceContainerHighest,
                    borderRadius=BorderRadius.circular(3),
                    border=Border.all(
                        width=1,
                        color=self.color_scheme.outlineVariant,
                    ),
                ),
                child=(
                    SelectableText(body, style=mono_style)
                    if self.selectable
                    else Text(body, style=mono_style)
                ),
            ),
        )

    def _link_span(self, *, text, url):
        link_style = TextStyle(
            color=self.color_scheme.primary,
            decoration=TextDecoration.underline,
            fontSize=self.base_style.fontSize,
        )
        return WidgetSpan(
            alignment=PlaceholderAlignment.middle,
            child=MouseRegion(
                cursor=SystemMouseCursors.click,
                child=Material(
                    color=Colors.transparent,
                    child=InkWell(
                        onTap=lambda: RockySystem.open_url(url),
                        child=Text(text, style=link_style),
                    ),
                ),
            ),
        )

    def _image_span(self, *, alt, url):
        image_widget = _build_image(url)
        if image_widget is None:
            return self._link_span(text=f"\U0001f5bc {alt or url}", url=url)
        return WidgetSpan(
            alignment=PlaceholderAlignment.middle,
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
        if self.selectable:
            return SelectableText.rich(root, style=cell_style, textAlign=text_align)
        return Text.rich(root, style=cell_style, textAlign=text_align)
