import bisect
import itertools
import re
from copy import deepcopy
from datetime import datetime
from functools import reduce

import pygments
import rich
from colour import Color as C
from pygments.token import Token
from rich.console import Console
from rich.segment import Segment, Segments
from rich.style import Style as S
from rich.syntax import PygmentsSyntaxTheme, Syntax
from rich.text import Text
from textual.app import App
from textual.widgets import Static

from codetype.utils import change_color_luminance, clean_text, print_section

STATUS_BACKSPACE = 1
STATUS_CORRECT = 2
STATUS_WRONG = 3


class Action:
    """Representation of one keypress.

    Parameters
    ----------
    pressed_key : str
        What key was pressed. We define a convention that pressing
        a backspace will be represented as `pressed_key=None`.

    status : int
        What was the status AFTER pushing the key. It should be one
        of the following integers:
            * STATUS_BACKSPACE
            * STATUS_CORRECT
            * STATUS_WRONG

    ts : datetime
        The timestamp corresponding to this action.
    """

    def __init__(self, pressed_key, status, ts):
        # if pressed_key is not None and len(pressed_key) != 1:
        #     raise ValueError("The pressed key needs to be a single character")
        self.pressed_key = pressed_key
        self.status = status
        self.ts = ts

    def __eq__(self, other):
        """Check whether equal."""
        if not isinstance(other, self.__class__):
            return False

        return (
            self.pressed_key == other.pressed_key
            and self.status == other.status
            and self.ts == other.ts
        )


class TypedText:
    """Abstraction that represents the text and the styles to be rendered."""

    def __init__(self, lines, lexer):
        self.start_ts = None
        self.end_ts = None

        # self.curr_idx = 0
        # self.actions = [[] for _ in range(len(self.text))]
        # self.back_idxs = {}
        self.lexer = lexer
        self.lines = lines
        self.lines_start_idxs = []
        cum_len = 0
        for line in self.lines:
            self.lines_start_idxs.append(cum_len)
            cum_len += len(line) + 1

        self.text = "".join(x + "\n" for x in self.lines)
        self.gutter_col_width = len(str(len(self.lines))) + 1

        theme = pygments.styles.get_style_by_name("monokai")
        lighten_color = lambda m: change_color_luminance(m.group(0), 0.1)
        new_style = {
            tok_type: re.sub(r"#.{6,6}", lighten_color, sty)
            for tok_type, sty in theme.styles.items()
        }

        class untyped_style(theme):
            styles = new_style

        self.untyped_style = untyped_style
        self.gutter_style = S.parse(
            f"{theme.styles[Token.Comment]} on {theme.background_color}"
        )
        self.cursor_style = S(
            bgcolor=change_color_luminance(theme.background_color, 0.15), bold=True
        )
        self.wrong_style = S.parse("bold red on white")

    def update_dimensions(self, width, height):
        self.width = width
        self.height = height

        self.curr_idx = 0
        self.actions = [[] for _ in range(len(self.text))]
        self.back_idxs = {}
        self.create_rich_lines()

    def set_console(self, console):
        self.console = console

    def create_rich_lines(self):
        syntax = Syntax(
            self.text,
            self.lexer,
            theme=self.untyped_style,
            # word_wrap=True,
            # line_numbers=True,
            # indent_guides=True,
        )
        rich_text = syntax.highlight(self.text)
        # assert len(rich_text) == len(self.text)

        self.rich_lines_start_idxs = deepcopy(self.lines_start_idxs)
        self.orig_rich_lines = []
        for line_no, line in enumerate(rich_text.split("\n")):
            line_text = line.plain
            # assert self.lines[line_no] == line_text

            cum_len = 0
            for idx, wrapped_line in enumerate(
                line.wrap(
                    self.console,
                    self.width - (self.gutter_col_width + 1),
                )
            ):
                line_text = line_text.removeprefix(wrapped_line.plain.rstrip())
                if line_text and line_text[0].isspace():
                    line_text = line_text.lstrip()
                if not wrapped_line.plain[-1].isspace():
                    wrapped_line.append(" ")

                rich_line = Text()
                if idx == 0:
                    line_column = str(line_no + 1).rjust(self.gutter_col_width) + " "
                    rich_line.append(Text(line_column, style=self.gutter_style))
                else:
                    rich_line.append(
                        Text(
                            " " * (self.gutter_col_width + 1),
                            style=self.gutter_style,
                        )
                    )
                    bisect.insort(
                        self.rich_lines_start_idxs,
                        self.lines_start_idxs[line_no] + cum_len,
                    )

                cum_len += len(wrapped_line.plain.rstrip()) + 1
                rich_line.append(wrapped_line)
                rich_line.append("\n")
                self.orig_rich_lines.append(rich_line)

        # assert len(self.orig_rich_lines) == len(self.rich_lines_start_idxs)
        self.rich_lines = deepcopy(self.orig_rich_lines)

    def get_rich_line_no(self, idx):
        line_idx = bisect.bisect(self.rich_lines_start_idxs, idx) - 1
        return (line_idx, idx - self.rich_lines_start_idxs[line_idx])

    @property
    def rich_text(self):
        self.style_cursor_location()

        if len(self.orig_rich_lines) > self.height:
            n_lines_above = 5
            line_idx, _ = self.get_rich_line_no(self.curr_idx)
            sl = max(0, line_idx - n_lines_above)
            el = line_idx + self.height - n_lines_above
        else:
            sl = 0
            el = len(self.orig_rich_lines)
        return reduce(lambda acc, x: acc.append(x), self.rich_lines[sl:el], Text())

    def style_cursor_location(self):
        line_idx, idx = self.get_rich_line_no(self.curr_idx)
        self.rich_lines[line_idx].stylize(
            self.cursor_style,
            self.gutter_col_width + idx + 1,
            self.gutter_col_width + idx + 2,
        )

    def style_for_backspace_at(self, idx):
        line_idx, idx2 = self.get_rich_line_no(idx)
        rich_line = self.orig_rich_lines[line_idx]

        sty = rich_line.get_style_at_offset(
            self.console, self.gutter_col_width + idx2 + 1
        )
        self.rich_lines[line_idx].stylize(
            sty,
            self.gutter_col_width + idx2 + 1,
            self.gutter_col_width + idx2 + 2,
        )
        if idx == 0:
            return

        p_idx = self.back_idxs[idx]
        p_line_idx, p_idx2 = self.get_rich_line_no(p_idx)
        p_rich_line = self.orig_rich_lines[p_line_idx]
        p_sty = p_rich_line.get_style_at_offset(
            self.console, self.gutter_col_width + p_idx + 1
        )
        self.rich_lines[p_line_idx].stylize(
            p_sty,
            self.gutter_col_width + p_idx2 + 1,
            self.gutter_col_width + p_idx2 + 2,
        )

    def style_wrong_char_at(self, idx):
        line_idx, idx2 = self.get_rich_line_no(idx)
        i = idx2 + self.gutter_col_width + 1
        self.rich_lines[line_idx].stylize(self.wrong_style, i, i + 1)

    def style_correct_char_at(self, idx):
        line_idx, idx2 = self.get_rich_line_no(idx)
        i = idx2 + self.gutter_col_width + 1

        rich_line = self.orig_rich_lines[line_idx]
        sty = rich_line.get_style_at_offset(self.console, i)

        if self.text[idx].isspace():
            self.rich_lines[line_idx].stylize(sty, i, i + 1)
        else:
            new_col = change_color_luminance(sty.color.name, 0.15, lighten=False)
            self.rich_lines[line_idx].stylize(sty + S.parse(new_col), i, i + 1)

    def _n_characters_with_status(self, status):
        """Count the number of characters with a given status.

        Parameters
        ----------
        status : str
            The status we look for in the character.

        Returns
        -------
        The number of characters with status `status`.
        """
        return len([x for x in self.actions if x and x[-1].status == status])

    @property
    def elapsed_seconds(self):
        """Get the number of seconds elapsed from the first action."""
        if self.start_ts is None:
            return 0

        end_ts = self.end_ts or datetime.now()
        return (end_ts - self.start_ts).total_seconds()

    @property
    def n_actions(self):
        """Get the number of actions that have been taken."""
        return sum(len(x) for x in self.actions)

    @property
    def n_characters(self):
        """Get the number of characters in the text."""
        return len(self.text)

    @property
    def n_backspace_actions(self):
        """Get the number of backspace actions."""
        return sum(
            sum(1 for a in x if a.status == STATUS_BACKSPACE) for x in self.actions
        )

    @property
    def n_backspace_characters(self):
        """Get the number of characters that have been backspaced."""
        return self._n_characters_with_status(STATUS_BACKSPACE)

    @property
    def n_correct_characters(self):
        """Get the number of characters that have been typed correctly."""
        return self._n_characters_with_status(STATUS_CORRECT)

    @property
    def n_untouched_characters(self):
        """Get the number of characters that have not been touched yet."""
        return len([x for x in self.actions if not x])  ################

    @property
    def n_wrong_characters(self):
        """Get the number of characters that have been typed wrongly."""
        return self._n_characters_with_status(STATUS_WRONG)

    def compute_accuracy(self):
        """Compute the accuracy of the typing."""
        try:
            acc = self.n_correct_characters / (
                self.n_actions - self.n_backspace_actions
            )
        except ZeroDivisionError:
            acc = 0

        return acc

    def compute_cpm(self):
        """Compute characters per minute."""
        try:
            cpm = 60 * self.n_correct_characters / self.elapsed_seconds

        except ZeroDivisionError:
            # We actually set self.end_ts = self.start_ts in instant death
            cpm = 0

        return cpm

    def compute_wpm(self, word_size=5):
        """Compute words per minute."""
        return self.compute_cpm() / word_size

    def check_finished(self, force_perfect=False):
        """Determine whether the typing has been finished successfully.

        Parameters
        ----------
        force_perfect : bool
            If True, one can only finished if all the characters were typed
            correctly. Otherwise, all characters need to be either correct
            or wrong.

        """
        # if force_perfect:
        #     return self.n_correct_characters == self.n_characters
        # else:
        #     return (
        #         self.n_correct_characters + self.n_wrong_characters == self.n_characters
        #     )
        return self.curr_idx >= self.n_characters

    def type_character(self, ch):
        """Type one single character.

        Parameters
        ----------
        ch : str or None
            The character that was typed. Note that if None then we assume
            that the user used backspace.
        """
        idx = self.curr_idx
        if not (0 <= idx < len(self.text)):
            raise IndexError(f"The index {idx} is outside of the text.")

        ts = datetime.now()

        # check if it is the first action
        if self.start_ts is None:
            self.start_ts = ts

        if ch == "backspace":
            self.actions[idx].append(Action(ch, STATUS_BACKSPACE, ts))
            self.style_for_backspace_at(idx)

            # line_idx = self.get_rich_line_no(idx)
            # si = self.gutter_col_width + 1
            # ei = (
            #     idx - self.rich_lines_start_idxs[line_idx] + self.gutter_col_width + 1
            # )
            # if self.orig_rich_lines[line_idx].plain[si:ei].isspace():
            #     self.curr_idx = self.rich_lines_start_idxs[line_idx]
            # else:
            #     self.curr_idx = max(0, self.curr_idx - 1)
            self.curr_idx = 0 if idx == 0 else self.back_idxs[idx]
            return

        elif ch == "tab":
            if self.text[idx] != " " or (idx != 0 and self.text[idx - 1] != "\n"):
                self.actions[idx].append(Action(ch, STATUS_WRONG, ts))
                self.style_wrong_char_at(idx)

            else:
                self.actions[idx].append(Action(ch, STATUS_CORRECT, ts))
                self.style_correct_char_at(idx)

            new_index = idx + sum(
                1 for _ in itertools.takewhile(str.isspace, self.text[idx:])
            )
            self.curr_idx = min(self.n_characters - 1, new_index)
            self.back_idxs[new_index] = idx

        else:
            line_idx, i = self.get_rich_line_no(idx)
            rich_line = self.orig_rich_lines[line_idx]
            i = i + self.gutter_col_width + 1
            if (
                ch == " "
                and rich_line.plain[i:].isspace()
                # and "\n" not in rich_line.plain[i:]
            ):
                self.actions[idx].append(Action(ch, STATUS_CORRECT, ts))
                self.style_correct_char_at(self.curr_idx)
                try:
                    self.curr_idx = self.rich_lines_start_idxs[line_idx + 1]
                except IndexError:
                    raise ZeroDivisionError()
                self.back_idxs[self.curr_idx] = idx
                # return

            else:
                if ch == self.text[idx]:
                    self.actions[idx].append(Action(ch, STATUS_CORRECT, ts))
                    self.style_correct_char_at(idx)
                else:
                    self.actions[idx].append(Action(ch, STATUS_WRONG, ts))
                    self.style_wrong_char_at(idx)
                self.curr_idx = min(self.n_characters, idx + 1)
                self.back_idxs[self.curr_idx] = idx

        if self.check_finished(force_perfect=False):
            self.end_ts = ts
            raise ZeroDivisionError()

    def process_character(self, key):
        """Process an entered character."""
        # Substitution list from:
        # https://github.com/cronvel/terminal-kit/issues/101#issuecomment-546934809
        match key:
            case "ctrl+i":
                key = "tab"
            case "ctrl+h":
                key = "backspace"
            case ("ctrl+j" | "ctrl+m" | "enter"):
                key = "\n"

        if key not in {"tab", "backspace"} and len(key) > 1:
            return
        self.type_character(key)

    def unroll_actions(self):
        """Export actions in an order they appeared.

        Returns
        -------
        res : list
            List of tuples of `(ix_char, Action(..))`
        """
        return sorted(
            [(i, a) for i, x in enumerate(self.actions) for a in x],
            key=lambda x: x[1].ts,
        )


class TypingApp(App):
    def __init__(self, tt, **kwargs):
        super().__init__(**kwargs)
        self.tt = tt

    async def on_mount(self) -> None:
        self.body = Static(Text())
        await self.view.dock(self.body, edge="top")

        self.tt.set_console(self.body.console)
        # self.tt.update_dimensions(*self.body.size)
        self.tt.update_dimensions(
            self.body.console.options.max_width, self.body.console.options.max_height
        )
        await self.body.update(self.tt.rich_text)

    async def on_key(self, event):
        k = event.key
        try:
            self.tt.process_character(k)
        except ZeroDivisionError:
            # self.shutdown()
            self.panic(Text())
        await self.body.update(self.tt.rich_text)

    async def on_resize(self, event):
        self.tt.update_dimensions(*event.size)
        await self.body.update(self.tt.rich_text)


def main_basic(content, filename):
    lines, lexer = clean_text(content, filename)
    tt = TypedText(lines, lexer)
    TypingApp.run(title="codetype", tt=tt)

    # while not tt.check_finished(force_perfect=force_perfect):
    #     writer.render()
    #     writer.process_character()

    #     if instant_death and tt.n_wrong_characters > 0:
    #         tt.end_ts = tt.start_ts
    #         break

    with print_section(" Statistics ", fill_char="=", add_ts=False):
        print(f"Accuracy: {tt.compute_accuracy():.1%}\n" f"WPM: {tt.compute_wpm():.1f}")
