"""Pure read-only advisors: no filesystem, networking, planner or editor imports.

Inputs are ordinary data snapshots. Results describe evidence and capability gaps;
they cannot call a design operation. Persistence and optional vision live elsewhere.
"""
import math


def lookup(knowledge, table, ident):
    book = knowledge[table]
    row = next((r for r in book['rows'] if r['id'] == ident), None)
    if row is None:
        raise ValueError('No matching knowledge row; no measurement will be invented.')
    citation = {'table':table,'row_id':ident,'version':book['version'],
                'sha256':book['sha256'],'source_note':row['source_note'],
                'verified_by_user':row['verified_by_user'],'seed_data':book['seed_data'],
                'previous_value':row.get('previous_value'),
                'unconfirmed_seed_difference':bool(row.get('proposed_seed_value') and not row['proposed_seed_value'].get('confirmed_by_user'))}
    return row,citation


def advise_placement(garment, position, knowledge):
    for row in knowledge['placements.json']['rows']:
        if row['garment'] == garment and row['position'] == position:
            value,citation = lookup(knowledge,'placements.json',row['id'])
            return {'advisory_only':True,'placement':dict(value),'citations':[citation],'operations':[]}
    return {'advisory_only':True,'message':'No placement row exists for this garment and position. Ask for the shop specification.','citations':[],'operations':[]}


def advise_backing(fabric, density, garment, knowledge):
    rows=[]
    for row in knowledge['backing.json']['rows']:
        if fabric in row['fabric'] and row['density'] in (density,'unspecified'):
            value,citation=lookup(knowledge,'backing.json',row['id'])
            rows.append({'recommendation':dict(value),'citation':citation})
    return {'advisory_only':True,'recommendations':rows,'operations':[],
            'message':'Unverified seed guidance; confirm with your shop.' if rows else 'No verified backing recommendation exists for these inputs.'}


def check_lettering(cap_height_mm, stitch_type, fabric, knowledge):
    if type(cap_height_mm) not in (int,float) or not math.isfinite(cap_height_mm) or cap_height_mm <= 0:
        raise ValueError('A positive measured cap height is required.')
    choices=[r for r in knowledge['lettering.json']['rows'] if r['stitch_type']==stitch_type and r['fabric'] in (fabric,'unspecified')]
    if not choices:
        return {'advisory_only':True,'message':'No lettering threshold is available for these inputs.','operations':[]}
    row,citation=lookup(knowledge,'lettering.json',choices[0]['id'])
    minimum=row['minimum_cap_height_mm']
    small=cap_height_mm<minimum
    return {'advisory_only':True,'measured_cap_height_mm':cap_height_mm,'minimum_cap_height_mm':minimum,
            'below_seed_minimum':small,'scale_factor':minimum/cap_height_mm if small else 1,
            'options':['Enlarge proportionally to the stated cap height, then re-digitize.',
                       'Explicitly remove this text line after reviewing it.',
                       'Rebuild as single running-stitch lettering if that capability is added.'] if small else [],
            'capability_gaps':['Font-based satin lettering and single-line font reconstruction are not implemented.'],
            'citations':[citation],'operations':[]}


def advise_sewout(observation, design, knowledge):
    """Reason about bounded visual observations, not remembered embroidery facts."""
    limits,limit_citation=lookup(knowledge,'sewout.json','photo.limits')
    if not isinstance(observation,dict) or set(observation)!={'quality','findings'}:
        raise ValueError('Invalid photographic observation.')
    if observation['quality'] not in {'usable','uncertain','poor'} or not isinstance(observation['findings'],list) or len(observation['findings'])>6:
        raise ValueError('Invalid photo quality or finding count.')
    result={'advisory_only':True,'operations':[],'patch':{},'findings':[],
            'quality':observation['quality'],'citations':[limit_citation],
            'limitations':list(limits['not_measurable']),'capture_guidance':limits['capture'],
            'design_comparison':dict(design),
            'comparison_limit':'The photo is not registered to stitch objects. Regional density and physical gap sizes are not measured.'}
    seen=set()
    for finding in observation['findings']:
        if not isinstance(finding,dict) or set(finding)!={'issue_id','box'} or finding['issue_id']=='photo.limits':
            raise ValueError('Unsupported visual finding.')
        row,citation=lookup(knowledge,'sewout.json',finding['issue_id'])
        box=finding['box']
        if not isinstance(box,list) or len(box)!=4 or any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=1 for n in box) or box[0]>=box[2] or box[1]>=box[3]:
            raise ValueError('Finding must locate a visible area in the photo.')
        if row['id'] in seen: raise ValueError('Duplicate visual finding.')
        seen.add(row['id'])
        if observation['quality']!='usable':continue
        result['findings'].append({'issue_id':row['id'],'visible_observation':row['label'],
            'photo_box':list(box),'possible_causes':list(row['possible_causes']),
            'remedy':row['remedy'],'setting':row['setting'],'adjustment':row['adjustment'],
            'capability_gap':row['capability_gap'],'citation':citation})
    result['message']=('Photo quality is insufficient for a reliable review. Retake it before changing the design.'
        if observation['quality']!='usable' else
        'Possible visible symptoms found. Causes are hypotheses; confirm them with a controlled sample.'
        if result['findings'] else 'No listed visible defects were reported. This is not proof of a fault-free sew-out.')
    return result
