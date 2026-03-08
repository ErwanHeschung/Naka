import logging
import sys

class NakaLogger(logging.Formatter):
    BLUE = "\033[34m"      # System output
    LIGHT_GRAY = "\033[37m" # Standard output
    RED = "\033[31m"       # Errors
    RESET = "\033[0m"      # Reset color

    FORMATS = {
        logging.DEBUG: LIGHT_GRAY + "%(message)s" + RESET,
        logging.INFO: BLUE + "[SYSTEM] %(message)s" + RESET,
        logging.WARNING: LIGHT_GRAY + "[WARN] %(message)s" + RESET,
        logging.ERROR: RED + "[ERROR] %(message)s" + RESET,
        logging.CRITICAL: RED + "[CRITICAL] %(message)s" + RESET,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def get_logger(name="Naka"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(NakaLogger())
        logger.addHandler(console_handler)
    
    return logger

log = get_logger()