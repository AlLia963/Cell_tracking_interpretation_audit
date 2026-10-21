"""Orient saved comparison readouts without recomputing their native witnesses."""
def reverse_pair_record(record):
    r=dict(record)
    r.setdefault('witness_native_before_graph',record['before_graph'])
    r.setdefault('witness_native_after_graph',record['after_graph'])
    for prefix,suffixes in [('canonical_',['']),('',['_minimum','_maximum'])]:
        for suffix in suffixes:
            for a,b in [('before_TP','after_TP'),('gains','losses')]:
                ka,kb=prefix+a+suffix,prefix+b+suffix
                if ka in r and kb in r:r[ka],r[kb]=r[kb],r[ka]
    for side in ['min','max']:
        a,b='independent_gain_'+side,'independent_loss_'+side
        if a in r and b in r:r[a],r[b]=r[b],r[a]
    if r.get('canonical_net') not in [None,'']:r['canonical_net']=-int(r['canonical_net'])
    if r.get('net_minimum') not in [None,'']:
        r['net_minimum'],r['net_maximum']=-int(record['net_maximum']),-int(record['net_minimum'])
    r['before_graph'],r['after_graph']=record['after_graph'],record['before_graph']
    r['witness_original_direction_reversed']=not bool(record.get('witness_original_direction_reversed',False))
    r['witness_readout_transform']='swap sides, gain/loss and before/after TP; negate net with min/max exchange'if r['witness_original_direction_reversed']else'native direction'
    return r

def orient_witness_values(values,reversed_direction):
    if not reversed_direction:return dict(values)
    return {'before_TP':values['after_TP'],'after_TP':values['before_TP'],'gains':values['losses'],'losses':values['gains'],'net':-values['net']}
