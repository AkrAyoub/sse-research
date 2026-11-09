#!/usr/bin/env python3
"""Map changed paths to deployment roles."""
import sys,json
ROLE_PATHS={
    'monitor':['services/monitor-agent/'],
    'provider':['services/provider-agent/'],
    'consumer':['services/consumer-app/'],
    'dashboard':['apps/control-plane/'],
    'logs':['infra/observability/'],
}
SENSITIVE={'contract','node','inventory','governance'}
def plan(files):
    updates=set(); approvals=[]
    for name in files:
        for role,prefixes in ROLE_PATHS.items():
            if any(name.startswith(p) for p in prefixes): updates.add(role)
        if name.startswith(('contracts/','foundry/','contracts/')): approvals.append('contract changes require review')
        if name.startswith(('infra/ethereum/','infra/ansible/')): approvals.append('infrastructure changes require review')
        if name.startswith('infra/inventory/'): approvals.append('inventory changes require review')
    return {'auto_candidate_roles':sorted(updates),'manual_review':sorted(set(approvals))}
if __name__=='__main__':
    print(json.dumps(plan(sys.argv[1:]),indent=2))
