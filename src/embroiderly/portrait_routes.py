"""Portrait proposals and measured details, without changing saved artwork."""
from pathlib import Path
import cv2
from .portrait import proposal,detect_portrait
from .preparation import load_image,prepare,data_url


def register_portrait(app,root):
    from flask import request,jsonify,abort
    @app.post('/portrait/<name>')
    def portrait_proposal(name):
        path=root/'work'/'uploads'/Path(name).name
        if not path.is_file():abort(404)
        body=request.get_json(silent=True)
        if not isinstance(body,dict) or not isinstance(body.get('options'),dict):return jsonify(error='Expected artwork settings.'),400
        try:
            image=load_image(path);detected=detect_portrait(image)
            if body.get('action')=='detect':return jsonify(detected)
            if body.get('action')!='propose':raise ValueError('Choose portrait detection or proposal.')
            patch=proposal();patch['count']=max(patch['count'],len(body['options'].get('locks',[])))
            candidate={**body['options'],**patch}
            prepared,palette,report=prepare(path,candidate,root/'work'/'decisions'/(path.name+'.masks'))
            return jsonify(patch=patch,image=data_url(prepared),palette=palette,report=report,detection=detected)
        except (ValueError,TypeError,KeyError,cv2.error,OSError) as error:return jsonify(error=str(error)),400
