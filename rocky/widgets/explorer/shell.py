import asyncio
import os
import shlex
import shutil
from pathlib import Path

from flut.dart import Brightness, Color
from flut.dart.ui import Clip
from flut.flutter.material import (
    Card,
    CircularProgressIndicator,
    Colors,
    Dialog,
    IconButton,
    Icons,
    InkWell,
    Theme,
    showDialog,
)
from flut.flutter.painting import (
    Alignment,
    Axis,
    Border,
    BorderRadius,
    BoxDecoration,
    BoxShape,
    EdgeInsets,
    RoundedRectangleBorder,
    TextOverflow,
    TextStyle,
)
from flut.flutter.rendering import MainAxisAlignment, MainAxisSize, WrapAlignment
from flut.flutter.rendering.box import BoxConstraints
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    GestureDetector,
    Icon,
    MediaQuery,
    Overlay,
    OverlayEntry,
    Positioned,
    Row,
    SingleChildScrollView,
    SizedBox,
    Stack,
    State,
    StatefulWidget,
    Text,
    Wrap,
)
from flut.flutter.widgets.navigator import Navigator

from rocky.agentic.tools.shell_provider import ShellProvider, ShellType
from rocky.contracts.shell import RockyShellProfile
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.shells.type_picker import RockyShellTemplates


class RockyShellExplorerDialog:
    @classmethod
    def open(
        cls,
        context,
        profile: RockyShellProfile,
        local_workdir: str | None = None,
    ) -> None:
        error = cls.profile_error(profile)
        provider = None if error else cls.profile_provider(profile, local_workdir)
        title = RockyShellTemplates.display_name(profile)
        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(24),
                child=RockyDialog(
                    title=f"Environment Explorer - {title}",
                    leading_icon=Icons.folder_open,
                    on_close=lambda: Navigator.pop(dialog_context),
                    body=Container(
                        width=840,
                        height=560,
                        child=RockyShellExplorer(
                            provider=provider,
                            initial_error=error,
                        ),
                    ),
                ),
            ),
        )

    @classmethod
    def open_shell(
        cls,
        context,
        shell_profiles,
        shell_profile_id: str,
        local_workdir: str | None = None,
    ) -> None:
        shell_profile = next(
            (
                candidate
                for candidate in (shell_profiles or [])
                if candidate.id == shell_profile_id
            ),
            None,
        )
        if shell_profile is None:
            return
        cls.open(context, shell_profile, local_workdir)

    @classmethod
    def profile_provider(
        cls,
        profile: RockyShellProfile,
        local_workdir: str | None = None,
    ) -> ShellProvider | None:
        if cls.profile_error(profile):
            return None
        return ShellProvider(
            profile.name,
            ShellType(profile.shell_type),
            shell_host=profile.host or None,
            local_workdir=local_workdir,
            output_max_head_tail=profile.output_max_head_tail,
        )

    @classmethod
    def profile_error(cls, profile: RockyShellProfile) -> str:
        try:
            ShellType(profile.shell_type)
        except ValueError:
            return (
                "Environment Explorer is unavailable because this environment type "
                f"is not supported: {profile.shell_type}."
            )
        if (
            RockyShellTemplates.requires_name(profile.shell_type)
            and not profile.name.strip()
        ):
            return (
                "Environment Explorer is unavailable because this environment has "
                "no Docker name."
            )
        if (
            RockyShellTemplates.requires_host(profile.shell_type)
            and not profile.host.strip()
        ):
            return (
                "Environment Explorer is unavailable because this environment has "
                "no host."
            )
        return ""


class RockyShellExplorer(StatefulWidget):
    def __init__(
        self,
        *,
        provider: ShellProvider | None,
        initial_error: str = "",
        key=None,
    ):
        super().__init__(key=key)
        self.provider = provider
        self.initial_error = initial_error

    def createState(self):
        return _RockyShellExplorerState()


class _RockyShellExplorerState(State[RockyShellExplorer]):
    def initState(self):
        self._path = "/"
        self._directories: list[str] = []
        self._files: list[str] = []
        self._loading = not self.widget.initial_error
        self._error = self.widget.initial_error
        self._active_menu_entry = None
        self._selected: str | None = None
        self._status_entry = None
        self._status_text = ""
        self._status_is_error = False
        if self.widget.provider is not None:
            asyncio.create_task(self._init_working_directory())

    def dispose(self):
        self._dismiss_active_menu()
        self._dismiss_status()
        super().dispose()

    @staticmethod
    def _get_working_directory(provider: ShellProvider) -> str:
        if provider.is_local:
            base = (
                Path(provider.local_workdir) if provider.local_workdir else Path.cwd()
            )
            path = base.resolve().as_posix()
            return path if path.endswith("/") else path + "/"
        result = provider.subprocess_exec(["pwd"])
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "unknown error"
            raise RuntimeError(f"pwd failed (rc={result.returncode}): {stderr}")
        path = result.stdout.strip()
        if not path:
            raise RuntimeError("pwd returned empty output")
        return path if path.endswith("/") else path + "/"

    @staticmethod
    def _list_directory(
        provider: ShellProvider, path: str
    ) -> tuple[list[str], list[str]]:
        if provider.is_local:
            local_path = Path(path)
            directories: list[str] = []
            files: list[str] = []
            for child in local_path.iterdir():
                if child.is_dir():
                    directories.append(child.name + "/")
                else:
                    files.append(child.name)
            directories.sort()
            files.sort()
            return directories, files
        result = provider.subprocess_exec(
            ["sh", "-c", f"ls -1pa {shlex.quote(path)} 2>&1"]
        )
        if result.returncode != 0:
            output = (result.stdout or result.stderr or "").strip()
            raise RuntimeError(f"ls failed (rc={result.returncode}): {output}")
        directories: list[str] = []
        files: list[str] = []
        for line in result.stdout.splitlines():
            name = line.strip()
            if not name or name in ("./", "../"):
                continue
            if name.endswith("/"):
                directories.append(name)
            else:
                files.append(name)
        directories.sort()
        files.sort()
        return directories, files

    @staticmethod
    def _read_file(provider: ShellProvider, path: str) -> bytes:
        return provider._read_file(path)

    @staticmethod
    def _delete_file(provider: ShellProvider, path: str) -> None:
        if provider.is_local:
            Path(path).unlink(missing_ok=True)
            return
        result = provider.subprocess_exec(["rm", "-f", "--", path])
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"rm failed (rc={result.returncode}): {output}")

    @staticmethod
    def _delete_directory(provider: ShellProvider, path: str) -> None:
        if provider.is_local:
            shutil.rmtree(path, ignore_errors=True)
            return
        result = provider.subprocess_exec(["rm", "-rf", "--", path])
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"rm -rf failed (rc={result.returncode}): {output}")

    @staticmethod
    def _write_file(provider: ShellProvider, remote_path: str, data: bytes) -> None:
        provider._write_file(remote_path, data)

    async def _init_working_directory(self):
        provider = self.widget.provider
        if provider is None:
            return
        try:
            loop = asyncio.get_event_loop()
            self._path = await loop.run_in_executor(
                None,
                self._get_working_directory,
                provider,
            )
        except Exception as error:
            print(f"[RockyShellExplorer] pwd failed, falling back to /: {error}")
            self._path = "/"
        await self._load()

    async def _load(self):
        provider = self.widget.provider
        if provider is None:
            self._loading = False
            self._error = (
                self.widget.initial_error or "Environment Explorer is unavailable."
            )
            self.setState(lambda: None)
            return

        self._loading = True
        self._error = ""
        self.setState(lambda: None)
        try:
            loop = asyncio.get_event_loop()
            directories, files = await loop.run_in_executor(
                None,
                self._list_directory,
                provider,
                self._path,
            )
            self._directories = directories
            self._files = files
            self._loading = False
            self.setState(lambda: None)
        except Exception as error:
            print(f"[RockyShellExplorer] load failed for {self._path}: {error}")
            self._error = str(error)
            self._loading = False
            self.setState(lambda: None)

    def _select(self, name: str):
        self._dismiss_active_menu()
        if self._selected != name:
            self._selected = name
            self.setState(lambda: None)

    def _clear_selection(self):
        self._dismiss_active_menu()
        if self._selected is not None:
            self._selected = None
            self.setState(lambda: None)

    def _child_path(self, name: str) -> str:
        return (
            self._path + name if self._path.endswith("/") else self._path + "/" + name
        )

    def _navigate(self, directory_name: str):
        if self.widget.provider is None:
            return
        path = self._child_path(directory_name)
        self._path = path if path.endswith("/") else path + "/"
        asyncio.create_task(self._load())

    def _navigate_to(self, absolute_path: str):
        if self.widget.provider is None:
            return
        self._path = (
            absolute_path if absolute_path.endswith("/") else absolute_path + "/"
        )
        asyncio.create_task(self._load())

    def _navigate_up(self):
        if self._path == "/":
            return
        parent = self._path.rstrip("/").rsplit("/", 1)[0]
        self._navigate_to(parent or "/")

    def _refresh(self):
        if self.widget.provider is not None:
            asyncio.create_task(self._load())

    def _save_as(self, filename: str):
        asyncio.create_task(self._save_files([(self._child_path(filename), filename)]))

    async def _save_files(self, files: list[tuple[str, str]]):
        provider = self.widget.provider
        if provider is None:
            return
        try:
            import tkinter as tk
            from tkinter import filedialog

            if len(files) == 1:
                remote_path, default_name = files[0]
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                destination = filedialog.asksaveasfilename(
                    initialfile=default_name,
                    title="Save As",
                )
                root.destroy()
                if not destination:
                    return
                targets = [(remote_path, destination, default_name)]
            else:
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                destination_directory = filedialog.askdirectory(title="Save to folder")
                root.destroy()
                if not destination_directory:
                    return
                targets = [
                    (remote_path, os.path.join(destination_directory, name), name)
                    for remote_path, name in files
                ]

            loop = asyncio.get_event_loop()
            errors: list[str] = []
            for index, (remote_path, destination, name) in enumerate(targets, 1):
                self._show_status(f"Downloading {index}/{len(targets)}: {name}...")
                try:
                    data = await loop.run_in_executor(
                        None,
                        self._read_file,
                        provider,
                        remote_path,
                    )
                    with open(destination, "wb") as output_file:
                        output_file.write(data)
                except Exception as error:
                    errors.append(f"{name}: {error}")
            if errors:
                self._update_status(
                    f"Download failed: {'; '.join(errors)}", is_error=True
                )
            else:
                self._dismiss_status()
        except Exception as error:
            print(f"[RockyShellExplorer] save failed: {error}")
            self._update_status(f"Save failed: {error}", is_error=True)

    def _delete(self, filename: str):
        asyncio.create_task(
            self._delete_path(self._child_path(filename), is_directory=False)
        )

    def _delete_directory_at(self, directory_name: str):
        asyncio.create_task(
            self._delete_path(self._child_path(directory_name), is_directory=True)
        )

    async def _delete_path(self, remote_path: str, *, is_directory: bool):
        provider = self.widget.provider
        if provider is None:
            return
        try:
            loop = asyncio.get_event_loop()
            if is_directory:
                await loop.run_in_executor(
                    None,
                    self._delete_directory,
                    provider,
                    remote_path,
                )
            else:
                await loop.run_in_executor(
                    None,
                    self._delete_file,
                    provider,
                    remote_path,
                )
            await self._load()
        except Exception as error:
            self._error = f"Delete failed: {error}"
            self.setState(lambda: None)

    def _upload_files(self):
        asyncio.create_task(self._upload_selected_files())

    async def _upload_selected_files(self):
        provider = self.widget.provider
        if provider is None:
            return
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            paths = filedialog.askopenfilenames(title="Select files to upload")
            root.destroy()
            if not paths:
                return

            target_path = self._path
            loop = asyncio.get_event_loop()
            errors: list[str] = []
            for index, path in enumerate(paths, 1):
                filename = os.path.basename(path)
                self._show_status(f"Uploading {index}/{len(paths)}: {filename}...")
                try:
                    with open(path, "rb") as input_file:
                        data = input_file.read()
                    remote_path = (
                        target_path + filename
                        if target_path.endswith("/")
                        else target_path + "/" + filename
                    )
                    await loop.run_in_executor(
                        None,
                        self._write_file,
                        provider,
                        remote_path,
                        data,
                    )
                except Exception as error:
                    errors.append(f"{filename}: {error}")
            if errors:
                self._update_status(
                    f"Upload failed: {'; '.join(errors)}", is_error=True
                )
            else:
                self._dismiss_status()
                if self._path == target_path:
                    await self._load()
        except Exception as error:
            print(f"[RockyShellExplorer] upload failed: {error}")
            self._update_status(f"Upload failed: {error}", is_error=True)

    def _show_status(self, text: str):
        self._dismiss_status()
        self._status_text = text
        self._status_is_error = False
        overlay = Overlay.of(self._build_context)
        self._status_entry = OverlayEntry(builder=self._build_status_overlay)
        overlay.insert(self._status_entry)

    def _update_status(self, text: str, *, is_error: bool = False):
        if self._status_entry is None:
            self._show_status(text)
        self._status_text = text
        self._status_is_error = is_error
        if self._status_entry and self._status_entry.mounted:
            self._status_entry.markNeedsBuild()

    def _dismiss_status(self):
        if self._status_entry and self._status_entry.mounted:
            self._status_entry.remove()
            self._status_entry.dispose()
        self._status_entry = None

    def _build_status_overlay(self, _):
        icon = (
            Icon(Icons.error, size=16, color=Color(0xFFF44336))
            if self._status_is_error
            else SizedBox(
                width=16,
                height=16,
                child=CircularProgressIndicator(
                    strokeWidth=2,
                    color=Color(0xFF2196F3),
                ),
            )
        )
        card = Card(
            color=Color(0xFF2D2D2D),
            elevation=6,
            margin=EdgeInsets.all(0),
            shape=RoundedRectangleBorder(borderRadius=BorderRadius.circular(8)),
            child=Container(
                padding=EdgeInsets.symmetric(horizontal=16, vertical=10),
                child=Row(
                    mainAxisSize=MainAxisSize.min,
                    children=[
                        icon,
                        SizedBox(width=10),
                        Text(
                            self._status_text,
                            style=TextStyle(
                                fontSize=12,
                                color=(
                                    Color(0xFFF44336)
                                    if self._status_is_error
                                    else Color(0xFFD4D4D4)
                                ),
                            ),
                        ),
                    ],
                ),
            ),
        )
        return Positioned(
            bottom=40,
            left=0,
            right=0,
            child=Row(
                mainAxisAlignment=MainAxisAlignment.center,
                children=[
                    Stack(
                        clipBehavior=Clip.none,
                        children=[
                            card,
                            Positioned(
                                top=-6,
                                right=-6,
                                child=GestureDetector(
                                    onTap=self._dismiss_status,
                                    child=Container(
                                        width=14,
                                        height=14,
                                        decoration=BoxDecoration(
                                            color=Color(0x99757575),
                                            shape=BoxShape.circle,
                                        ),
                                        child=Icon(
                                            Icons.close,
                                            size=10,
                                            color=Color(0xCCFFFFFF),
                                        ),
                                    ),
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _on_empty_right_click(self, details, context):
        if self.widget.provider is None:
            return
        self._clear_selection()
        self._show_context_menu(
            details, [("Upload Files...", self._upload_files)], context
        )

    def build(self, context):
        self._build_context = context
        is_dark = Theme.of(context).brightness == Brightness.dark
        has_provider = self.widget.provider is not None
        background = Color(0xFF1E1E1E) if is_dark else Color(0xFFFAFAFA)
        toolbar_background = Color(0xFF2D2D2D) if is_dark else Color(0xFFE8E8E8)
        text_color = Color(0xFFD4D4D4) if is_dark else Color(0xFF333333)
        dim_color = Color(0xFF808080) if is_dark else Color(0xFF999999)

        if self._loading:
            body = Container(
                alignment=Alignment.center,
                child=Text("Loading...", style=TextStyle(color=dim_color)),
            )
        elif self._error:
            body = Container(
                alignment=Alignment.center,
                padding=EdgeInsets.all(24),
                child=Text(self._error, style=TextStyle(color=Color(0xFFF44336))),
            )
        else:
            body = self._build_tile_grid(context, text_color, dim_color, is_dark)

        return GestureDetector(
            onTap=self._clear_selection,
            onSecondaryTapUp=(
                (lambda details: self._on_empty_right_click(details, context))
                if has_provider
                else None
            ),
            child=Container(
                color=background,
                child=Column(
                    children=[
                        self._build_navigation_bar(toolbar_background, text_color),
                        Expanded(child=body),
                    ],
                ),
            ),
        )

    def _build_navigation_bar(self, background, text_color):
        has_provider = self.widget.provider is not None
        parts = [part for part in self._path.split("/") if part]
        crumbs = [
            InkWell(
                onTap=(lambda: self._navigate_to("/")) if has_provider else None,
                child=Text("/", style=TextStyle(fontSize=13, color=text_color)),
            )
        ]
        for index, part in enumerate(parts):
            target = "/" + "/".join(parts[: index + 1]) + "/"
            crumbs.append(
                InkWell(
                    onTap=(
                        (lambda target_path=target: self._navigate_to(target_path))
                        if has_provider
                        else None
                    ),
                    child=Text(
                        part + "/",
                        style=TextStyle(fontSize=13, color=text_color),
                    ),
                )
            )

        button_style = {
            "iconSize": 16,
            "padding": EdgeInsets.all(6),
            "constraints": BoxConstraints(minWidth=28, minHeight=28),
        }
        return Container(
            height=44,
            padding=EdgeInsets.fromLTRB(8, 4, 8, 4),
            color=background,
            child=Row(
                children=[
                    IconButton(
                        icon=Icon(Icons.arrow_upward, size=16, color=text_color),
                        onPressed=self._navigate_up if has_provider else None,
                        **button_style,
                    ),
                    IconButton(
                        icon=Icon(Icons.refresh, size=16, color=text_color),
                        onPressed=self._refresh if has_provider else None,
                        **button_style,
                    ),
                    SizedBox(width=4),
                    Expanded(
                        child=SingleChildScrollView(
                            scrollDirection=Axis.horizontal,
                            child=Row(children=crumbs),
                        ),
                    ),
                ],
            ),
        )

    def _build_tile_grid(self, context, text_color, dim_color, is_dark):
        tiles = []
        for directory_name in self._directories:
            display = directory_name.rstrip("/")
            tiles.append(
                self._tile(
                    icon=Icons.folder,
                    icon_color=Color(0xFFFFCA28),
                    label=display,
                    text_color=text_color,
                    on_double_tap=lambda name=display: self._navigate(name),
                    context_items=[
                        ("Delete", lambda name=display: self._delete_directory_at(name))
                    ],
                    context=context,
                    is_dark=is_dark,
                )
            )

        for filename in self._files:
            tiles.append(
                self._tile(
                    icon=self._file_icon(filename),
                    icon_color=dim_color,
                    label=filename,
                    text_color=text_color,
                    on_double_tap=None,
                    context_items=[
                        ("Save As...", lambda name=filename: self._save_as(name)),
                        ("Delete", lambda name=filename: self._delete(name)),
                    ],
                    context=context,
                    is_dark=is_dark,
                )
            )

        if not tiles:
            return Container(
                alignment=Alignment.center,
                child=Text("Empty folder", style=TextStyle(color=dim_color)),
            )

        return SingleChildScrollView(
            child=Container(
                alignment=Alignment.topLeft,
                padding=EdgeInsets.all(12),
                child=Wrap(
                    spacing=8,
                    runSpacing=8,
                    alignment=WrapAlignment.start,
                    children=tiles,
                ),
            ),
        )

    def _tile(
        self,
        *,
        icon,
        icon_color,
        label: str,
        text_color,
        on_double_tap,
        context_items: list[tuple[str, object]],
        context,
        is_dark: bool,
    ):
        is_selected = self._selected == label
        selected_background = Color(0xFF094771) if is_dark else Color(0xFFD6EBFF)
        selected_border = Color(0xFF2188D9) if is_dark else Color(0xFF007ACC)
        tile_content = Container(
            width=90.0,
            padding=EdgeInsets.symmetric(vertical=8, horizontal=4),
            decoration=BoxDecoration(
                color=selected_background if is_selected else None,
                borderRadius=BorderRadius.circular(6),
                border=Border.all(
                    color=selected_border if is_selected else Color(0x00000000),
                    width=1.5,
                ),
            ),
            child=Column(
                mainAxisAlignment=MainAxisAlignment.center,
                children=[
                    Icon(icon, size=36, color=icon_color),
                    SizedBox(height=4),
                    Text(
                        label,
                        style=TextStyle(fontSize=11, color=text_color),
                        maxLines=2,
                        overflow=TextOverflow.ellipsis,
                    ),
                ],
            ),
        )
        return GestureDetector(
            onTapDown=lambda _: self._select(label),
            onDoubleTap=on_double_tap,
            onSecondaryTapUp=lambda details, items=context_items, tile_label=label: (
                self._select(tile_label),
                self._show_context_menu(details, items, context),
            ),
            child=tile_content,
        )

    def _show_context_menu(self, details, items, context):
        self._dismiss_active_menu()
        is_dark = Theme.of(context).brightness == Brightness.dark
        menu_background = Color(0xFF2D2D2D) if is_dark else Color(0xFFFFFFFF)
        menu_text = Color(0xFFD4D4D4) if is_dark else Color(0xFF333333)
        menu_hover = Color(0xFF094771) if is_dark else Color(0xFFE8E8E8)
        overlay = Overlay.of(context)
        entry = None

        def dismiss():
            nonlocal entry
            if entry and entry.mounted:
                entry.remove()
                entry.dispose()
            if self._active_menu_entry is entry:
                self._active_menu_entry = None
            entry = None

        def on_item(action):
            dismiss()
            action()

        menu_width = 160.0
        menu_item_height = 32.0
        menu_height = len(items) * menu_item_height + 8
        screen = MediaQuery.of(context).size
        dx = details.globalPosition.dx
        dy = details.globalPosition.dy
        if dx + menu_width > screen.width:
            dx = screen.width - menu_width - 4
        if dy + menu_height > screen.height:
            dy = screen.height - menu_height - 4

        def build_overlay(_):
            return Positioned(
                left=dx,
                top=dy,
                child=Card(
                    color=menu_background,
                    elevation=8,
                    margin=EdgeInsets.all(0),
                    shape=RoundedRectangleBorder(borderRadius=BorderRadius.circular(6)),
                    child=Container(
                        width=menu_width,
                        padding=EdgeInsets.symmetric(vertical=4),
                        child=Column(
                            mainAxisSize=MainAxisSize.min,
                            children=[
                                InkWell(
                                    onTap=lambda item_action=action: on_item(
                                        item_action
                                    ),
                                    hoverColor=menu_hover,
                                    child=Container(
                                        padding=EdgeInsets.symmetric(
                                            horizontal=12, vertical=6
                                        ),
                                        width=menu_width,
                                        child=Text(
                                            label,
                                            style=TextStyle(
                                                fontSize=13, color=menu_text
                                            ),
                                        ),
                                    ),
                                )
                                for label, action in items
                            ],
                        ),
                    ),
                ),
            )

        entry = OverlayEntry(builder=build_overlay)
        self._active_menu_entry = entry
        overlay.insert(entry)

    def _dismiss_active_menu(self):
        if self._active_menu_entry and self._active_menu_entry.mounted:
            self._active_menu_entry.remove()
            self._active_menu_entry.dispose()
        self._active_menu_entry = None

    @staticmethod
    def _file_icon(name: str):
        lower = name.lower()
        if lower.endswith((".py", ".pyw")):
            return Icons.code
        if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp")):
            return Icons.image
        if lower.endswith((".txt", ".md", ".rst", ".log")):
            return Icons.description
        if lower.endswith((".json", ".yaml", ".yml", ".toml", ".xml", ".csv")):
            return Icons.data_object
        if lower.endswith((".sh", ".bash", ".zsh", ".bat", ".cmd")):
            return Icons.terminal
        if lower.endswith((".zip", ".tar", ".gz", ".bz2", ".xz", ".7z")):
            return Icons.archive
        if lower.endswith((".html", ".htm", ".css", ".js", ".ts")):
            return Icons.web
        return Icons.insert_drive_file
