"""Portrait-only preparation policy and explicitly qualified feature measurements."""
import math
from pathlib import Path
import cv2
import numpy as np

from .colour_rows import unique_rows
PORTRAIT_COLOUR_DEFAULT = 10  # More room for skin highlights, midtones and shadows.
PORTRAIT_COLOUR_MAX = 12
PORTRAIT_MERGE_DELTA_E = 2.0  # Lab ΔE76; avoid merging nearby skin tones aggressively.
PORTRAIT_SMALL_CLUSTER_FRACTION = 0.0  # Never remove a colour merely because it is rare.
PORTRAIT_MIN_REGION_AREA_MM2 = 0.16  # Area screening only, not a physical sewability guarantee.
PORTRAIT_CONTOUR_SMOOTHING = 0  # Preserve the mouth/eye silhouette in preparation.
PORTRAIT_SIMPLIFY = 0
PORTRAIT_MASK_HOLES_MM2 = 0  # Do not close eye/mouth openings automatically.
PORTRAIT_FEATURE_SAMPLE_WEIGHT = 5
THREAD_WIDTH_MM = 0.4  # A conservative display/feature heuristic, not measured thread diameter.
FEATURE_READABLE_WIDTH_MM = 1.2  # Three nominal thread widths for a simple shape.
MIN_STITCH_MM = 0.3
MAX_STITCH_MM = 7.0
PHOTO_ROW_SPACING_MM = 0.4
PHOTO_BLEND_MM = 0.6
PHOTO_BLEND_MAX_MM = 1.0
PHOTO_SHORT_MM = 1.2
PHOTO_LONG_MM = 3.2
PHOTO_SEED = 1729


def proposal():
    return dict(artwork_type='portrait',count=PORTRAIT_COLOUR_DEFAULT,
                floor_mm2=PORTRAIT_MIN_REGION_AREA_MM2,smooth=PORTRAIT_CONTOUR_SMOOTHING,
                simplify=PORTRAIT_SIMPLIFY,mask_holes_mm2=PORTRAIT_MASK_HOLES_MM2,
                mask_smooth=0,fill_style='photo_stitch')


def feature_boxes(options,w,h):
    values=options.get('portrait_features',[])
    if not isinstance(values,list) or len(values)>40:raise ValueError('Use up to 40 feature boxes.')
    result=[]
    for value in values:
        if not isinstance(value,dict) or value.get('kind') not in {'mouth','eyes','teeth','detail'}:
            raise ValueError('Label a feature as mouth, eyes, teeth or detail.')
        bounds=value.get('bounds',[])
        if not isinstance(bounds,list) or len(bounds)!=4:raise ValueError('Invalid feature box.')
        if any(type(v) not in (float,int) or not math.isfinite(v) for v in bounds):raise ValueError('Invalid feature coordinates.')
        x,y,r,b=map(int,bounds)
        if not 0<=x<r<=w or not 0<=y<b<=h:raise ValueError('Feature box must be inside the image.')
        result.append(dict(kind=value['kind'],bounds=[x,y,r,b],source='user-marked area'))
    return result


def detect_portrait(image):
    """Offline face candidate detector, never an identity or landmark assertion."""
    if not hasattr(cv2,'CascadeClassifier'):
        try:
            from skimage.feature import Cascade
            import skimage.data
            detector=Cascade(skimage.data.lbp_frontal_face_cascade_filename())
            array=np.asarray(image.convert('RGB'));short=min(image.size)
            if short<32:return dict(likely=False,faces=[],method='Image too small for face candidates')
            detections=detector.detect_multi_scale(img=array,scale_factor=1.2,step_ratio=1,min_size=(32,32),max_size=(short,short),min_neighbor_number=5)
            faces=[[int(d['c']),int(d['r']),int(d['c']+d['width']),int(d['r']+d['height'])] for d in detections]
            return dict(likely=bool(faces),faces=faces,method='Local LBP face candidates; verify visually, not facial landmarks')
        except (ImportError,OSError,ValueError):
            return dict(likely=False,faces=[],method='Face detector unavailable')
    directory=getattr(getattr(cv2,'data',None),'haarcascades',None)
    filename=Path(directory)/'haarcascade_frontalface_default.xml' if directory else Path('missing')
    if not filename.is_file():filename=Path(__file__).resolve().parents[2]/'work/models/haarcascade_frontalface_default.xml'
    if not filename.is_file():return dict(likely=False,faces=[],method='Face detector unavailable')
    cascade=cv2.CascadeClassifier(str(filename))
    if cascade.empty():return dict(likely=False,faces=[],method='Face detector unavailable')
    gray=cv2.cvtColor(np.asarray(image.convert('RGB')),cv2.COLOR_RGB2GRAY)
    faces=cascade.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(30,30))
    return dict(likely=bool(len(faces)),faces=[[int(x),int(y),int(x+w),int(y+h)] for x,y,w,h in faces],
                method='OpenCV face candidates; verify visually, not facial landmarks')


def removal_records(original_labels,final_labels,palette,px_mm,height):
    """Report every original colour component changed by portrait cleanup."""
    records=[]
    for label in np.unique(original_labels[original_labels>=0]):
        n,cc,stats,_=cv2.connectedComponentsWithStats((original_labels==label).astype(np.uint8),8)
        for i in range(1,n):
            region=cc==i;changed=int(np.count_nonzero(region&(final_labels!=label)))
            if not changed:continue
            x,y,w,h,area=map(int,stats[i]);area_mm2=area*px_mm**2
            records.append(dict(colour='#%02x%02x%02x'%tuple(palette[label]),bounds=[x,y,x+w,y+h],
                area_mm2=area_mm2,width_mm=w*px_mm,height_mm=h*px_mm,changed_pixels=changed,
                action='removed' if np.all(final_labels[region]<0) else 'reassigned or partly changed',
                canvas_height_for_area_mm=round(height*math.sqrt(PORTRAIT_MIN_REGION_AREA_MM2/area_mm2),2),
                note='Unlabelled colour region; cannot identify it as a tooth or eye.'))
    return records


def feature_report(image,options,height):
    array=np.asarray(image);h,w=array.shape[:2];scale=height/h
    reports=[]
    for item in feature_boxes(options,w,h):
        x,y,r,b=item['bounds'];region=array[y:b,x:r];pixels=region[:,:,:3][region[:,:,3]>127]
        width=(r-x)*scale;short=min(r-x,b-y)*scale
        colours=len(unique_rows(pixels)) if len(pixels) else 0
        luminance=pixels@np.array([.2126,.7152,.0722]) if len(pixels) else np.array([0])
        contrast=float(luminance.max()-luminance.min())
        needed=max(height,height*FEATURE_READABLE_WIDTH_MM/max(short,1e-9))
        report={**item,'box_width_mm':round(width,2),'box_height_mm':round((b-y)*scale,2),
                'prepared_colours':colours,'luminance_range':round(contrast,2),
                'selected_pixels':len(pixels),'canvas_height_for_shape_mm':round(needed,1),
                'status':'no selected pixels' if not len(pixels) else 'below shape-width heuristic' if short<FEATURE_READABLE_WIDTH_MM else 'shape retained in prepared artwork; inspect stitch coverage',
                'note':'Measures a user-marked box, not an automatically segmented anatomical feature.'}
        if item['kind'] in {'teeth','mouth'}:
            report['alternative']='Suggest teeth as one light shape inside a dark mouth opening. Individual teeth and gaps are not detected or guaranteed; mark a specific gap to measure it.'
        reports.append(report)
    return reports
