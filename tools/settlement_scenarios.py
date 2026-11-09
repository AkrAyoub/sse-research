#!/usr/bin/env python3
"""Calculate escrow allocations for a set of admissible service histories."""
import argparse
import json
from pathlib import Path

HISTORY={'N':1, 'F':2, 'S':4}

def bounds(histories,fee,reservation):
    if not histories or not set(histories)<=set(HISTORY) or not 0<=reservation<=fee or fee<=0:
        raise ValueError('invalid financial history model')
    funds={'N':reservation,'F':0,'S':fee}
    allowed=[funds[h] for h in histories]
    lower,upper=min(allowed),max(allowed)
    return {'provider_credit':lower,'consumer_refund':fee-upper,'unresolved':upper-lower,
            'lower_bound':lower,'upper_bound':upper}


def scenarios(fee=25,reservation=5):
    specs=[('no-conclusive-evidence',['N','F','S']),
           ('ack-only',['F','S']),
           ('certified-success',['S']),
           ('certified-failure-no-ack',['N','F']),
           ('failure-and-ack',['F'])]
    data=[]
    for name,histories in specs:
        outcome=bounds(histories,fee,reservation)
        assert sum(outcome[k] for k in ('provider_credit','consumer_refund','unresolved')) == fee
        data.append({'scenario':name,'histories':histories,**outcome})
    return data


def report(fee=25,reservation=5):
    return {'mode':'simulation',
            'parameters':{'fee_units':fee,'reservation_units':reservation},
            'results':scenarios(fee,reservation)}

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--fee',type=int,default=25)
    parser.add_argument('--reservation',type=int,default=5)
    parser.add_argument('--output')
    args=parser.parse_args()
    payload=report(args.fee,args.reservation)
    rendered=json.dumps(payload,indent=2)+'\n'
    if args.output:Path(args.output).write_text(rendered)
    else:print(rendered,end='')
