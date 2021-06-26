import logging

from east_asian_spacing.shaper import ShaperBase


def init_logging(verbose, main=None):
    if not verbose or verbose <= 0:
        return

    if main:
        if verbose == 1:
            console = logging.StreamHandler()
            main.addHandler(console)
            main.setLevel(logging.INFO)
            return
        verbose -= 1

    if verbose <= 1:
        logging.basicConfig(level=logging.INFO)
        return

    logging.basicConfig(level=logging.DEBUG)
    if verbose <= 2:
        return

    ShaperBase._show_shaper_logs = True
