"""Single scientific figures from saved identities, masks and measurements."""
from pathlib import Path
import csv, gzip, io, json, re, zipfile
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle
from matplotlib.colors import ListedColormap
from reader_wording import main_reader_text

import argparse
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--input-root',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();I=args.input_root.resolve();O=args.output.resolve()
O.mkdir(parents=True,exist_ok=False);S=O/'source_data';S.mkdir()
BLUE='#0072B2'; ORANGE='#D55E00'; GREY='#777777'; DARK='#242424'
plt.rcParams.update({'font.family':'Arial','font.size':9,'axes.labelsize':10,
 'axes.linewidth':.7,'xtick.labelsize':9,'ytick.labelsize':9,'pdf.fonttype':42,
 'ps.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})
SD=(I/'source_data.md').read_text(encoding='utf-8')
manifest={'main':[],'supplement':[],'scientific_execution':'Saved-record extraction and display only',
          'width_mm':165,'generated_experimental_images':False,'source_records':{}}

def table(code):
    heading=r'(?:'+code+r'\b|Data table '+str(int(code[1:]))+r'\b)'
    section=re.search(r'^## '+heading+r'.*?(?=^## |\Z)',SD,re.M|re.S).group(0)
    rows=[[c.strip() for c in line.strip('|').split('|')] for line in section.splitlines() if line.startswith('|')]
    return [row for row in rows if not all(re.fullmatch(r':?-+:?',c) for c in row)]

def axis(height=3.6):
    f,a=plt.subplots(figsize=(165/25.4,height),layout='constrained')
    a.spines[['top','right']].set_visible(False)
    return f,a

def save(f,label,stem,caption,source_data,group='main'):
    if len(f.axes)!=1:raise ValueError('Every figure must have one axes')
    caption=main_reader_text(caption)
    for ext in ('png','pdf','svg'):f.savefig(O/(stem+'.'+ext),dpi=450)
    manifest[group].append({'label':label,'stem':stem,'path':str(O/(stem+'.png')),
        'pdf':str(O/(stem+'.pdf')),'svg':str(O/(stem+'.svg')),'width_mm':165,
        'caption':caption,'single_axes':True,'source_data':source_data})
    plt.close(f)

# Complete candidate topology of the actual D47 query, not a centroid-only sketch.
task=json.loads((I/'worked_audit_report.json').read_text(encoding='utf-8'))
with np.load(I/'worked_audit_prediction.npz',allow_pickle=False) as z:
    pred_pairs=set(map(tuple,z['edges'].tolist()))
paths=[row['mapped_path'] for row in task['complete_joint_truth_table']]
queried=[(paths[0][0],paths[0][1]),(paths[0][1],paths[0][2]),
         (paths[1][0],paths[1][1]),(paths[1][1],paths[1][2])]
present=[pair in pred_pairs for pair in queried]
if present!=[False,True,True,False]:raise ValueError('D47 saved edges contradict the report')
f,a=axis(3.9);a.set(xlim=(-.7,3.7),ylim=(-1.7,2.7));a.axis('off')
ref=[(0,2),(1.5,2),(3,2)];p={23499:(0,0),23977:(1.5,.55),24012:(1.5,-.65),24483:(3,0)}
for x in ref:a.scatter(*x,s=440,marker='s',c='white',edgecolors=DARK,linewidths=1.1,zorder=4)
for k,(x,y) in enumerate(ref):
    a.text(x,y,f'r{k}',ha='center',va='center',weight='bold',zorder=8)
    a.text(x,2.48,f'Frame {50+k}',ha='center',fontsize=9)
for left,right in zip(ref,ref[1:]):a.add_patch(FancyArrowPatch(left,right,arrowstyle='-|>',mutation_scale=12,shrinkA=16,shrinkB=16,color=DARK,lw=1.4))
for rid,pid in [(0,23499),(1,23977),(1,24012),(2,24483)]:
    a.plot([ref[rid][0],p[pid][0]],[ref[rid][1]-.17,p[pid][1]+.15],ls=(0,(3,3)),c=GREY,lw=.8,zorder=1)
for pid,(x,y) in p.items():
    a.scatter(x,y,s=820,c='white',edgecolors=BLUE,linewidths=1.5,zorder=5)
    a.text(x,y,str(pid),ha='center',va='center',fontsize=8,zorder=6)
for pair,exists in zip(queried,present):
    left,right=p[pair[0]],p[pair[1]]
    a.add_patch(FancyArrowPatch(left,right,arrowstyle='-|>' if exists else '-',mutation_scale=12,
         shrinkA=19,shrinkB=19,color=BLUE if exists else ORANGE,lw=1.8 if exists else 1.1,
         linestyle='-' if exists else (0,(2,2))))
    if not exists:
        x,y=(np.array(left)+np.array(right))/2
        a.text(x,y,'×',ha='center',va='center',fontsize=17,color=ORANGE,
               bbox={'facecolor':'white','edgecolor':'none','pad':0})
a.text(1.8,1.22,'Choose one shared\nmiddle-node match',ha='left',fontsize=9,color=DARK)
a.text(-.5,1.0,'Reference\nrelations',fontsize=9,color=DARK)
a.text(-.52,-.92,'Saved prediction\nrelations',fontsize=9,color=BLUE)
a.text(2.0,.56,'Map α: 0, 1',fontsize=9,color=DARK)
a.text(2.0,-.66,'Map β: 1, 0',fontsize=9,color=DARK)
a.text(1.5,-1.38,'Both complete maps give joint recovery 0',ha='center',weight='bold',fontsize=10)
a.legend(handles=[Line2D([0],[0],c=BLUE,lw=1.8,label='Present prediction pair'),
 Line2D([0],[0],c=ORANGE,ls=':',label='Absent queried pair')],loc='lower left',bbox_to_anchor=(.01,-.07),ncol=2,fontsize=8,frameon=False)
save(f,'Figure 1','Figure1_shared_correspondence',
 'Complete candidate topology for the D47 interpretation task. Black arrows are the two reference relations; grey dashed lines are reference-to-prediction assignments. Blue arrows are actual saved prediction pairs. Orange crossed dotted segments mark queried pairs absent from the saved prediction, not predicted edges. The middle reference node must select prediction 23977 or 24012 once for both incident relations. Their recovery vectors are 01 and 10, so neither complete map recovers both. Layout is schematic; IDs, pairs and frame indices are recorded data. D47/D50 and Supplement S7.8 give the full reference IDs and contract.', ['D47','D50'])
manifest['source_records']['D47_pairs']={'pairs':queried,'present':present,'truth':task['complete_joint_truth_table']}

# Ordered processing boundaries, retaining gains and losses rather than their net.
rows={row[0]:row for row in table('D08')[1:]}
gains=[];losses=[];bounds=[]
for k in range(1,7):
    g=rows[f'Gain S{k-1}→S{k}'];l=rows[f'Loss S{k-1}→S{k}']
    gains.append(int(g[2]));losses.append(int(l[2]));bounds.append([list(map(int,g[3].split('–'))),list(map(int,l[3].split('–')))])
f,a=axis(3.65);x=np.arange(6)
a.bar(x-.18,gains,.32,color=BLUE,label='Gained visibility')
a.bar(x+.18,-np.array(losses),.32,color=ORANGE,label='Lost visibility')
for k,(g,l,lim) in enumerate(zip(gains,losses,bounds)):
    a.plot([k-.18]*2,lim[0],c=DARK,lw=1.1);a.plot([k+.18]*2,[-lim[1][1],-lim[1][0]],c=DARK,lw=1.1)
    a.text(k-.18,max(lim[0])+1.4,str(g),ha='center',va='bottom',fontsize=8)
    a.text(k+.18,-max(lim[1])-1.4,str(l),ha='center',va='top',fontsize=8)
a.axhline(0,c=DARK,lw=.7)
a.set(xticks=x,xticklabels=[f'S{k-1}→S{k}' for k in range(1,7)],ylim=(-61,46),
      xlabel='Processing boundary in saved order',ylabel='Reference relations gained (+) or lost (−)')
a.legend(frameon=False,ncol=2,loc='upper left',fontsize=8)
a.text(5,38,'S5→S6: fixed IDs/pairs,\nfitted coordinates',ha='right',fontsize=8)
save(f,'Figure 2','Figure2_ordered_stage_changes',
 'Visibility changes in saved processing order for all eight original 3D films. Bars are canonical gains and losses, reported separately; black intervals show separately attainable minima and maxima under complete per-view-product correspondences. These are finite admissibility ranges, not confidence intervals, and their endpoints need not coexist. The numbers label canonical counts. Coordinate fitting at S5→S6 preserves IDs and directed pairs, so its turnover concerns reference visibility. All 31 fields and equality-linked results remain in D08.', ['D03','D08'])
manifest['source_records']['stage_changes']={'gains':gains,'losses':losses,'product_ranges':bounds}

# Saved relation comparison: retain the direct identity structure of the v1.0
# movie-21 figure, adding the actual prediction graph without an image projection.
frames=[56,57,60,61,62];edge_source={}
for arm in ('WW','WA'):
    path=I/f'movie21/{arm}.npz'
    with np.load(path,allow_pickle=False) as z:
        edges=[list(map(int,e)) for e in z['typed_edges'] if int(e[0]) in frames and int(e[2]) in frames]
        for frame,ident in ([(56,58),(57,58),(60,67),(61,67),(62,67)] if arm=='WW'
                            else [(56,58),(57,66),(60,69),(61,67),(62,69)]):
            if not np.any(z[f'frame_{frame:04}']==ident):raise ValueError('Saved prediction endpoint absent')
    edge_source[arm]=edges
selected_WW=[[56,58,57,58,0],[60,67,61,67,0],[61,67,62,67,0]]
changed=[56,58,57,66,1]
absent_WA=[[60,69,61,67],[61,67,62,69]]
for e in selected_WW:
    if e not in edge_source['WW']:raise ValueError('Expected actual WW relation absent')
if changed not in edge_source['WA']:raise ValueError('Saved WA type change absent')
for e in absent_WA:
    if any(row[:4]==e for row in edge_source['WA']):raise ValueError('Queried absent WA pair is present')
f,a=axis(4.0);a.set(xlim=(-2.0,6.1),ylim=(-1.5,3.9));a.axis('off')
x=[0,1.35,2.95,4.30,5.65];edge_indices=[(0,1),(2,3),(3,4)]
a.text(-1.95,3.65,'Movie 21 · pulse at frame 56',weight='bold',fontsize=10)
for pos,frame in zip(x,frames):a.text(pos,3.20,f'Frame {frame}',ha='center',fontsize=9)
for y,ids,label,col,marker in [(2.45,[58,58,63,63,63],'Reference\ncontinuations',DARK,'s'),
                              (1.20,[58,58,67,67,67],'WW prediction',BLUE,'o'),
                              (-.05,[58,66,69,67,69],'WA prediction',ORANGE,'o')]:
    a.text(-1.95,y,label,va='center',color=col,fontsize=9)
    for pos,ident in zip(x,ids):
        a.scatter(pos,y,s=510,marker=marker,c='white',edgecolors=col,linewidths=1.3,zorder=4)
        a.text(pos,y,str(ident),ha='center',va='center',fontsize=10,zorder=5)
    for k,(i,j) in enumerate(edge_indices):
        exists=(y>=1 or k==0)
        a.add_patch(FancyArrowPatch((x[i],y),(x[j],y),arrowstyle='-|>' if exists else '-',
            mutation_scale=12,shrinkA=17,shrinkB=17,color=col,lw=1.7,
            linestyle='-' if exists else (0,(2,2))))
        if y<1:
            a.text((x[i]+x[j])/2,y+.32,'Division' if exists else 'No saved pair',
                   ha='center',fontsize=8,color=col)
            if not exists:a.text((x[i]+x[j])/2,y,'×',ha='center',va='center',fontsize=16,color=col,
                                bbox={'facecolor':'white','edgecolor':'none','pad':0})
        elif y<2:a.text((x[i]+x[j])/2,y+.32,'Continuation',ha='center',fontsize=8,color=col)
a.text(-1.95,-.78,'Local typed history (A→B→C→D):',fontsize=9)
a.text(1.50,-.78,'WW / AW: 1111',fontsize=9,color=BLUE,weight='bold')
a.text(4.00,-.78,'WA / AA: 0000',fontsize=9,color=ORANGE,weight='bold')
a.text(-1.95,-1.25,'All three final losses were already absent at local view A.',fontsize=9)
save(f,'Figure 3','Figure3_actual_prediction_relations',
 'Actual saved prediction pairs corresponding to all three pulse-associated reference losses in movie 21. Nodes carry frame-local object IDs. Solid arrows are saved relations; crossed dotted segments are queried endpoint pairs with no saved edge. WW retains all three continuations. WA changes the first to division 58→66 and contains neither of the other two queried pairs. The full reference identities and matched prediction endpoints are given in Table S14. All three relations are typed-visible throughout the inspected A–D window in WW/AW and absent throughout in WA/AA; the final intervention difference therefore provides no local observed-loss boundary. Node placement is schematic, with acquisition frames and actual relation identities retained; no raw-image background or interpolated trajectory is used.', ['D26','D28'])
manifest['source_records']['movie21']={'frames':frames,'WW_selected_edges':selected_WW,'WA_type_changed_edge':changed,
 'WA_absent_queried_pairs':absent_WA,'saved_edges_in_selected_frames':edge_source,
 'background_projection':None,'design_source':'v1.0 direct identity comparison, redrawn with actual saved prediction relations'}

# Redraw the effective v1.0 native-pixel sequence. This is one continuous
# single-axes comparison of the same relation, preserving the previous anchor
# and all saved A-D supports rather than superimposing their different shapes.
pixel_dir=I/'type_change'
meta=json.loads((pixel_dir/'EXAMPLE.json').read_text(encoding='utf-8'))
with np.load(pixel_dir/'SOURCE_PIXELS.npz',allow_pickle=False) as z:pix={k:z[k] for k in z.files}
y0,y1,x0,x1=meta['crop_yx'];h=y1-y0;w=x1-x0
lo,hi=np.quantile(np.r_[pix['raw_previous'].ravel(),pix['raw_current'].ravel()],[.01,.99])
f,a=axis(3.7);step=39;starts=np.arange(5)*step
for n,(start,key) in enumerate(zip(starts,['previous_prediction','A','B','C','D'])):
    previous=n==0;raw=pix['raw_previous' if previous else 'raw_current'][y0:y1,x0:x1]
    a.imshow(raw,cmap='gray',vmin=lo,vmax=hi,extent=(start-.5,start+w-.5,h-.5,-.5),interpolation='nearest')
    reference=pix['previous_reference' if previous else 'current_reference'][y0:y1,x0:x1]
    prediction=pix[key][y0:y1,x0:x1]
    a.contour(start+np.arange(w),np.arange(h),reference.astype(float),[.5],colors=[ORANGE],linewidths=1.2)
    a.contour(start+np.arange(w),np.arange(h),prediction.astype(float),[.5],colors=[BLUE],linewidths=1.2)
    a.text(start+w/2,-7,'Previous D' if previous else key,ha='center',weight='bold',fontsize=10)
    a.text(start+w/2,-2.4,'Frame 40' if previous else 'Frame 41',ha='center',fontsize=8)
    a.plot([start+2,start+12],[h+2,h+2],c='black',lw=1.8)
    a.text(start+14,h+2,'10 px',va='center',fontsize=7.5)
    kind='Mother 40\nshared anchor' if previous else ('Division\ntyped visible 1' if n<3 else 'Continuation\ntyped visible 0')
    a.text(start+w/2,h+8,kind,ha='center',va='top',fontsize=8)
    if n:
        a.text(start+w/2,h+20,'IoU '+('113/171' if n<3 else '113/145'),ha='center',fontsize=7.5)
        if n<4:a.annotate('',(start+step-1,-9.5),(start+w+1,-9.5),arrowprops={'arrowstyle':'->','lw':.8,'color':DARK})
a.axvline((starts[0]+w+starts[1])/2,ymin=.28,ymax=.9,c='#BBBBBB',lw=.6)
a.text((starts[1]+starts[-1]+w)/2,-14,'Saved processing order at the same acquisition frame',ha='center',fontsize=9)
a.text((starts[-1]+w)/2,h+29,'Same saved pair 4→100004 · raw 1111 · typed 1100',ha='center',fontsize=9,weight='bold')
a.set(xlim=(-2,starts[-1]+w+2),ylim=(h+43,-19));a.set_aspect('equal');a.axis('off')
a.legend(handles=[Line2D([0],[0],c=ORANGE,label='Reference boundary'),Line2D([0],[0],c=BLUE,label='Matched prediction support')],
         frameon=False,loc='lower center',ncol=2,fontsize=8)
save(f,'Figure 4','Figure4_actual_type_change',
 'Actual support and type sequence for one mother-to-daughter relation in movie 29. The frame-40 previous-D mother is the shared anchor; A–D show the same frame-41 daughter in saved processing order: resized probability support, winner-threshold support, component-selected support and retained return rows. Every image uses the same spatial crop, native aspect ratio and common intensity display range. Orange contours are reference supports and blue contours are the actual saved prediction supports. A/B retain division membership; C/D carry continuation flags. Thus the same raw pair survives while typed visibility becomes 1100, even though current-support IoU rises from 113/171 to 113/145. Type labels are read from saved graph/flag records, not inferred from pixels. The reference is mother 40 to daughter 58; the companion daughter is not recovered, so this is not a complete-event certificate. Scale bars are 10 native pixels. Supplement S4.4/S5 retain the complete event and relation crosswalk.', ['D44'])
manifest['source_records']['type_example']={'source':str(pixel_dir/'SOURCE_PIXELS.npz'),'metadata':meta,'display_crop':meta['crop_yx'],
 'design_source':'v1.0 native-pixel sequence redrawn from original arrays','shared_display_limits':[float(lo),float(hi)]}

# Full identity turnover behind count cancellation, without a spurious TP-FP path.
epi=json.loads((I/'movie3_complete_result.json').read_text(encoding='utf8'))
changed_edges=[e for e in epi['edge_records'] if e['history'][2]!=e['history'][3]]
changed_edges.sort(key=lambda e:(e['history'][2]=='1',e['id']))
if len(changed_edges)!=8 or sum(e['history'][2:]=='01' for e in changed_edges)!=4:raise ValueError('Epithelial turnover is not four/four')
matrix=np.array([[int(v) for v in e['history']] for e in changed_edges])
f,a=axis(3.6);a.imshow(matrix,cmap=ListedColormap(['#E9E9E9',BLUE]),vmin=0,vmax=1,aspect='auto',interpolation='nearest')
for row in range(8):
    for col in range(4):a.text(col,row,str(matrix[row,col]),ha='center',va='center',color='white' if matrix[row,col] else DARK,fontsize=10)
labels=[f"{e['nodes'][0][0]}:{e['nodes'][0][1]} → {e['nodes'][1][0]}:{e['nodes'][1][1]}" for e in changed_edges]
a.set(xticks=range(4),xticklabels=['E0\nInteriors','E1\nSmall-object\nremoval','E2\nWatershed','E3\nBorder removal'],
 yticks=range(8),yticklabels=labels,xlim=(-.5,5.1),ylim=(8.5,-.6),ylabel='Reference relation (frame:label → frame:label)')
a.text(3.65,1.5,'4 gained',color=BLUE,fontsize=10,weight='bold')
a.text(3.65,5.5,'4 lost',color=ORANGE,fontsize=10,weight='bold')
a.text(3.65,7.5,'ΔTP = 0',fontsize=10,weight='bold')
a.text(3.65,8.12,'Full-movie TP',fontsize=8)
for col,stage in enumerate(epi['stages']):a.text(col,8.12,str(stage['reference_edge_TP']),ha='center',fontsize=9)
for spine in a.spines.values():spine.set_visible(False)
save(f,'Figure 5','Figure5_identity_cancellation',
 'All eight reference identities exchanged by epithelial movie 3 at E2→E3. Each row is an actual reference relation, labelled by acquisition frame and curated label. One means recovered under the checked correspondence; zero means absent. All four saved processing views are shown. Four gains and four losses leave full-movie TP unchanged at 892; the remaining 1,775 relations are omitted from this explanatory display but retained in the complete 1,783-relation record. D35 contains all three time series, exclusions, TP/FP and boundary counts. The display establishes identity cancellation, not eight independent biological replicates.', ['D35'])
(S/'epithelial_changed_identities.json').write_text(json.dumps(changed_edges,ensure_ascii=False,indent=2),encoding='utf-8')
manifest['source_records']['epithelial_turnover']={'records':changed_edges,'complete_reference_relations':epi['reference_edges'],'stage_counts':epi['stages']}

# Two independent saved-order plots preserve all three external time series.
epir=table('D35')[1:4]
for which,label in [(0,'Figure S1'),(1,'Figure S2')]:
    f,a=axis(3.3)
    for row,col,marker in zip(epir,[BLUE,ORANGE,GREY],['o','^','s']):
        vals=[list(map(int,pair.strip().split('/')))[which] for pair in row[3].split(';')]
        a.plot(range(4),vals,marker=marker,c=col,lw=1.4,mfc='white',label=f'{row[0]} ({row[1]} frames)')
        for x,y in enumerate(vals):
            offset=(7 if row[0]!='movie2' else -13) if which==0 else (-13 if row[0]=='movie3' else 7)
            shifted = which==1 and row[0]=='movie1' and x==1
            a.annotate(str(y),(x,y),xytext=(-9,10) if shifted else (0,offset),textcoords='offset points',ha='right' if shifted else 'center',va='center' if shifted else 'baseline',fontsize=8,color=col)
    a.set(xticks=range(4),xticklabels=['E0\nInteriors','E1\nSmall-object removal','E2\nWatershed','E3\nBorder removal'],
          xlabel='Saved processing view',ylabel='True-positive relations' if which==0 else 'False-positive relations')
    a.margins(y=.18);a.legend(frameon=False,fontsize=8)
    save(f,label,f'FigureS{which+1}_epithelial_{"TP" if which==0 else "FP"}',
         f'Complete saved-order {"TP" if which==0 else "FP"} counts for the three epithelial time series. Lines follow E0→E3 processing order; no interpolation, smoothing or parameter-scale law is fitted. The static fourth example is ineligible for temporal relations. Exact values and all gains/losses are in D35.', ['D35'],'supplement')

(O/'FIGURE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'main_figures':len(manifest['main']),'supplement_figures':len(manifest['supplement']),
                  'single_axes_all':all(e['single_axes'] for e in manifest['main']+manifest['supplement'])}))
