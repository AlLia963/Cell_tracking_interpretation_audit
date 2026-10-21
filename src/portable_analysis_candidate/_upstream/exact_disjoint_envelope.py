"""Exact optimal-correspondence envelope for DISJOINT reference instances.

Strict IoU > 1/2 only. Prediction instances may overlap. Pixel registration
and biological meaning of derived supports remain the caller's obligation.
Not an envelope for coordinate matching or overlapping reference instances.
"""
import numpy as np

def envelope(pred,reference):
    if pred.frame!=reference.frame or pred.masks.shape[1:]!=reference.masks.shape[1:]:
        raise ValueError('registered same-frame pixel arrays required')
    if np.any(reference.masks.sum(axis=0)>1):
        raise ValueError('disjoint-reference contract violated')
    result={};claimed={}
    for rid,rm in zip(reference.ids,reference.masks):
        best=None;choices=[]
        for pid,pm in zip(pred.ids,pred.masks):
            intersection=int(np.count_nonzero(rm&pm));union=int(np.count_nonzero(rm|pm))
            if not union or 2*intersection<=union:continue
            # A predicted support cannot pass >1/2 IoU for two disjoint references.
            if int(pid) in claimed:raise AssertionError('strict-majority uniqueness violated')
            claimed[int(pid)]=int(rid)
            if best is None or intersection*best[1]>best[0]*union:
                best=(intersection,union);choices=[int(pid)]
            elif intersection*best[1]==best[0]*union:choices.append(int(pid))
        result[int(rid)]=tuple(sorted(choices))
    return result

def edge_envelope(source_options,target_options,edges):
    """Return certain/possible visibility, not a selected canonical value.

    Domains at adjacent frames are independently optimal under the disjoint
    reference contract. Empty domain means invisible under every optimum.
    edges must be the appropriate typed OR untyped relation, explicitly chosen.
    """
    if not source_options or not target_options:return (False,False)
    outcomes=[(x,y) in edges for x in source_options for y in target_options]
    return (all(outcomes),any(outcomes))
