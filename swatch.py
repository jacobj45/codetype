from colour import Color as C
from pygments import styles
from rich.color import Color, parse_rgb_hex
from rich.style import Style
from rich.text import Text
from textual.app import App
from textual.events import Keys
from textual.widgets import ScrollView


class ColorChanger(App):
    async def on_load(self):
        sty = styles.get_style_by_name("monokai")
        background = Color.from_rgb(*parse_rgb_hex(sty.background_color[1:]))
        self.standard_text = Text()
        for k, v in sty.styles.items():
            if len(v) != 7:
                continue

            self.standard_text.append(
                f"{k}: {v}\n",
                Style(color=Color.from_rgb(*parse_rgb_hex(v[1:])), bgcolor=background),
            )

        self.dark_text = Text()
        for k, v in sty.styles.items():
            if len(v) != 7:
                continue
            col = C(v)
            col.luminance = max(0, col.luminance - 0.05)

            self.dark_text.append(
                f"{k}: {v}\n",
                Style(
                    color=Color.from_rgb(*[x * 255 for x in col.rgb]),
                    bgcolor=background,
                ),
            )

        self.light_text = Text()
        for k, v in sty.styles.items():
            if len(v) != 7:
                continue
            col = C(v)
            col.luminance = min(1, col.luminance + 0.1)

            self.light_text.append(
                f"{k}: {v}\n",
                Style(
                    color=Color.from_rgb(*[x * 255 for x in col.rgb]),
                    bgcolor=background,
                ),
            )

    async def on_mount(self) -> None:
        self.standard = ScrollView()
        self.dark = ScrollView()
        self.light = ScrollView()

        await self.standard.update(self.standard_text)
        await self.dark.update(self.dark_text)
        await self.light.update(self.light_text)

        await self.view.dock(self.standard, self.dark, self.light, edge="left")


ColorChanger.run()
