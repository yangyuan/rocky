from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from flut.dart.typed_data import Uint8List
from flut.dart.ui import FontWeight
from flut.flutter.foundation.key import ValueKey
from flut.flutter.material import Colors, Icons, InkWell, Material, Theme
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisSize
from flut.flutter.widgets import (
    ClipRRect,
    Container,
    Flexible,
    Icon,
    Image,
    Row,
    SizedBox,
    StatelessWidget,
    Text,
    Wrap,
)

from rocky.services.attachments import RockyAttachments
from rocky.contracts.chat import RockyAttachment
from rocky.system import RockySystem


class RockyAttachmentPicker:
    _FILETYPES: list[tuple[str, str]] = [
        (
            "All supported files",
            " ".join(f"*{ext}" for ext in RockyAttachments.SUPPORTED_EXTENSIONS),
        ),
        (
            "Images",
            " ".join(f"*{ext}" for ext in RockyAttachments.IMAGE_MIME_TYPES),
        ),
        (
            "Text files",
            " ".join(f"*{ext}" for ext in RockyAttachments.TEXT_MIME_TYPES),
        ),
        ("All files", "*.*"),
    ]

    @classmethod
    def pick(cls) -> list[RockyAttachment]:
        paths = RockySystem.tk_select_files_with_types(
            title="Attach files",
            filetypes=cls._FILETYPES,
        )
        results: list[RockyAttachment] = []
        for raw_path in paths:
            attachment = RockyAttachments.load(Path(raw_path))
            if attachment is not None:
                results.append(attachment)
        return results


class RockyAttachmentChip(StatelessWidget):
    def __init__(
        self,
        *,
        attachment: RockyAttachment,
        on_remove: Optional[Callable[[], None]] = None,
        key=None,
    ):
        super().__init__(key=key)
        self.attachment = attachment
        self.on_remove = on_remove

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        attachment = self.attachment
        if RockyAttachments.is_image(attachment):
            leading = ClipRRect(
                borderRadius=BorderRadius.circular(4),
                child=Image.memory(
                    Uint8List(RockyAttachments.decoded_bytes(attachment)),
                    width=22,
                    height=22,
                    gaplessPlayback=True,
                    excludeFromSemantics=True,
                ),
            )
        else:
            leading = Icon(
                Icons.description,
                size=16,
                color=color_scheme.onSurfaceVariant,
            )

        children = [
            leading,
            SizedBox(width=6),
            Flexible(
                child=Text(
                    attachment.filename,
                    style=TextStyle(
                        fontSize=12,
                        color=color_scheme.onSurface,
                    ),
                ),
            ),
        ]
        if self.on_remove is not None:
            children.append(SizedBox(width=4))
            children.append(
                Material(
                    color=Colors.transparent,
                    child=InkWell(
                        onTap=self.on_remove,
                        borderRadius=BorderRadius.circular(8),
                        child=Container(
                            padding=EdgeInsets.all(2),
                            child=Icon(
                                Icons.close,
                                size=14,
                                color=color_scheme.onSurfaceVariant,
                            ),
                        ),
                    ),
                )
            )

        return Container(
            padding=EdgeInsets.fromLTRB(8, 4, 4, 4),
            decoration=BoxDecoration(
                color=color_scheme.surfaceContainerHighest,
                borderRadius=BorderRadius.circular(8),
                border=Border.all(width=1, color=color_scheme.outlineVariant),
            ),
            child=Row(
                mainAxisSize=MainAxisSize.min,
                crossAxisAlignment=CrossAxisAlignment.center,
                children=children,
            ),
        )


class RockyAttachmentComposerStrip(StatelessWidget):
    def __init__(
        self,
        *,
        attachments: list[RockyAttachment],
        on_remove: Optional[Callable[[int], None]] = None,
        key=None,
    ):
        super().__init__(key=key)
        self.attachments = attachments
        self.on_remove = on_remove

    def build(self, context):
        if not self.attachments:
            return SizedBox(width=0, height=0)
        chips = [
            RockyAttachmentChip(
                attachment=attachment,
                on_remove=(
                    (lambda index=index: self.on_remove(index))
                    if self.on_remove is not None
                    else None
                ),
            )
            for index, attachment in enumerate(self.attachments)
        ]
        return Container(
            padding=EdgeInsets.fromLTRB(2, 0, 2, 8),
            child=Wrap(spacing=6, runSpacing=6, children=chips),
        )


class RockyAttachmentBubbleStrip(StatelessWidget):
    def __init__(
        self,
        *,
        attachments: list[RockyAttachment],
        key=None,
    ):
        super().__init__(key=key)
        self.attachments = attachments

    def build(self, context):
        if not self.attachments:
            return SizedBox(width=0, height=0)
        color_scheme = Theme.of(context).colorScheme
        items = []
        for attachment in self.attachments:
            if RockyAttachments.is_image(attachment):
                items.append(
                    ClipRRect(
                        borderRadius=BorderRadius.circular(6),
                        child=Image.memory(
                            Uint8List(RockyAttachments.decoded_bytes(attachment)),
                            width=120,
                            height=120,
                            gaplessPlayback=True,
                            excludeFromSemantics=True,
                            key=ValueKey(f"attachment_image_{attachment.filename}"),
                        ),
                    )
                )
            else:
                items.append(
                    Container(
                        padding=EdgeInsets.fromLTRB(8, 4, 8, 4),
                        decoration=BoxDecoration(
                            color=color_scheme.surfaceContainerHighest,
                            borderRadius=BorderRadius.circular(6),
                            border=Border.all(
                                width=0.5, color=color_scheme.outlineVariant
                            ),
                        ),
                        child=Row(
                            mainAxisSize=MainAxisSize.min,
                            crossAxisAlignment=CrossAxisAlignment.center,
                            children=[
                                Icon(
                                    Icons.description,
                                    size=14,
                                    color=color_scheme.onSurfaceVariant,
                                ),
                                SizedBox(width=6),
                                Text(
                                    attachment.filename,
                                    style=TextStyle(
                                        fontSize=12,
                                        fontWeight=FontWeight.w500,
                                        color=color_scheme.onSurface,
                                    ),
                                ),
                            ],
                        ),
                    )
                )
        return Container(
            padding=EdgeInsets.only(bottom=6),
            child=Wrap(spacing=6, runSpacing=6, children=items),
        )
