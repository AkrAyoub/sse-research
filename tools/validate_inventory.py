#!/usr/bin/env python3
"""Static inventory validation only. Does not trust or provision the named machines."""
import sys,json,ipaddress,re
from pathlib import Path
ALLOWED_ROLES={'provider','consumer','monitor','ethereum_full_node','validator','rpc','observer','dashboard','logs'}
ALLOWED_CLIENTS={'none','el_cl','el_cl_vc'}
ALLOWED_STATUS={'pending','approved','active','quarantined','retired'}
NAME=re.compile(r'^[a-z][a-z0-9-]{0,62}$')

def validate(data):
    if data.get('environment') not in {'staging','production'}: raise ValueError('Invalid environment')
    nodes=data.get('nodes')
    if not isinstance(nodes,list): raise ValueError('nodes must be list')
    ids=set(); addresses=set()
    for node in nodes:
        if set(node)!={'node_id','address','ssh_user','roles','ethereum_client','status'}:
            raise ValueError('unexpected or missing fields')
        name=node['node_id']; addr=node['address']; roles=node['roles']; client=node['ethereum_client']
        if not isinstance(name,str) or not NAME.fullmatch(name) or name in ids: raise ValueError('bad/duplicate node_id')
        if not isinstance(addr,str): raise ValueError('address must be string')
        try: ipaddress.ip_address(addr)
        except ValueError: raise ValueError('address must be an IP, not a shell command or URL')
        if addr in addresses: raise ValueError('duplicate address')
        if not isinstance(node['ssh_user'],str) or not NAME.fullmatch(node['ssh_user']): raise ValueError('bad ssh_user')
        if not isinstance(roles,list) or not roles or len(set(roles)) != len(roles) or not set(roles)<=ALLOWED_ROLES: raise ValueError('bad roles')
        if client not in ALLOWED_CLIENTS: raise ValueError('bad client type')
        if ('validator' in roles) != (client=='el_cl_vc'): raise ValueError('validator must declare EL+CL+VC; VC is NOT evidence of activation')
        if 'ethereum_full_node' in roles and client == 'none': raise ValueError('full node requires EL+CL')
        if node['status'] not in ALLOWED_STATUS: raise ValueError('bad status')
        ids.add(name); addresses.add(addr)
    return len(nodes)
if __name__=='__main__':
    try: print(f'Valid inventory ({validate(json.loads(Path(sys.argv[1]).read_text()))} nodes)')
    except Exception as err: print(f'INVALID inventory: {err}',file=sys.stderr); sys.exit(1)
