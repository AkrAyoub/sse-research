#!/usr/bin/env python3
"""R181 read-only bounded observer Beacon database inventory.

Never read file content, follow links, change Docker, or inspect Engine JWT.
"""
from __future__ import annotations
import json
from pathlib import Path
import stat
import sys

ROOT=Path("/root/.local/share/sse-r137-node-8be265272c35f3d8c3a0/beacon")
MAX_ENTRIES=256
MAX_DEPTH=4

class Refused(ValueError): pass

def inventory(root=ROOT):
    if root!=ROOT or root.is_symlink() or not root.is_dir():
        raise Refused("unexpected or missing exact Beacon data root")
    count=0
    total_file_bytes=0
    files=0
    directories=0
    symlinks=0
    summary=[]
    pending=[(root,0)]
    while pending:
        folder,depth=pending.pop()
        try:
            entries=list(folder.iterdir())
        except OSError as exc:
            raise Refused("Beacon database directory not readable") from exc
        for item in entries:
            count+=1
            if count>MAX_ENTRIES:
                raise Refused("Beacon inventory exceeds safe entry limit")
            mode=item.lstat().st_mode
            if stat.S_ISLNK(mode):
                symlinks+=1
                kind="symlink"
                size=None
            elif stat.S_ISDIR(mode):
                directories+=1
                kind="directory"
                size=None
                if depth+1<=MAX_DEPTH:
                    pending.append((item,depth+1))
            elif stat.S_ISREG(mode):
                files+=1
                kind="file"
                size=item.lstat().st_size
                total_file_bytes+=size
            else:
                raise Refused("unexpected Beacon DB special file")
            # Relative basename only, not private absolute paths.
            relative=str(item.relative_to(root))
            if len(relative)>256:
                raise Refused("Beacon relative path too long")
            summary.append({"relativePath":relative,"type":kind,
                            "sizeBytes":size})
    return {
      "schema":"SSE_R181_VM4709_READONLY_BEACON_DB_INVENTORY_V1",
      "entryCount":count, "regularFiles":files,
      "directories":directories, "symlinksNotFollowed":symlinks,
      "regularFileBytes":total_file_bytes,
      "depthLimit":MAX_DEPTH, "entryLimit":MAX_ENTRIES,
      "beaconDataAppearsEmpty":count==0,
      "stateModified":False, "jwtOrBeaconFileContentsRead":False,
      "entries":sorted(summary,key=lambda x:x["relativePath"])
    }

if __name__=="__main__":
    try:
        print(json.dumps(inventory(),indent=2,sort_keys=True))
    except (Refused,OSError,ValueError) as exc:
        print("R181_READONLY_BEACON_INVENTORY_REFUSED: "+str(exc),file=sys.stderr)
        sys.exit(2)
