#!/usr/bin/env python3
"""Parse role names or numbered menu choices, without silently dropping roles."""
import sys
ROLES=("consumer","provider","monitor","keeper")
def parse(raw):
    selected=[]
    for item in raw.lower().split(","):
        token=item.strip()
        if token in ("1","2","3","4"): token=ROLES[int(token)-1]
        if token not in ROLES or token in selected:
            raise ValueError("Choose distinct roles 1..4 or consumer,provider,monitor,keeper")
        selected.append(token)
    return ",".join(selected)
if __name__=="__main__":
    try: print(parse(sys.argv[1]))
    except (ValueError,IndexError) as e:
        print(str(e),file=sys.stderr); raise SystemExit(2)
