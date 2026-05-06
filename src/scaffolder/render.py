"""Central Jinja2 environment factory.

All templates and addons use make_env() so the custom delimiters
stay defined in exactly one place.
"""

from pathlib import Path

import jinja2


def make_env(loader_path: Path | None = None) -> jinja2.Environment:
    """Return a Jinja2 Environment with jumpstart's custom delimiters.

    Pass loader_path to load templates from a directory.
    Omit it (or pass None) when rendering strings directly.
    """
    loader: jinja2.BaseLoader
    if loader_path is not None:
        loader = jinja2.FileSystemLoader(str(loader_path))
    else:
        loader = jinja2.BaseLoader()

    return jinja2.Environment(
        loader=loader,
        keep_trailing_newline=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="[%",
        block_end_string="%]",
        line_comment_prefix=None,
    )
