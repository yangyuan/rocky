import asyncio
import importlib.util
import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)


class RockySystem:
    _shutting_down = False

    @staticmethod
    def request_shutdown() -> None:
        RockySystem._shutting_down = True

    @staticmethod
    def is_shutting_down() -> bool:
        return RockySystem._shutting_down

    @staticmethod
    def _open_folder_impl(path: str) -> None:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    @staticmethod
    def open_folder(path: Union[str, Path]) -> None:
        path_str = str(path)
        asyncio.get_running_loop().call_soon(RockySystem._open_folder_impl, path_str)

    @staticmethod
    def open_url(url: str) -> None:
        asyncio.get_running_loop().call_soon(webbrowser.open, url)

    @staticmethod
    def is_tk_installed() -> bool:
        try:
            return importlib.util.find_spec("tkinter") is not None
        except Exception:
            return False

    @staticmethod
    def is_litert_lm_installed() -> bool:
        try:
            return importlib.util.find_spec("litert_lm") is not None
        except Exception:
            return False

    @staticmethod
    def os_display_name() -> str:
        if sys.platform == "win32":
            return "Windows"
        if sys.platform == "darwin":
            return "macOS"
        return "Linux"

    @staticmethod
    def monospace_font_family() -> str:
        if sys.platform == "win32":
            return "Consolas"
        if sys.platform == "darwin":
            return "Menlo"
        return "DejaVu Sans Mono"

    @staticmethod
    def monospace_font_family_fallback() -> list[str]:
        return ["Consolas", "Menlo", "DejaVu Sans Mono", "Courier New", "monospace"]

    @staticmethod
    def tk_select_file_with_types(
        *,
        title: str,
        filetypes: Sequence[Tuple[str, str]],
    ) -> Optional[str]:
        if not RockySystem.is_tk_installed():
            logger.warning(
                "tkinter is not installed; ignoring file picker request (%s).",
                title,
            )
            return None
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        try:
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title=title,
                filetypes=list(filetypes),
            )
        finally:
            root.destroy()
        return path or None

    @staticmethod
    def tk_select_files_with_types(
        *,
        title: str,
        filetypes: Sequence[Tuple[str, str]],
    ) -> list[str]:
        if not RockySystem.is_tk_installed():
            logger.warning(
                "tkinter is not installed; ignoring file picker request (%s).",
                title,
            )
            return []
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        try:
            root.withdraw()
            root.attributes("-topmost", True)
            paths = filedialog.askopenfilenames(
                title=title,
                filetypes=list(filetypes),
            )
        finally:
            root.destroy()
        return list(paths or [])
