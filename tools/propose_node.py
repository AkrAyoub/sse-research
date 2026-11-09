#!/usr/bin/env python3
"""Create a validated, PENDING VM enrollment request; no remote access or role activation.

Typical use: python3 tools/propose_node.py --name cloud-c --ip 10.0.0.12 \\
  --roles provider monitor --client none --out infra/inventory/proposals/cloud-c.json
"""
import argparse, json, sys, os
from pathlib import Path
from validate_inventory import validate

def build_proposal(name: str, ip: str, roles: list[str], client: str,
                   ssh_user: str='ubuntu', environment: str='staging') -> dict:
    node={'node_id':name,'address':ip,'ssh_user':ssh_user,
          'roles':list(roles),'ethereum_client':client,'status':'pending'}
    validate({'environment':environment,'nodes':[node]})
    return {'environment':environment,'nodes':[node]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name',required=True);p.add_argument('--ip',required=True)
    p.add_argument('--roles',required=True,nargs='+');p.add_argument('--client',default='none')
    p.add_argument('--ssh-user',default='ubuntu');p.add_argument('--environment',default='staging')
    p.add_argument('--out',required=True)
    a=p.parse_args()
    proposal=build_proposal(a.name,a.ip,a.roles,a.client,a.ssh_user,a.environment)
    target=Path(a.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(str(target),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f: json.dump(proposal,f,indent=2);f.write('\n')
    print(target)

if __name__=='__main__':
    try:main()
    except (ValueError,FileExistsError) as e:
        print(f'ERROR: {e}',file=sys.stderr);sys.exit(1)
