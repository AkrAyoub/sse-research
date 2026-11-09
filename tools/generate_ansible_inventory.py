#!/usr/bin/env python3
"""Render an Ansible inventory grouped by node roles."""
import argparse, json
from pathlib import Path
from validate_inventory import validate, ALLOWED_ROLES


def render(data):
    validate(data)
    approved=[n for n in data['nodes'] if n['status'] in ('approved','active')]
    rows=['[sse_managed]']
    for n in sorted(approved,key=lambda x:x['node_id']):
        roles=json.dumps(n['roles'],separators=(',', ':'))
        rows.append(f"{n['node_id']} ansible_host={n['address']} ansible_user={n['ssh_user']} sse_roles='{roles}'")
    for role in sorted(ALLOWED_ROLES):
        hosts=[n['node_id'] for n in approved if role in n['roles']]
        if hosts:
            rows+=['',f'[{role}]',*sorted(hosts)]
    rows.append('')
    return '\n'.join(rows)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('inventory')
    p.add_argument('--output')
    a=p.parse_args()
    content=render(json.loads(Path(a.inventory).read_text()))
    if a.output: Path(a.output).write_text(content)
    else: print(content,end='')
