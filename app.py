import asyncio
import os

from flut import run_app_async
from flut.flutter.material import MaterialApp, ThemeData
from flut.flutter.widgets import Builder, State, StatefulWidget

from rocky.chats import RockyChats
from rocky.settings import RockySettings
from rocky.system import RockySystem
from rocky.widgets.app.home import RockyHome
from rocky.widgets.app.theme import RockyTheme


class RockyApp(StatefulWidget):
    def createState(self):
        return RockyAppState()


class RockyAppState(State[RockyApp]):
    def initState(self):
        self.settings = RockySettings.load()
        self.chats = RockyChats(self.settings)
        self.settings.addListener(self._on_changed)

    def dispose(self):
        RockySystem.request_shutdown()
        self.settings.removeListener(self._on_changed)

    def _on_changed(self):
        self.setState(lambda: None)

    def exit_app(self):
        RockySystem.request_shutdown()
        asyncio.get_running_loop().call_soon(lambda: os._exit(0))

    def build(self, context):
        return MaterialApp(
            title="Rocky",
            theme=ThemeData(
                colorScheme=RockyTheme.build_color_scheme(self.settings.theme),
                useMaterial3=True,
            ),
            home=Builder(
                builder=lambda _ctx: RockyHome(
                    settings=self.settings,
                    chats=self.chats,
                    on_exit=self.exit_app,
                )
            ),
        )


async def main():
    await run_app_async(
        RockyApp(),
        width=960,
        height=640,
        title="Rocky",
    )


if __name__ == "__main__":
    print("Starting Rocky...")
    asyncio.run(main())
