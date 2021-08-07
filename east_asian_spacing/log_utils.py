import logging

_log_shaper_logs = False


def _to_loggers(loggers):
    if isinstance(loggers, str):
        return [logging.getLogger(name) for name in loggers.split(',')]
    if isinstance(loggers, logging.Logger):
        return [loggers]
    return loggers


def _set_level(loggers, handler, level):
    for logger in loggers:
        logger.addHandler(handler)
        logger.setLevel(level)


def init_logging(verbose: int, main=None, debug=None):
    if (main and verbose > 0) or debug:
        handler = logging.StreamHandler()
        if debug:
            format = '%(levelname)s:%(name)s:%(message)s'
            formatter = logging.Formatter(format)
            handler.setFormatter(formatter)

        if main and verbose > 0:
            main = _to_loggers(main)
            if verbose <= len(main):
                _set_level(main[0:verbose], handler, logging.INFO)
            verbose -= len(main)

        if debug:
            debug = _to_loggers(debug)
            _set_level(debug, handler, logging.DEBUG)

    if verbose <= 0:
        return

    verbose -= 1
    if verbose <= 0:
        logging.basicConfig(level=logging.INFO)
        return

    logging.basicConfig(level=logging.DEBUG)
    verbose -= 1
    if verbose <= 0:
        return

    global _log_shaper_logs
    _log_shaper_logs = True
