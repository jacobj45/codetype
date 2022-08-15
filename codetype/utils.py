import shutil
from contextlib import contextmanager
from datetime import datetime
from hashlib import blake2b
from pathlib import Path
from urllib.parse import urlparse

import requests
from colour import Color as C
from pygments.lexers import get_lexer_for_filename
from pygments.token import Token

cache_folder = Path.home() / ".codetype/cache"
cache_folder.mkdir(exist_ok=True, parents=True)


def read_from_url(url):
    parsed_url = urlparse(url)
    name = blake2b(url.encode(), digest_size=16).hexdigest()
    cache_file = cache_folder / name

    if cache_file.exists():
        content = cache_file.read_text()
    else:
        resp = requests.get(url)
        if resp.status_code != 200:
            # raise requests.exceptions.RequestException(
            #     f"Failed with status code: {resp.status_code}"
            # )
            resp.raise_for_status()
        content = resp.text
        cache_file.write_text(content)
    return content, parsed_url.path


def clean_text(
    content,
    filename,
    lexer=None,
    # keep_comments=False,
):
    if lexer is None:
        lexer = get_lexer_for_filename(filename)

    line, lines = [], []
    for token_type, token_text in lexer.get_tokens(content):
        if token_type in Token.Comment or token_type in Token.Literal.String.Doc:
            token_text = "\n"

        if token_text == "\n":
            lines.append("".join(line))
            line = []
        else:
            line.append(token_text)
    if line:
        lines.append("".join(line))

    lines2 = []
    for line in "\n".join(lines).strip().splitlines():
        line = line.rstrip()
        if line == "":
            continue
        lines2.append(line)
    return lines2, lexer


@contextmanager
def print_section(name, fill_char="=", drop_end=False, add_ts=True):
    """Print nice section blocks.

    Parameters
    ----------
    name : str
        Name of the section.

    fill_char : str
        Character to be used for filling the line.

    drop_end : bool
        If True, the ending line is not printed.

    add_ts : bool
        We add a time step to the heading.
    """
    if len(fill_char) != 1:
        raise ValueError("The fill_char needs to have exactly one character")

    if add_ts:
        ts = datetime.now().strftime("%H:%M:%S")
        title = f"{name}| {ts} "
    else:
        title = name

    width, _ = shutil.get_terminal_size()
    print(title.center(width, fill_char))

    yield

    if not drop_end:
        print(width * fill_char)


def change_color_luminance(color, delta_luminance, lighten=True, rgb=False):
    col = C(color)
    if not lighten:
        delta_luminance *= -1
    col.luminance = max(0, min(1, col.luminance + delta_luminance))
    return col.rgb if rgb else col.hex
