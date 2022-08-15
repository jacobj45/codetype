from pathlib import Path

import click
import validators

from codetype.base import main_basic
from codetype.utils import read_from_url


@click.group()
def cli():  # noqa: D400
    """Tool for improving typing speed and accuracy while "programming"!"""


@cli.command()
@click.argument(
    "path",
    type=str,
    help="File path or URL of source file",
)
@click.option(
    "-l",
    "--lexer",
    type=str,
    help="Lexer to use (see https://pygments.org/docs/lexers/)",
)
@click.option(
    "-s",
    "--start-line",
    type=int,
    help="The start line of the excerpt to use. needs to be used together "
    "with end-line.",
)
@click.option(
    "-e",
    "--end-line",
    type=int,
    help="The end line of the excerpt to use. Needs to be used together with "
    "start-line.",
)
@click.option(
    "-f",
    "--force-perfect",
    is_flag=True,
    help="All characters need to be typed correctly",
)
@click.option(
    "-i",
    "--instant-death",
    is_flag=True,
    help="End game after the first mistake",
)
@click.option(
    "-t",
    "--target-wpm",
    type=int,
    help="The desired speed to be shown as a guide",
)
@click.option(
    "-c",
    "--keep-comments",
    is_flag=True,
    help="Include comments from code file",
)
def file(
    path,
    lexer,
    start_line,
    end_line,
    force_perfect,
    instant_death,
    target_wpm,
    keep_comments,
):  # noqa: D400
    """Type text from a source file"""  # noqa: D400

    if validators.url.url(path):
        filename, content = read_from_url(path)
    elif (filepath := Path(path)).exists():
        filename = filepath.name
        content = filepath.read_text()
    else:
        raise FileNotFoundError(f"Cannot find '{path}'")

    # if not 0 <= start_line < end_line < len(all_lines):
    #     raise ValueError(
    #         f"Selected lines fall outside of the range (0, {n_all_lines})"
    #         " or are in a wrong order."
    #     )
    # selected_lines = all_lines[start_line:end_line]

    main_basic(
        content,
        filename,
        # force_perfect=force_perfect,
        # instant_death=instant_death,
        # target_wpm=target_wpm,
    )
