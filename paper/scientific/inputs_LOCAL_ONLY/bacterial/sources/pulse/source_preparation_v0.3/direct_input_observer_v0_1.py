"""Actual read-only tensor cloning; no GT, RNG draws or model/source rewrites."""
import ast,hashlib,inspect,json,shutil,sys,types
from pathlib import Path
import numpy as np
import torch
from native_stage_observer_v04_copy import install_observer as install_49

MIN_FREE=8*1024**3
def _install_observer(predictor):
    install_49(predictor)
    out=predictor.output_dir/'direct_trace';out.mkdir(exist_ok=False)
    records=[];counter={}
    def snapshot(kind,values):
        free=shutil.disk_usage(out).free
        if free<MIN_FREE:raise RuntimeError(f'Trace storage NO-GO free={free}')
        frame=int(predictor.i);key=(frame,kind);ordinal=counter.get(key,0);counter[key]=ordinal+1
        stem=f'{frame:04d}_{kind}_{ordinal:02d}';arrays={};topology={}
        def walk(value,path):
            if isinstance(value,torch.Tensor):
                copied=value.detach().clone().cpu()
                arrays[path]=copied.numpy().copy()
                topology[path]={'type':'tensor','shape':list(value.shape),'dtype':str(value.dtype),'device':str(value.device),'requires_grad':value.requires_grad}
            elif isinstance(value,np.ndarray):
                arrays[path]=value.copy();topology[path]={'type':'numpy','dtype':str(value.dtype),'shape':list(value.shape)}
            elif isinstance(value,dict):
                topology[path]={'type':'dict','keys':[str(k) for k in value]}
                for k,v in value.items():walk(v,path+'/'+str(k))
            elif isinstance(value,(list,tuple)):
                topology[path]={'type':type(value).__name__,'length':len(value)}
                for i,v in enumerate(value):walk(v,path+'/'+str(i))
            elif hasattr(value,'tensors') and hasattr(value,'mask'):
                topology[path]={'type':type(value).__name__};walk(value.tensors,path+'/tensors');walk(value.mask,path+'/mask')
            elif value is None or isinstance(value,(bool,str,int,float)):
                topology[path]={'type':type(value).__name__,'value':value}
            else:raise TypeError(f'Unsupported actual trace value {path}: {type(value)}')
        walk(values,'root')
        need=sum(a.nbytes for a in arrays.values())
        if free<MIN_FREE+2*need:raise RuntimeError(f'Trace storage NO-GO pending={need} free={free}')
        npz=out/(stem+'.npz');meta=out/(stem+'.json')
        with npz.open('xb') as f:np.savez_compressed(f,**arrays)
        with meta.open('x',encoding='utf-8') as f:json.dump({'frame':frame,'kind':kind,'ordinal':ordinal,'topology':topology,'uncompressed_bytes':need,'free_before':free},f,indent=2)
        record={'frame':frame,'kind':kind,'ordinal':ordinal,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (npz,meta)}}
        records.append(record)
        (out/'inventory.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    model=predictor.model
    def runtime():
        return {name:{key:getattr(module,key) for key in ('training','train_model','refine_track_queries','use_dab','two_stage') if hasattr(module,key)} for name,module in model.named_modules()}
    def before(module,args,kwargs):
        flags=runtime()
        if any(v.get('training') or v.get('train_model') for v in flags.values()):raise RuntimeError('Unexpected active training path')
        snapshot('before_model',{'targets':kwargs.get('targets'),'samples':args[0],'mapping':{k:{'present':hasattr(predictor,k),'value':getattr(predictor,k) if hasattr(predictor,k) else None} for k in ('cells','all_indices','track_indices','object_indices','div_indices','div_track','prevcells')},'runtime':flags})
    def after(module,args,kwargs,result):
        output=result[0] if isinstance(result,(list,tuple)) else result
        required=('pred_logits','pred_boxes','pred_masks','hs_embed')
        if not all(k in output for k in required):raise RuntimeError('Missing raw model output head')
        snapshot('raw_model_output',{k:output[k] for k in required})
    handles=[model.register_forward_pre_hook(before,with_kwargs=True),model.register_forward_hook(after,with_kwargs=True)]
    bases=[cls for cls in type(model).__mro__ if cls.__name__=='DeformableTransformer' and 'forward' in cls.__dict__]
    if len(bases)!=1:raise RuntimeError('Expected exactly one defining DeformableTransformer class in actual model MRO')
    consumer_class=bases[0];original=consumer_class.__dict__['forward'];func=original
    mro_method_bindings={}
    for cls in type(model).__mro__:
        if cls.__name__ in ('DETRSegmBase','DETRTrackingBase','DeformableDETR','DeformableTransformer') and 'forward' in cls.__dict__:
            method=cls.__dict__['forward'];method_source=Path(inspect.getsourcefile(method))
            mro_method_bindings[cls.__module__+'.'+cls.__qualname__]={'source':str(method_source),'source_sha256':hashlib.sha256(method_source.read_bytes()).hexdigest(),'code_firstlineno':method.__code__.co_firstlineno}
    source=Path(inspect.getsourcefile(func));tree=ast.parse(source.read_text(encoding='utf-8'))
    definition=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.lineno==func.__code__.co_firstlineno)
    nodes=[n for n in ast.walk(definition) if isinstance(n,ast.Assign)]
    def find(name,fragment):
        found=[n for n in nodes if any(isinstance(t,ast.Name) and t.id==name for t in n.targets) and fragment in ast.unparse(n.value)]
        if len(found)!=1:raise RuntimeError(f'Consumer anchor ambiguous: {name}/{fragment}')
        return found[0]
    stack=find('prev_boxes','torch.stack(');effective=find('prev_tgt','prev_hs_embed');ref=find('reference_points','prev_boxes[...,')
    # Line events precede execution. Sibling next statement observes completed assignment.
    def next_line(node):
        for parent in ast.walk(definition):
            for _,value in ast.iter_fields(parent):
                if isinstance(value,list) and node in value:
                    i=value.index(node)
                    if i+1<len(value):return value[i+1].lineno
        raise RuntimeError('Consumer anchor lacks following statement')
    anchors={next_line(stack):'consumer_stack',next_line(effective):'consumer_effective_content',next_line(ref):'consumer_reference_points'}
    (out/'consumer_source_binding.json').write_text(json.dumps({'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'anchors':anchors,'actual_model_class':type(model).__module__+'.'+type(model).__qualname__,'actual_MRO':[cls.__module__+'.'+cls.__qualname__ for cls in type(model).__mro__],'consumer_defining_class':consumer_class.__module__+'.'+consumer_class.__qualname__,'MRO_forward_source_bindings':mro_method_bindings,'dispatch':'Observed original defining function code via unchanged native MRO super call','scope':'Actual original consumer locals; learned refinement and reference-point construction unchanged'},indent=2),encoding='utf-8')
    def consumer(self,*args,**kwargs):
        if self is not model:raise RuntimeError('Unexpected shared-class consumer instance')
        if sys.gettrace() is not None:raise RuntimeError('Consumer requires untraced execution')
        seen=[]
        def local(frame,event,arg):
            if event=='line' and frame.f_lineno in anchors:
                kind=anchors[frame.f_lineno];loc=frame.f_locals
                keys={'consumer_stack':('prev_boxes','prev_hs_embed','output_target'),'consumer_effective_content':('prev_tgt','output_target'),'consumer_reference_points':('reference_points','num_track_queries','output_target')}[kind]
                snapshot(kind,{k:loc[k] for k in keys});seen.append(kind)
            return local
        def dispatch(frame,event,arg):return local if frame.f_code is func.__code__ else None
        sys.settrace(dispatch)
        completed=False
        try:
            result=original(self,*args,**kwargs)
            completed=True
            return result
        finally:
            sys.settrace(None)
            snapshot('consumer_applicability',{'captured':seen,'anchors_present':True,'original_consumer_returned':completed,'scope':'Finally-written capture; not a successful whole model-call certificate'})
    consumer_class.forward=consumer
    oldpost=predictor.post_process_masks
    def post(self,*args,**kwargs):
        result=oldpost(*args,**kwargs)
        if self._factorial_geometry_frame!=int(self.i):raise RuntimeError('Stale geometry frame')
        snapshot('postprocess_M_G',{'M':result[0],'G':self._factorial_geometry_masks,'cells':self.cells,'all_indices':self.all_indices,'arm':self._factorial_arm,'active':self._pulse_active})
        return result
    predictor.post_process_masks=types.MethodType(post,predictor)
    def close():
        for h in handles:h.remove()
        consumer_class.forward=original
    return close


def install_observer(predictor):
    """Transactional installation and close; retain partial disk evidence on failure."""
    sentinel=object()
    methods={key:predictor.__dict__.get(key,sentinel) for key in ('post_process_masks','preprocess_img','forward')}
    model=predictor.model
    modules=list(model.modules())
    hook_names=('_forward_hooks','_forward_pre_hooks','_forward_hooks_with_kwargs','_forward_pre_hooks_with_kwargs','_forward_hooks_always_called')
    hooks=[(module,{key:dict(getattr(module,key)) for key in hook_names if hasattr(module,key)}) for module in modules]
    forwards=[(module,module.__dict__.get('forward',sentinel)) for module in modules]
    consumer_classes=[cls for cls in type(model).__mro__ if cls.__name__=='DeformableTransformer' and 'forward' in cls.__dict__]
    class_forwards=[(cls,cls.__dict__['forward']) for cls in consumer_classes]
    previous_trace=sys.gettrace()
    def restore():
        for cls,value in class_forwards:cls.forward=value
        for key,value in methods.items():
            if value is sentinel:predictor.__dict__.pop(key,None)
            else:predictor.__dict__[key]=value
        for module,states in hooks:
            for key,state in states.items():
                current=getattr(module,key);current.clear();current.update(state)
        for module,value in forwards:
            if value is sentinel:module.__dict__.pop('forward',None)
            else:module.__dict__['forward']=value
        sys.settrace(previous_trace)
    try:original_close=_install_observer(predictor)
    except BaseException:
        restore()
        raise
    def close():
        try:original_close()
        finally:restore()
    return close
