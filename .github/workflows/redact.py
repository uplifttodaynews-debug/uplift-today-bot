"""Copies stdin to stdout and to preview-log.txt with every secret value replaced by ***."""
import os
import sys

secrets = [v for k, v in os.environ.items() if v and len(v) > 6 and any(w in k for w in ("KEY", "SECRET", "TOKEN", "CLIENT_ID"))]
out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "previews", "preview-log.txt"), "w")
for line in sys.stdin:
    for s in secrets:
        line = line.replace(s, "***")
    sys.stdout.write(line)
    out.write(line)
    out.flush()
