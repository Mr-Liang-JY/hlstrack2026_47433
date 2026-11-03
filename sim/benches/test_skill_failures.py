from pathlib import Path
from types import SimpleNamespace
import sys,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'skill/scripts'))
from pynq_tools import DmaRunner,load_config

class FakeBuffer(np.ndarray):
    def flush(self):pass
    def invalidate(self):pass
    def freebuffer(self):self.released=True

class FakeDma:
    def __init__(self,error=0):
        self.mmio=self;self.reset_done=False;self.error=error
        self.sendchannel=self.recvchannel=SimpleNamespace(transfer=lambda value:None,wait=lambda:None)
    def read(self,address):return 0 if address==0 else 1 if self.reset_done else self.error
    def write(self,address,value):self.reset_done=True

class FailureChecks(unittest.TestCase):
    def exercise(self,error,expected):
        config=load_config(ROOT/'skill/examples/loopback.json');config['timeout_s']=.003
        dma=FakeDma(error);overlay=SimpleNamespace(ip_dict={'axi_dma_0':{}},axi_dma_0=dma)
        def allocate(shape,dtype):return np.zeros(shape,dtype).view(FakeBuffer)
        runner=DmaRunner(config,overlay=overlay,allocator=allocate)
        with self.assertRaises(expected):runner.transfer(np.zeros(config['input_shape'],np.uint32))
        self.assertTrue(runner.last_failure['reset_quiescent'])
        self.assertEqual(runner.last_failure['type'],expected.__name__)
        self.assertEqual(runner.last_failure['tx_status'],'0x%08X'%error)
        runner.close();self.assertTrue(runner.tx.released);self.assertTrue(runner.rx.released)
    def test_timeout_saves_status_and_resets_before_free(self):self.exercise(0,TimeoutError)
    def test_dma_error_saves_status_and_resets_before_free(self):self.exercise(0x10,RuntimeError)

if __name__=='__main__':unittest.main(verbosity=2)
