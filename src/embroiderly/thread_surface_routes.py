"""Bounded CPU mockups from existing PES files. No generation or export mutation."""
from io import BytesIO
from pathlib import Path
from hashlib import sha256
import json
from threading import BoundedSemaphore
from flask import request, jsonify, send_file
from .thread_surface import render_file
from .product_mockup import products, render_product


def register_thread_surface(app, root):
    gate=BoundedSemaphore(1)

    @app.get('/api/products')
    def product_list():
        return jsonify(products=products())

    @app.get('/thread-mockup/<name>')
    def thread_mockup(name):
        if Path(name).name!=name:
            return jsonify(error='Unknown design.'),404
        legacy=request.args.get('legacy','false')=='true'
        folder=root/'work'/('machine-preview' if legacy else 'inkstitch-preview')/Path(name).stem
        source=folder/('experimental.dst' if legacy else 'design.pes')
        if not source.is_file() or not (folder/'playback.json').is_file():
            return jsonify(error='Generate and export stitches before saving a mockup.'),404
        if source.stat().st_size>10_000_000:
            return jsonify(error='This export exceeds the bounded mockup size.'),413
        if not gate.acquire(blocking=False):
            return jsonify(error='Another mockup is rendering. Please retry shortly.'),429
        try:
            if request.args.get('neutral','false') not in ('true','false'):
                raise ValueError('Neutral light must be true or false.')
            digest=sha256(source.read_bytes()).hexdigest()
            palette=None
            if legacy:
                metadata=json.loads((folder/'playback.json').read_text())
                if metadata.get('source_sha256')!=digest:
                    raise ValueError('The DST palette is not bound to this export. Regenerate it before previewing.')
                palette=metadata.get('colors')
            look=dict(palette=palette,width=int(request.args.get('width',960)),height=int(request.args.get('height',720)),
                strand=float(request.args.get('strand',.375)),texture=request.args.get('texture','twill'),
                angle=float(request.args.get('angle',225)),neutral=request.args.get('neutral','false')=='true')
            note=None
            if request.args.get('product'):
                image,note=render_product(source,request.args['product'],request.args.get('placement',''),
                    request.args.get('fabric','#c2baa8'),**look)
            else:
                image=render_file(source,fabric=request.args.get('fabric','#c2baa8'),**look)
            if digest!=sha256(source.read_bytes()).hexdigest():
                return jsonify(error='The exported file changed during rendering. Please retry.'),409
            output=BytesIO();image.save(output,format='PNG');output.seek(0)
            response=send_file(output,mimetype='image/png',as_attachment=request.args.get('download','true')!='false',download_name='embroiderly-thread-mockup.png')
            response.headers['X-Export-SHA256']=digest
            if note: response.headers['X-Mockup-Note']=note
            response.headers['Cache-Control']='no-store'
            return response
        except (ValueError,TypeError,OverflowError) as error:
            return jsonify(error=str(error)),400
        except (OSError,IndexError) as error:
            app.logger.warning('Written stitch file could not be rendered: %s',type(error).__name__)
            return jsonify(error='The written stitch file could not be read. Regenerate it and retry.'),422
        finally:
            gate.release()
