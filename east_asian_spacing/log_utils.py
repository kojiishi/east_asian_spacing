import logging

_log_shaper_logs = False


def init_logging(verbose, loggers=None, main=None):
    if not verbose or verbose <= 0:
        return

    if main:
        assert loggers is None
        loggers = [main]
    if loggers:
        if verbose <= len(loggers):
            for logger in loggers[0:verbose]:
                console = logging.StreamHandler()
                logger.addHandler(console)
                logger.setLevel(logging.INFO)
            return
        verbose -= len(loggers)
        assert verbose > 0

    if verbose <= 1:
        logging.basicConfig(level=logging.INFO)
        return

    logging.basicConfig(level=logging.DEBUG)
    if verbose <= 2:
        return

    global _log_shaper_logs
    _log_shaper_logs = True
