"""Validate real HWH contracts and deterministic failure cases without a board."""
from pathlib import Path
import copy,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'skill/scripts'))
from pynq_tools import load_config,check_overlay,compare_arrays
import numpy as np
def main():
    rows=[]
    for name in ['loopback','award_sobel']:
        c=load_config(ROOT/('skill/examples/'+name+'.json'));result=check_overlay(c)
        rows.append(dict(case=name,status='PASS',metadata=result))
        for case,changes,exception in [('missing_file',{'bitfile':'/not_present/test.bit'},FileNotFoundError),
                ('missing_ip',{'dma_ip':'not_present_dma'},ValueError),
                ('length_overflow',{'input_shape':[1000000000]},ValueError),
                ('zero_timeout',{'timeout_s':0},ValueError)]:
            test=copy.deepcopy(c);test.update(changes)
            try:check_overlay(test)
            except exception:rows.append(dict(case=name+'_'+case,status='PASS',expected_failure=True))
            else:raise AssertionError('Contract did not reject '+case)
    result=compare_arrays(np.array([0,1],dtype=np.uint32),np.array([0,2],dtype=np.uint32))
    assert not result['passed'] and result['mismatches']==1 and result['first_mismatch']==[1]
    rows.append(dict(case='mismatch_diagnostic',status='PASS',detail=result))
    out=ROOT/'validation/skill_contracts.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
