"""Replace authoring identifiers with scientific descriptions in reader text."""
import re


def source_references(text):
    # Source-data table numbers are publication references, not experiment names.
    pat=r'\bD\d{2}(?:(?:[–/]|\s+and\s+)D\d{2})*\b'
    def sub(match):
        value=match.group()
        plural=len(re.findall(r'D\d{2}',value))>1
        values=re.sub(r'D0?(\d+)',r'\1',value)
        return 'Source Data Table'+('s ' if plural else ' ')+values
    text=re.sub(pat,sub,text)
    text=text.replace('Source Data Source Data','Source Data')
    return re.sub(r'(Source Data Table \d+) and \1\b',r'\1',text)


def main_reader_text(text):
    changes={
      'D47 supplies a real saved graph from film': 'The worked audit uses a real saved graph from film',
      'Historical SVM/SDY variants with different inputs or compound changes remain separate.':
      'Coordinate-estimation and trajectory-smoothing variants with different inputs or compound changes are analysed separately.',
      'Three fresh processes instrument the D47 task': 'Three fresh processes instrument the worked audit task',
      'In D47 the reference path is': 'In the worked audit, the reference path is',
      'for the D47 interpretation task': 'for the worked interpretation task',
      'the single development path used by D47': 'the single development path used in the worked audit',
      'The original 3D path example and D47 use different saved carriers':
      'The original 3D path example and the worked audit use different saved carriers',
      'Historical IWS/SVM/SDY records explain how these policies arose and retain failed or confounded variants; they are not pooled with common-input contrasts.':
      'Separate coordinate-estimation and trajectory-smoothing analyses retain adverse and confounded outcomes; their unmatched-input contrasts are not pooled with the common-input comparison.',
      'D47 requires a median': 'The worked audit requires a median',
      'D47 gives an end-to-end example.': 'The worked audit gives an end-to-end example.',
      'D47 repeats one development path': 'the worked audit repeats one development path',
      'Can an analyst report both neighbouring relations as simultaneously recovered? In the worked audit,':
      'The proposed statement requires both neighbouring relations to be recovered simultaneously. In the worked audit,',
      'How much of the natural evidence is affected? In the eight-film 3D cohort,':
      'The eight-film 3D cohort localizes the natural effect of correspondence alternatives. Across this cohort,',
      'Do stage histories recover the declared last-loss target, and does the protocol outperform equally informed differencing?':
      'Known-origin controls test last-loss recovery against equally informed differencing.',
      'Does a harmful final intervention imply that a saved local stage deleted the affected relations?':
      'The pulse experiment tests whether a harmful final intervention identifies a deletion inside the inspected local window.',
      'Can an apparently preserved pair establish correct typed recovery?':
      'The native-stage example tests whether preserving a raw pair establishes correct typed recovery.',
      'Can unchanged TP counts establish that an operation preserved every recovered relation?':
      'Unchanged TP counts can conceal changes in the recovered relation identities.',
      'Do the available interventions provide a general repair benefit?':
      'Complete intervention cohorts test whether the available processing changes provide a general repair benefit.',
      'What must an analyst pay to obtain the stronger report?':
      'The measured task separates the costs needed to obtain the stronger report.',
    }
    for old,new in changes.items():text=text.replace(old,new)
    return source_references(text)


def supplement_reader_text(text):
    text=text.replace(
      'Development B combines the SVM4 combination-validation graph with native coordinates/provenance from validation raw predictions. E combines the existing event-completion graph with target095 current-baseline raw native observations.',
      'Development carrier B combines the coordinate-estimation validation graph with native coordinates and provenance from its raw validation predictions. Evidence carrier E combines the event-completion graph with the corresponding baseline raw native observations.')
    paras=text.split('\n\n')
    for i,p in enumerate(paras):
        if p.startswith('Source modules event_consensus.py, affirmative_veto.py'):
            paras[i]=(
              'Sources for strict consensus, affirmative veto, coordinate blending and endpoint completion are indexed in the software provenance manifest. '
              'Separate full-pipeline coordinate-estimation and smoothing analyses use different execution boundaries. '
              'The complete estimator/variance-smoothing reconstruction gains/loses 11/9 development relations and 3/6 transfer relations on the same 16 films. '
              'Free endpoints do not move; junction coordinates change without visibility turnover. '
              'A separate trajectory-smoothing analysis retains five arms in four films, with all 20 recounts matching. '
              'Smoothing the pooled-coordinate graph without changing its topology gains/loses 12/10 relations, including an adverse 3/6 case and null films. '
              'The unpooled-coordinate comparison changes topology and omits cache-dependent supplementation, so it cannot isolate smoothing. '
              'All four learned-coordinate prediction folds underperform the community baseline in displacement; training was not rerun. '
              'These negative and confounded observations remain separate from the matched-input intervention comparison. '
              'Internal branch names and original source paths are retained in the author provenance record.')
    text='\n\n'.join(paras)
    text=text.replace('actual D47 case','actual shared-map audit case')
    text=text.replace("D47's raw saved common-carrier graph", "the worked audit's saved common-carrier graph")
    text=text.replace("D47's two authorized NPZ inputs", 'the worked audit\'s two authorized NPZ inputs')
    text=text.replace('D47 supplies the retrospectively selected common-carrier example;',
                      'The worked audit uses the retrospectively selected common-carrier example;')
    text=text.replace('These are the original seven-stage shared-middle coordinates at zero-based index 7; they are a different saved context from the D47 adoption graph in main Figure 1.',
                      'These are the original seven-stage shared-middle coordinates at zero-based index 7; they are a different saved context from the worked audit in main Figure 1.')
    text=text.replace('The main image display uses prediction-mask centroids, not GT tracks.',
                      'The main figure shows actual saved prediction pairs and types in a schematic layout, without a raw-intensity background.')
    text=text.replace('Ω=∏_s F_s', r'$\Omega=\prod_s{F_s}$')
    text=source_references(text)
    for old,new in {
      'Instrumented Source Data Table 47 costs in milliseconds':'Instrumented costs of the worked audit in milliseconds',
      'Concrete Source Data Table 47 report fields':'Concrete fields returned by the worked audit',
      'The Source Data Table 47 constructor instrument':'The worked-audit constructor instrument',
      'Source Data Table 47 instrumented constructor and literal comparison':'Worked audit: instrumented constructor and literal comparison',
      'Source Data Table 47’s two authorized NPZ inputs':'the worked audit’s two authorized NPZ inputs',
      'Its scientific REPORT.json equals Source Data Table 47;':'Its scientific REPORT.json matches the retained worked-audit record (Source Data Table 47);',
      'authorized Source Data Table 47 inputs':'authorized inputs for the worked audit',
    }.items():text=text.replace(old,new)
    return text
