import signal

def handle_exit(sig, frame):
    raise SystemExit()

signal.signal(signal.SIGTERM, handle_exit)
