#!/usr/bin/env python3
"""Exact committee risk under uniform sampling without replacement.
Analytical model, NOT a benchmark or an estimate of actual operator independence.
"""
import argparse,json,math
from fractions import Fraction

def risk(population,adversarial,seats):
    if any(type(x) is not int for x in (population,adversarial,seats)) or not (4<=seats<=population and 0<=adversarial<=population):
        raise ValueError("invalid committee parameters")
    b=(seats-1)//3
    q=seats-b
    denominator=math.comb(population,seats)
    distribution={}
    for a in range(max(0,seats-(population-adversarial)),min(seats,adversarial)+1):
        distribution[a]=Fraction(math.comb(adversarial,a)*math.comb(population-adversarial,seats-a),denominator)
    assert sum(distribution.values())==1
    exceed=sum((p for a,p in distribution.items() if a>b),Fraction(0))
    capture=sum((p for a,p in distribution.items() if a>=q),Fraction(0))
    def encode(p):return {"numerator":str(p.numerator),"denominator":str(p.denominator),"probability":float(p)}
    return {"population":population,"adversarialIdentities":adversarial,"seats":seats,"quorum":q,"assumedByzantineTolerance":b,
            "faultBoundExceeded":encode(exceed),"attackerQuorum":encode(capture),"distribution":{str(a):encode(p) for a,p in distribution.items()},
            "assumptions":["uniform sample without replacement","fixed eligible population and adversarial subset before entropy","no selection or cancellation bias"],
            "actualOperatorIndependenceEstablished":False,"liveV3GlobalUniformityEstablished":False}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--population",type=int,required=True)
    p.add_argument("--adversarial",type=int,required=True)
    p.add_argument("--seats",type=int,required=True)
    a=p.parse_args()
    print(json.dumps(risk(a.population,a.adversarial,a.seats),indent=2))
if __name__=="__main__":main()
