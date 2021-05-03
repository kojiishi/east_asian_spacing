import logging

from east_asian_spacing.shaper import show_dump_images


def init_logging(verbose):
    if not verbose or verbose <= 0:
        return

    if verbose <= 1:
        logging.basicConfig(level=logging.INFO)
        return

    logging.basicConfig(level=logging.DEBUG)
    if verbose <= 2:
        return

    show_dump_images()
