"""Independent scientific figures from fixed records and actual pixel crops."""
from pathlib import Path
import json,shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--retained-figures',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();D=args.input_root.resolve();Q=D;OLD=args.retained_figures.resolve();O=args.output.resolve();O.mkdir(parents=True,exist_ok=False)
BLUE='#0072B2';ORANGE='#D55E00';PURPLE='#AA4499';GREEN='#009E73';GREY='#888888';DARK='#222222'
plt.rcParams.update({'font.family':'Arial','font.size':9,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})
manifest={'main':[],'supplement':[],'generated_experimental_images':False,'main_width_mm':165,'sources':{}}
def save(fig,label,stem,caption,sources,group='main'):
    assert len(fig.axes)==1
    for ext in ['png','pdf','svg']:fig.savefig(O/(stem+'.'+ext),dpi=450,bbox_inches='tight',pad_inches=.045)
    width={'Figure 2':158,'Figure 4':145,'Figure 5':130,'Figure 7':115,'Figure S4':158,'Figure S5':158}.get(label,165)
    manifest[group].append({'label':label,'stem':stem,'path':str(O/(stem+'.png')),'pdf':str(O/(stem+'.pdf')),'svg':str(O/(stem+'.svg')),'caption':caption,'source_records':sources,'width_mm':width,'one_experiment_or_query_per_figure':True});plt.close(fig)
def axes(height):
    f,a=plt.subplots(figsize=(165/25.4,height));a.spines[['top','right']].set_visible(False);return f,a
def copy_figure(old,label,stem,caption,group='main'):
    for ext in ['png','pdf','svg']:shutil.copy2(OLD/(old+'.'+ext),O/(stem+'.'+ext))
    manifest[group].append({'label':label,'stem':stem,'path':str(O/(stem+'.png')),'pdf':str(O/(stem+'.pdf')),'svg':str(O/(stem+'.svg')),'caption':caption,'width_mm':165,'retained_existing_figure':str(OLD/(old+'.png'))})
copy_figure('Figure1_shared_correspondence','Figure 1','Figure1_shared_correspondence','The complete shared-correspondence task. Black arrows are reference relations, blue arrows are actual saved predicted pairs, grey dashed lines are admissible assignments, and crossed dotted segments are queried pairs absent from the prediction. Choosing the shared middle representative gives 01 or 10; neither full mapping recovers both relations. The layout is schematic, and does not depict a measured image trajectory. The ordinary equally informed constrained method gives the same exclusion. Supplement S7.8 and Source Data Tables 47 and 50 identify the input and complete families.')
focus=json.loads((Q/'LINKED_FOCUSED_CONTRASTS.json').read_text(encoding='utf8'))
def forest(comp,label,stem,group):
    rows=sorted(comp['per_movie'],key=lambda r:r['film']);f,a=axes(7.8 if len(rows)==40 else 5);y=np.arange(len(rows));a.axvline(0,color='#BBBBBB',lw=.75,zorder=0)
    for i,r in enumerate(rows):
        a.plot([int(r['net_minimum']),int(r['net_maximum'])],[i-.13]*2,color='#989898',lw=1.1,solid_capstyle='butt')
        a.plot([r['linked_bounds']['net']['minimum'],r['linked_bounds']['net']['maximum']],[i+.13]*2,color=BLUE,lw=1.7,solid_capstyle='butt')
        a.plot(int(r['canonical_net']),i,'o',ms=3.5,mec=DARK,mfc='white'if r['identical_saved_graph']else DARK,zorder=5)
    a.set_yticks(y,[r['film']+(' *'if r['identical_saved_graph']else'')for r in rows]);a.invert_yaxis();a.set_xlabel('Net recovered-reference change (gains − losses)');a.set_ylabel('All common movies, fixed identifier order');a.grid(axis='y',color='#EEEEEE',lw=.45);a.legend(handles=[Line2D([0],[0],color='#989898',label='Independent attainable range'),Line2D([0],[0],color=BLUE,lw=1.7,label='Linked attainable range'),Line2D([0],[0],marker='o',color='none',mec=DARK,mfc=DARK,ms=4,label='Canonical readout')],loc='lower center',bbox_to_anchor=(.5,1.01),frameon=False,ncol=1,fontsize=8)
    f.subplots_adjust(left=.27,right=.985,bottom=.075,top=.89)
    c=comp['totals']['canonical_net'];p=comp['totals']['joint_bounds_sum_over_distinct_movies']['net'];l=comp['linked_aggregate_bounds']['net']
    threshold=comp['design'].replace('division_threshold_','').replace('_to_',' to ');threshold=threshold.replace('060','0.60').replace('078','0.78').replace('090','0.90')
    a.text(.985,.975,threshold.replace(' to ',' → ')+f"\nPooled canonical {c}\nPooled linked [{l['minimum']}, {l['maximum']}]",transform=a.transAxes,ha='right',va='top',fontsize=7.2,color=DARK)
    caption=f"Complete common-movie comparison for the division-acceptance threshold change {threshold}. Every movie is retained in identifier order. Grey intervals are scalar attainable ranges under independent reevaluation; blue intervals impose the declared identical-matching-input links. Points show canonical net changes. Asterisks and open points identify identical saved graphs. The pooled canonical net is {c}; the independent range is [{p['minimum']}, {p['maximum']}] and the linked range is [{l['minimum']}, {l['maximum']}]. These are attainable ranges, not confidence intervals. Interval endpoints for different quantities must not be combined as one joint outcome. Source Data Table 55 provides all movies and declared links."
    save(f,label,stem,caption,[str(Q/'LINKED_FOCUSED_CONTRASTS.json')],group)
forest(focus[0],'Figure 2','Figure2_complete_40_movie_contrast','main')
forest(focus[1],'Figure S4','FigureS4_threshold_078_090','supplement');forest(focus[2],'Figure S5','FigureS5_threshold_060_090','supplement')
motion=json.loads((Q/'MOTION_INTERVENTION_RESULTS.json').read_text(encoding='utf8'));rows=motion['records'];f,a=axes(3.6);a.axvline(0,color=DARK,lw=.8)
for i,r in enumerate(rows):
    gain=int(r['product']['canonical_gains']);loss=int(r['product']['canonical_losses']);a.barh(i-.16,gain,height=.29,color=BLUE);a.barh(i+.16,-loss,height=.29,color=ORANGE)
    gb=r['linked_bounds']['gains'];lb=r['linked_bounds']['losses'];a.plot([gb['minimum'],gb['maximum']],[i-.16]*2,color=DARK,lw=1.3,marker='|',markersize=5);a.plot([-lb['maximum'],-lb['minimum']],[i+.16]*2,color=DARK,lw=1.3,marker='|',markersize=5);a.text(max(gain,gb['maximum'])+.8,i-.16,str(gain),va='center',fontsize=8);a.text(-max(loss,lb['maximum'])-.8,i+.16,str(loss),va='center',ha='right',fontsize=8)
a.set_yticks(range(8),[r['film']for r in rows]);a.invert_yaxis();a.set_xlabel('Reference relations lost (left) or gained (right)');a.legend(handles=[Line2D([0],[0],color=BLUE,lw=5,label='Gained'),Line2D([0],[0],color=ORANGE,lw=5,label='Lost'),Line2D([0],[0],color=DARK,label='Linked scalar attainable range')],frameon=False,fontsize=8,loc='lower center',bbox_to_anchor=(.48,1.0),ncol=3);a.margins(x=.14);f.subplots_adjust(left=.25,right=.98,bottom=.16,top=.88)
save(f,'Figure 3','Figure3_component_intervention','Complete eight-movie intervention disabling motion replacement while replaying the remaining processing sequence from its saved raw graphs and retained image/weight context. Bars separate canonical gained and lost reference relations; black marks are their separately attainable linked-contract endpoints. All movies, including adverse and null outcomes, are retained. The intervention gains 55 relations and loses 29, giving canonical net +26 and linked attainable net [24,27]. The comparison uses the same retained raw graphs and image/weight context in both arms. Historical norm-based TP/FP results and the current calculated-distance audit are distinguished in Source Data Table 56.',[str(Q/'MOTION_INTERVENTION_RESULTS.json')])
# Actual three-dimensional source pixels with separate schematic relation lanes.
src=D/'actual_3d_case';m=json.loads((src/'SOURCE.json').read_text(encoding='utf8'))
with np.load(src/'DISPLAY_PIXELS.npz')as z:pix={k:z[k]for k in z.files}
h,w=next(iter(pix.values())).shape;step=w+22;f,a=axes(4.8);a.axis('off');lo,hi=np.quantile(np.concatenate([v.ravel()for v in pix.values()]),[.01,.99]);z0,z1,y0,y1,x0,x1=m['display_crop_zyx'];sc=np.array(m['scale_um_zyx']);reference=np.array(m['reference_um'])[:,1:]/sc
centres=[]
for i,t in enumerate(m['frames']):
    start=i*step;centres.append(start+w/2);a.imshow(pix['frame_'+str(t)],cmap='gray',vmin=lo,vmax=hi,extent=(start-.5,start+w-.5,h-.5,-.5),interpolation='nearest');a.text(start+w/2,-7,f'Frame {t}',ha='center',fontsize=10);a.scatter(start+reference[i,2]-x0,reference[i,1]-y0,marker='s',s=80,facecolors='none',edgecolors='#E69F00',lw=1.2,zorder=5)
    for view,col,marker in zip(m['views'],[BLUE,PURPLE],['x','+']):
        p=np.array(view['prediction_um'])[i,1:]/sc;a.scatter(start+p[2]-x0,p[1]-y0,marker=marker,color=col,s=65,lw=1.3,zorder=7)
    a.plot([start+2,start+12],[h+3,h+3],color=DARK,lw=1.5);a.text(start+15,h+3,'4.06 µm',fontsize=7,va='center')
    zz=[int(round(np.array(v['prediction_um'])[i,1]/sc[0]))for v in m['views']]
    a.text(start+w/2,h+11,f'z: {int(reference[i,0])}/{zz[0]}/{zz[1]} px',ha='center',fontsize=9.5)
for level,(name,col,nodes,bits)in enumerate([('Reference',DARK,['r0','r1','r2'],[1,1]),('Before',BLUE,[str(x)for x in m['views'][0]['prediction_ids']],m['views'][0]['saved_pair_exists']),('After',PURPLE,[str(x)for x in m['views'][1]['prediction_ids']],m['views'][1]['saved_pair_exists'])]):
    y=h+20+level*18;a.text(-8,y,name,ha='right',va='center',fontsize=8)
    for x,n in zip(centres,nodes):a.text(x,y,n,ha='center',va='center',color=col,fontsize=8,bbox={'facecolor':'white','edgecolor':'none','pad':1.5})
    for i,exists in enumerate(bits):
        left,right=centres[i]+10,centres[i+1]-10
        if exists:a.add_patch(FancyArrowPatch((left,y),(right,y),arrowstyle='-|>',mutation_scale=10,color=col,lw=1.2))
        else:a.plot([left,right],[y,y],color=GREY,ls=':',lw=1.1);a.text((left+right)/2,y,'×',ha='center',va='center',color=GREY,fontsize=12)
a.text((centres[0]+centres[1])/2,h+65,'0 → 1: gained',ha='center',fontsize=8,color=BLUE);a.text((centres[1]+centres[2])/2,h+65,'1 → 0: lost',ha='center',fontsize=8,color=ORANGE)
a.text((centres[0]+centres[-1])/2,h+77,'Relation lanes are schematic; image markers are recorded 3D centres.',ha='center',fontsize=7)
a.set(xlim=(-31,2*step+w+2),ylim=(h+87,-15));a.set_aspect('equal');a.legend(handles=[Line2D([0],[0],marker='s',mfc='none',mec='#E69F00',color='none',label='Reference'),Line2D([0],[0],marker='x',color=BLUE,ls='none',label='Before'),Line2D([0],[0],marker='+',color=PURPLE,ls='none',label='After')],loc='upper center',bbox_to_anchor=(.54,1.075),ncol=3,frameon=False,fontsize=8)
save(f,'Figure 4','Figure4_actual_80_movie_exchange','Actual adjacent gain and loss in the 80-movie output comparison, movie 44b6_12dfb391 at frames 22–24. Identical XY crops and the same z=42–49 slice slab are displayed as maximum projections, with shared grayscale limits. Squares locate reference centres; crosses and plus signs locate the before and after saved predictions. The z labels are source-pixel coordinates in reference/before/after order; matching uses the full three-dimensional coordinates in micrometres, not the projection. The lower lanes separately show the reference path and the actually saved canonical mapped pairs. Solid arrows denote present pairs and crossed dotted segments denote absent queried pairs; these are relation diagrams, not image-measured trajectories. The canonical visibility changes from 01 to 10. The complete 80-movie comparison retains 145 gains and 123 losses, with attainable net [12,34]. Source Data Tables 55 and 59 bind the display to its inputs.',[str(src/'SOURCE.json'),str(src/'DISPLAY_PIXELS.npz')])
# Pulse: same region, shared previous frame, two actual output-arm supports.
src=D/'bacterial_pulse';m=json.loads((src/'SOURCE.json').read_text(encoding='utf8'))
with np.load(src/'PIXELS.npz')as z:p={k:z[k]for k in z.files}
h,w=p['raw56'].shape;step=w+25;f,a=axes(5.4);a.axis('off');lo,hi=np.quantile(np.r_[p['raw56'].ravel(),p['raw57'].ravel()],[.01,.99])
for i,(title,raw,ref,preds)in enumerate([('Shared frame 56','raw56','ref56',[('parent56',BLUE)]),('WW · frame 57','raw57','ref57',[('WW57',BLUE)]),('WA · frame 57','raw57','ref57',[('WA57_66',BLUE),('WA57_67',GREEN)])]):
    start=i*step;a.imshow(p[raw],cmap='gray',vmin=lo,vmax=hi,extent=(start-.5,start+w-.5,h-.5,-.5),interpolation='nearest');a.contour(start+np.arange(w),np.arange(h),p[ref].astype(float),[.5],colors=['#E69F00'],linewidths=1.05)
    for key,col in preds:a.contour(start+np.arange(w),np.arange(h),p[key].astype(float),[.5],colors=[col],linewidths=1.0)
    a.text(start+w/2,-7,title,ha='center',fontsize=9);a.plot([start+2,start+12],[h+3,h+3],color=DARK,lw=1.5);a.text(start+16,h+3,'10 px',fontsize=7,va='center')
a.text(w/2,h+15,'Predicted parent 58',ha='center',fontsize=8);a.text(step+w/2,h+15,'58 → 58\nContinuation',ha='center',va='top',fontsize=9);a.text(2*step+w/2,h+15,'58 → 66, 67\nDivision',ha='center',va='top',fontsize=9)
a.text(step+w/2,h+37,'Local A → B → C → D',ha='center',fontsize=9,weight='bold');a.text(step+w/2,h+49,'WW / AW:  1 → 1 → 1 → 1\nWA / AA:   0 → 0 → 0 → 0',ha='center',va='top',fontsize=9)
a.set(xlim=(-10,2*step+w+10),ylim=(h+75,-17));a.set_aspect('equal');a.legend(handles=[Line2D([0],[0],color='#E69F00',label='Reference 58'),Line2D([0],[0],color=BLUE,label='Matched prediction'),Line2D([0],[0],color=GREEN,label='Other saved daughter')],loc='lower center',bbox_to_anchor=(.5,-.025),ncol=2,fontsize=8,frameon=False)
save(f,'Figure 5','Figure5_pulse_actual_support','Actual image and typed-edge evidence for one pulse-associated reference continuation in bacterial movie 21. All panels use the same crop and common display limits. The previous predicted parent support is shared by WW and WA. At frame 57, WW records continuation 58→58, while WA records division pairs 58→66 and 58→67; reference 58 matches prediction 66 in WA. Contours are derived from saved labels and type names from typed_edges. The local A–D observation is 1111 in WW/AW and 0000 in WA/AA, so this inspected window contains no new loss boundary. Acquisition time, intervention arm and processing view are distinct. The complete 29-movie result and all three lost reference relations remain in Source Data Tables 26–28; the other 28 movies have zero count effect.',[str(src/'SOURCE.json'),str(src/'PIXELS.npz')])
copy_figure('Figure4_actual_type_change','Figure 6','Figure6_support_and_relation_type','Actual support and type sequence for the mother-40 to daughter-58 relation in bacterial movie 29. Previous-D at frame 40 is the shared anchor; A–D are saved processing states of frame 41. Fixed crops, native aspect ratio and display limits retain actual pixel support. The saved raw pair 4→100004 survives, but its type changes from division to continuation, giving typed visibility 1100 while support IoU rises from 113/171 to 113/145. Type comes from saved flags, not from image appearance. The companion daughter has typed visibility 0000, so the displayed relation does not certify the complete event. Source Data Table 44 preserves separate relation, event and chain denominators.')
# Epithelial: actual two acquisition frames, before/after removal of border labels.
src=D/'epithelial_boundary';m=json.loads((src/'SOURCE.json').read_text(encoding='utf8'))
with np.load(src/'PIXELS.npz')as z:p={k:z[k]for k in z.files}
h,w=p['raw1'].shape;sx=w+23;sy=h+35;f,a=axes(5.1);a.axis('off')
for row,stage in enumerate(['S2','S3']):
    for col,t in enumerate([1,2]):
        x=col*sx;y=row*sy;a.imshow(p['raw'+str(t)],cmap='gray',vmin=0,vmax=1,extent=(x-.5,x+w-.5,y+h-.5,y-.5),interpolation='nearest');a.contour(x+np.arange(w),y+np.arange(h),p['ref'+str(t)].astype(float),[.5],colors=['#E69F00'],linewidths=1.0)
        mask=p[f'{stage}_{t}'];mask=mask if stage=='S2'else mask>0
        if np.any(mask):a.contour(x+np.arange(w),y+np.arange(h),mask.astype(float),[.5],colors=[BLUE if stage=='S2'else GREY],linewidths=.9)
        a.plot([x+w-.5]*2,[y-.5,y+h-.5],color=ORANGE,lw=1.2);a.text(x+w/2,y-8,f'E{stage[1:]}: frame {t}',ha='center',fontsize=9);a.plot([x+4,x+24],[y+h+5]*2,color=DARK,lw=1.5);a.text(x+28,y+h+5,'20 px',va='center',fontsize=7)
        a.text(x+w/2,y+h+17,('Matched label '+str([85,135][col]))if stage=='S2'else'No reference-145 match',ha='center',fontsize=8)
a.set(xlim=(-4,sx+w+5),ylim=(sy+h+39,-22));a.set_aspect('equal');a.legend(handles=[Line2D([0],[0],color='#E69F00',label='Reference 145'),Line2D([0],[0],color=BLUE,label='Matched E2 support'),Line2D([0],[0],color=GREY,label='Other retained E3 support'),Line2D([0],[0],color=ORANGE,label='Actual image boundary')],loc='lower center',bbox_to_anchor=(.5,-.07),ncol=2,frameon=False,fontsize=7.5)
save(f,'Figure 7','Figure7_epithelial_border_loss','One actual border-associated loss hidden by a zero net change in epithelial movie 3. The same two acquisition frames are shown before and after border-object removal. Backgrounds are means of the three actual channels after per-channel normalization with limits pooled over the two frames. Orange contours denote reference label 145, blue the matched E2 labels 85 and 135, and grey any other retained E3 support. The red-orange line is the actual image extent, not a relation. The saved correspondence to reference 145 is absent at E3 in both frames. This relation has history 0010. Across the complete 1,783-relation movie, four gains offset four losses while TP remains 892; Figure S1 retains all eight identities and every saved state. Source Data Tables 35 and 59 provide the complete records.',[str(src/'SOURCE.json'),str(src/'PIXELS.npz')])
copy_figure('Figure5_identity_cancellation','Figure S1','FigureS1_all_eight_exchanged_identities','All eight exchanged reference identities and their four saved-state histories in epithelial movie 3. Four gains and four losses cancel in total TP; the complete movie contains 1,783 reference relations. This complete identity display accompanies the actual-material example in Figure 7. Source Data Table 35 retains all three time series.','supplement')
copy_figure('Figure2_ordered_stage_changes','Figure S2','FigureS2_original_seven_stage_changes','Complete original eight-film changes in saved processing order. Canonical gains and losses are separate, with individually attainable product-contract extrema. Original inputs and 31-field results are preserved in Source Data Table 8; these are not the newly expanded 199-film corpus.','supplement')
copy_figure('FigureS1_epithelial_TP','Figure S3','FigureS3_complete_epithelial_TP','Complete saved-order TP counts for all three epithelial time series. These are processing stages and actual recorded values, not a fitted temporal trend. Full TP/FP, identity and exclusion records remain in Source Data Table 35.','supplement')
copy_figure('FigureS2_epithelial_FP','Figure S6','FigureS6_complete_epithelial_FP','Complete saved-order FP counts for all three epithelial time series, with the same processing stages as Figure S3. The static fourth example remains ineligible for temporal relations.','supplement')
(O/'FIGURE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print('Figures',len(manifest['main']),'+',len(manifest['supplement']))
