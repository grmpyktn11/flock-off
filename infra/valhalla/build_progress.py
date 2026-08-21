"""Show how far a Valhalla tile build has got.

    python infra/valhalla/build_progress.py --container valhalla-dmv
    python infra/valhalla/build_progress.py --container valhalla-dmv --watch

Valhalla logs each stage as it starts and reports a TIMING line when it
ends, but it does not report a percentage or say what is still to come.
This reads the container log, matches it against the known stage order,
and prints what is done, what is running, and how long each took.
"""

import argparse
import pathlib
import re
import subprocess
import sys
import time

# Ordered as mjolnir runs them. The pattern is the first line that appears
# once the stage is underway.
STAGES = [
    ("download extracts", r"Downloading\s+http"),
    ("parse ways", r"Parsing ways\.\.\."),
    ("parse relations", r"Parsing relations\.\.\."),
    ("parse nodes", r"Parsing nodes\.\.\."),
    ("construct edges", r"BuildEdges took"),
    ("build local tiles", r"Building \d+ tiles with"),
    ("enhance", r"Start stage = enhance"),
    ("hierarchy", r"Done HierarchyBuilder"),
    ("shortcuts", r"Creating shortcuts on level"),
    ("turn restrictions", r"Adding complex turn restrictions"),
    ("validate", r"GraphValidator|Validating tiles|validator\.cc"),
    # Detected by the tarball appearing on disk, not by a log line: the
    # startup warning mentions valhalla_tiles.tar long before it exists.
    ("cleanup + tarball", None),
]

TIMESTAMP = re.compile(r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def read_log(container):
    result = subprocess.run(
        ["docker", "logs", container],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return ANSI.sub("", result.stdout + result.stderr).splitlines()


def stage_times(lines):
    """First timestamp each stage was seen at, in stage order."""
    seen = {}
    for line in lines:
        stamp = TIMESTAMP.match(line)
        for name, pattern in STAGES:
            if pattern and name not in seen and re.search(pattern, line):
                seen[name] = stamp.group(1) if stamp else ""
    return seen


def elapsed(lines):
    stamps = [TIMESTAMP.match(x).group(1) for x in lines if TIMESTAMP.match(x)]
    if len(stamps) < 2:
        return None
    fmt = "%Y/%m/%d %H:%M:%S"
    first = time.mktime(time.strptime(stamps[0], fmt))
    last = time.mktime(time.strptime(stamps[-1], fmt))
    return first, last


def is_serving(port):
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://localhost:{port}/status", timeout=3):
            return True
    except Exception:
        return False


def tarball_mb(tile_dir):
    tar = pathlib.Path(tile_dir) / "valhalla_tiles.tar"
    return tar.stat().st_size / 1e6 if tar.exists() else None


def render(container, port, tile_dir):
    lines = read_log(container)
    if not lines:
        return f"no log output from container {container}"

    seen = stage_times(lines)
    done = is_serving(port)

    tar_mb = tarball_mb(tile_dir)
    if tar_mb is not None:
        seen["cleanup + tarball"] = ""
    # The running stage is the last one that started; everything before it
    # has finished, everything after has not begun.
    started = [n for n, _ in STAGES if n in seen]
    current = started[-1] if started else None

    out = []
    for name, _ in STAGES:
        if done or (name in seen and name != current):
            mark, when = "done   ", seen.get(name, "")
        elif name == current:
            mark, when = "RUNNING", seen[name]
        else:
            mark, when = "       ", ""
        out.append(f"  [{mark}] {name:<20} {when[-8:]}")

    span = elapsed(lines)
    header = f"{container}: {len(started)}/{len(STAGES)} stages"
    if span:
        header += f", {(span[1] - span[0]) / 60:.0f} min elapsed"
    if tar_mb is not None:
        header += f", tarball {tar_mb:.0f} MB"
    if done:
        header += "  -- SERVING, BUILD COMPLETE"

    tail = [x for x in lines if TIMESTAMP.match(x)]
    footer = "\n  last log: " + (tail[-1][:100] if tail else "none")
    return header + "\n" + "\n".join(out) + footer


def main(argv=None):
    parser = argparse.ArgumentParser()
    # Each of these may be a comma-separated list to watch several builds
    # side by side; the Nth container uses the Nth port and directory.
    parser.add_argument("--container", default="valhalla-dmv")
    parser.add_argument("--port", default="8003")
    parser.add_argument("--watch", action="store_true", help="refresh until done")
    parser.add_argument("--interval", type=int, default=20)
    parser.add_argument("--dir", default=r"C:alhalla\dmv\custom_files")
    args = parser.parse_args(argv)

    names = args.container.split(",")
    ports = [int(p) for p in str(args.port).split(",")]
    dirs = args.dir.split(",")

    while True:
        text = "\n\n".join(
            render(name, ports[i], dirs[i]) for i, name in enumerate(names)
        )
        if not args.watch:
            print(text)
            return 0
        # Redraw in place rather than scrolling the terminal.
        sys.stdout.write("\x1b[2J\x1b[H" + text + "\n")
        sys.stdout.flush()
        if "BUILD COMPLETE" in text:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
