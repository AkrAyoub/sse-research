"""R117 exact-stale-owner recovery guards, all operations mocked."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import sse_pos_r117_owner_stale_stopped_endpoint_recovery as m

def fixture():
    private={"Driver":"bridge","Internal":True,"Id":"private-id","Containers":{}}
    public={"Driver":"bridge","Internal":False,"EnableIPv6":True,"Containers":{}}
    cs={}
    for name,(ip,alias) in m.EXPECTED.items():
        cs[name]={
          "State":{"Running":False,"Status":"exited"},
          "HostConfig":{"NetworkMode":m.PRIVATE,"PortBindings":{
              k:[{"HostIp":host,"HostPort":port}] for k,(host,port) in m.PORTS[name].items()}},
          "NetworkSettings":{"Networks":{m.PRIVATE:{
              "NetworkID":"private-id","EndpointID":"","IPAddress":"",
              "Aliases":[alias] if alias else [],"IPAMConfig":{"IPv4Address":ip} if name==m.BN else None
          }}}
        }
    cs[m.VC]={"State":{"Running":False}}
    return {m.PRIVATE:private,m.PUBLIC:public},cs

class R117Tests(unittest.TestCase):
    def test_exact_exited_stale_state_accepted(self):
        networks,cs=fixture()
        with patch.object(m,"cmd",return_value=m.OWNER_IP+"/40"),patch.object(
                m,"network",side_effect=lambda n:networks[n]),patch.object(
                m,"inspect",side_effect=lambda n:cs[n]):
            self.assertEqual(set(m.validate()),set(m.EXPECTED))
    def test_live_validator_refused(self):
        networks,cs=fixture()
        cs[m.VC]["State"]["Running"]=True
        with patch.object(m,"cmd",return_value=m.OWNER_IP+"/40"),patch.object(
                m,"network",side_effect=lambda n:networks[n]),patch.object(
                m,"inspect",side_effect=lambda n:cs[n]),self.assertRaises(m.Refused):
            m.validate()
    def test_actual_endpoint_not_treated_as_stale(self):
        networks,cs=fixture()
        cs[m.EL]["NetworkSettings"]["Networks"][m.PRIVATE]["EndpointID"]="live"
        with patch.object(m,"cmd",return_value=m.OWNER_IP+"/40"),patch.object(
                m,"network",side_effect=lambda n:networks[n]),patch.object(
                m,"inspect",side_effect=lambda n:cs[n]),self.assertRaises(m.Refused):
            m.validate()
    def test_unexpected_network_refused(self):
        networks,cs=fixture()
        cs[m.BN]["NetworkSettings"]["Networks"][m.PUBLIC]={}
        with patch.object(m,"cmd",return_value=m.OWNER_IP+"/40"),patch.object(
                m,"network",side_effect=lambda n:networks[n]),patch.object(
                m,"inspect",side_effect=lambda n:cs[n]),self.assertRaises(m.Refused):
            m.validate()
    def test_engine_exposure_refused(self):
        networks,cs=fixture()
        cs[m.EL]["HostConfig"]["PortBindings"]["8551/tcp"]=[{"HostIp":"::","HostPort":"8551"}]
        with patch.object(m,"cmd",return_value=m.OWNER_IP+"/40"),patch.object(
                m,"network",side_effect=lambda n:networks[n]),patch.object(
                m,"inspect",side_effect=lambda n:cs[n]),self.assertRaises(m.Refused):
            m.validate()
    def test_never_uses_container_create_or_validator_start(self):
        s=(ROOT/"tools"/"sse_pos_r117_owner_stale_stopped_endpoint_recovery.py").read_text()
        self.assertIn('docker("network","disconnect","--force",PRIVATE,name)',s)
        self.assertIn('docker("network","connect",PUBLIC,name)',s)
        self.assertNotIn('docker("rm"',s)
        self.assertNotIn('docker("create"',s)
        self.assertNotIn('docker("start",VC)',s)

if __name__=="__main__":
    unittest.main()
