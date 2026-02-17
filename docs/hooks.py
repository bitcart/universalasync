from datetime import date

from mkdocs.config.defaults import MkDocsConfig


def on_config(config: MkDocsConfig) -> None:
    config.copyright = f"Copyright &copy; 2021-{date.today().year} MrNaif2018"
