"""Standalone mask-instance correspondence; no image model, injection labels or GT producer."""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import linear_sum_assignment

@dataclass
class MaskFrame:
    ids: np.ndarray
    masks: np.ndarray
    frame: int
    support_definition: str

    def __post_init__(self):
        ids=np.asarray(self.ids);masks=np.asarray(self.masks)
        if ids.ndim!=1 or ids.dtype.kind not in 'iu' or len(set(ids))!=len(ids):
            raise ValueError('Unique integer instance IDs required')
        if ids.dtype.kind=='u' and ids.size and int(ids.max())>np.iinfo(np.int64).max:
            raise ValueError('Instance ID overflow')
        if masks.ndim!=3 or masks.dtype.kind!='b' or len(masks)!=len(ids):
            raise ValueError('Explicit NxHxW boolean instance support required')
        if isinstance(self.frame,(bool,np.bool_)) or not isinstance(self.frame,(int,np.integer)):
            raise ValueError('Integral frame index required')
        if not isinstance(self.support_definition,str) or not self.support_definition.strip():
            raise ValueError('Declare support interpretation; no implicit thresholding')
        self.ids=ids.astype(np.int64,copy=True);self.masks=masks.copy()

def match_iou(pred,reference, *, gate):
    """Strict IoU>gate; max cardinality then sum IoU; overlap supports allowed."""
    if pred.frame!=reference.frame or pred.masks.shape[1:]!=reference.masks.shape[1:]:
        raise ValueError('Frames and pixel array shapes must agree')
    if not np.isfinite(gate) or not 0<gate<1:
        raise ValueError('Declare finite IoU gate in (0,1)')
    if not len(pred.ids) or not len(reference.ids):return {}
    pi=np.argsort(pred.ids);ri=np.argsort(reference.ids)
    p=pred.masks[pi].reshape(len(pi),-1).astype(float)
    r=reference.masks[ri].reshape(len(ri),-1).astype(float)
    intersection=r@p.T
    union=r.sum(axis=1)[:,None]+p.sum(axis=1)[None,:]-intersection
    iou=np.divide(intersection,union,out=np.zeros_like(intersection),where=union>0)
    allowed=iou>gate
    cost=np.where(allowed,1-iou,2*(min(len(pi),len(ri))+1))
    rows,cols=linear_sum_assignment(cost)
    return {int(reference.ids[ri[a]]):int(pred.ids[pi[b]]) for a,b in zip(rows,cols) if allowed[a,b]}
