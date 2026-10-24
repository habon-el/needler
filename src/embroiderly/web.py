"""Local interactive review workspace; it consumes structured pipeline data."""

from __future__ import annotations
from .knowledge_messages import message as knowledge_message

from dataclasses import asdict
import json
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for
from PIL import Image, ImageDraw, ImageChops
import numpy as np

from .demo import sample_design
from .export import export_design
from .regions import analyze_image, recommend
from .simulation import audit_preview_coverage, create_preview
from .playback import build_playback
from .simulation import PreviewSegment
import math


def create_app(workspace: Path | None = None) -> Flask:
    root = workspace or Path.cwd()
    uploads = root / "work" / "uploads"
    decisions = root / "work" / "decisions"
    exports = root / "outputs"
    uploads.mkdir(parents=True, exist_ok=True)
    decisions.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["EMBROIDERLY_WORKSPACE"] = str(root)
    from .preferences import register_preferences
    register_preferences(app, root)
    from .library import register_library
    register_library(app, root)
    from .preparation import register_preparation
    register_preparation(app, root)
    from .lettering import register_lettering
    register_lettering(app, root)
    from .piece_guards import register as register_piece_guards
    register_piece_guards(app, root)
    from .size_sets import register_size_sets
    register_size_sets(app, root)
    from .auto_digitize import register_auto_digitize
    register_auto_digitize(app, root)

    @app.get('/api/fabrics')
    def fabrics():
        # Fabric presets for the fabric menu (generation_policy).
        from .generation_policy import presets, DEFAULT
        return jsonify(default=DEFAULT, fabrics=[dict(id=r['fabric'], label=r.get('label', r['fabric']),
                                                      stabilizer=r.get('stabilizer', ''), backing=r.get('backing'),
                                                      topping=r.get('topping')) for r in presets()])
    from .assistance import register_assistance
    register_assistance(app, root)
    from .ai_draft import register_ai_draft
    register_ai_draft(app, root)
    from .ai_workflow import register_ai_workflow
    register_ai_workflow(app, root)
    from .portrait_routes import register_portrait
    from .sewout_review import register_sewout_review
    register_sewout_review(app, root)
    register_portrait(app, root)
    from .thread_variants import register_thread_variants
    register_thread_variants(app, root)
    from .thread_surface_routes import register_thread_surface
    register_thread_surface(app, root)
    app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

    @app.route('/colours/<name>', methods=['GET', 'POST'])
    def colours(name):
        path = uploads / Path(name).name
        if not path.is_file():
            abort(404)
        analysis = analyze_image(path)
        target = decisions / (path.name + '.colours.json')
        palette = ['#%02x%02x%02x' % rgb for rgb in analysis.palette]
        if request.method == 'POST':
            values = request.get_json()
            try:
                assert set(values) == set(palette)
                for item in values.values():
                    assert type(item['include']) is bool
                    assert len(item['thread']) == 7 and item['thread'][0] == '#'
                    int(item['thread'][1:],16)
            except (AssertionError, TypeError, KeyError, ValueError):
                abort(400, 'Invalid colour selection')
            target.write_text(json.dumps(values,sort_keys=True))
            return jsonify(saved=True)
        values = json.loads(target.read_text()) if target.exists() else {c:{'include':c!='#ffffff','thread':c} for c in palette}
        return render_template('colours.html',name=path.name,palette=palette,values=values)

    def apply_colours(path, planned):
        target = decisions / (path.name + '.colours.json')
        if not target.exists():
            return planned
        values = json.loads(target.read_text())
        return [PreviewSegment(p.points,values.get(p.colour,{}).get('thread',p.colour),p.kind)
                for p in planned if values.get(p.colour,{}).get('include',True)]

    @app.route('/editor/<name>', methods=['GET', 'POST'])
    def editor(name):
        path = uploads / Path(name).name
        if not path.is_file():
            abort(404)
        storage = decisions / (path.name + '.editor.json')
        analysis = analyze_image(path)
        if request.method == 'POST':
            data = request.get_json()
            try:
                height = float(data['height_mm'])
                assert math.isfinite(height) and 5 <= height <= 500
                assert isinstance(data['paths'], list) and len(data['paths']) <= 10000
                for p in data['paths']:
                    assert p['kind'] == 'sewn' and len(p['points']) >= 2
                    assert len(p['points']) <= 10000
                    assert len(p['colour']) == 7 and p['colour'][0] == '#'
                    int(p['colour'][1:], 16)
                    for x,y in p['points']:
                        assert math.isfinite(x) and math.isfinite(y)
                        assert 0 <= x <= analysis.width_px and 0 <= y <= analysis.height_px
            except (AssertionError, KeyError, TypeError, ValueError):
                abort(400, knowledge_message('web.19'))
            storage.write_text(json.dumps({'height_mm':height,'paths':data['paths']}))
            return jsonify(saved=True)
        if storage.exists():
            state = json.loads(storage.read_text())
        else:
            saved_file = decisions / f'{path.stem}.json'
            saved = json.loads(saved_file.read_text()) if saved_file.exists() else {}
            choices = {r.id:{**asdict(recommend(r,analysis.estimated_dpi,analysis.line_art_mode)),**saved.get(r.id,{})} for r in analysis.regions}
            state = {'height_mm':analysis.height_px*25.4/analysis.estimated_dpi,
                     'paths':[asdict(p) for p in create_preview(path,analysis,choices) if p.kind=='sewn']}
        template = 'workspace.html' if request.args.get('workspace') == '1' else 'editor.html'
        return render_template(template,name=path.name,state=state,analysis=analysis)

    @app.get('/studio-export/<name>/<format>')
    def studio_export(name,format):
        from .release_gate import FORMATS
        if format not in FORMATS or Path(name).name != name:
            abort(404)
        target=root/'work'/'inkstitch-preview'/Path(name).stem
        if not (target/'playback.json').is_file():
            abort(404)
        from .release_gate import download
        return download(target,format)
    @app.get('/applique-cut/<name>')
    def applique_cut(name):
        # Appliqué fabric shapes at actual size (engine.cutting_svg), written with the stitches.
        if Path(name).name != name:
            abort(404)
        target=root/'work'/'inkstitch-preview'/Path(name).stem/'applique-cut.svg'
        if not target.is_file():
            abort(404)
        from flask import send_file
        return send_file(target,mimetype='image/svg+xml',as_attachment=True,download_name='applique-cutting.svg')
    @app.get('/api/problems/<name>')
    def design_problems(name):
        # Problems panel (problems.py): findings of the generated stitches with one-click fixes.
        if Path(name).name != name or not name.startswith('prepared_'):
            abort(404)
        target=root/'work'/'inkstitch-preview'/Path(name).stem
        prepared=uploads/name
        if not (target/'playback.json').is_file() or not prepared.is_file():
            abort(404)
        meta=prepared.with_suffix('.prep.json')
        options=json.loads(meta.read_text()).get('options',{}) if meta.is_file() else {}
        from .problems import collect
        from .release_gate import ReleaseError
        try:
            return jsonify(problems=collect(target,prepared,options))
        except ReleaseError as error:
            return jsonify(problems=[],note=str(error))
    @app.get('/text-font/<key>')
    def text_font(key):
        # The embroidery fonts' TTF files, for the instant letter preview while typing.
        from .embroidery_fonts import FONTS, font_path
        if key not in FONTS:
            abort(404)
        path=Path(font_path(key))
        return send_from_directory(path.parent,path.name,mimetype='font/ttf',max_age=86400)
    @app.get('/api/area-at/<name>')
    def area_at_point(name):
        # Remove stitches: the whole colour area under a click (problems.area_at).
        if Path(name).name != name or not name.startswith('prepared_') or not (uploads/name).is_file():
            abort(404)
        from .problems import area_at
        try:
            area=area_at(uploads/name,float(request.args['x']),float(request.args['y']))
        except (KeyError,ValueError):
            abort(400)
        return jsonify(area=area)
    @app.get("/")
    def index():
        if any(key in request.args for key in ('view', 'sort', 'q')):
            return redirect(url_for('design_library_page', **request.args.to_dict()))
        return render_template("landing.html")

    @app.get("/designs")
    def design_library_page():
        return render_template("library.html", files=app.extensions['design_library'].list('recent'))

    @app.post("/upload")
    def upload():
        image = request.files.get("image")
        if not image or not image.filename:
            abort(400, "Choose an image to analyse")
        suffix = Path(image.filename).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".svg"}:
            abort(400, "Supported image formats: PNG, JPG, BMP, WebP, SVG")
        if suffix == ".svg":
            # Vector logos are rendered by our own geometry-only reader to a
            # transparent PNG; the original SVG is kept beside it for reference.
            from .vector_raster import svg_upload
            try:
                rendered, source = svg_upload(image.read())
            except ValueError as error:
                abort(400, str(error))
            name = f"{uuid4().hex}.png"
            rendered.save(uploads / name)
            (decisions / (name + ".source.svg")).write_bytes(source)
        else:
            name = f"{uuid4().hex}{suffix}"
            image.save(uploads / name)
        from .preparation import load_image
        from .subject_model import warm_image
        warm_image(load_image(uploads/name))
        return redirect(url_for("prepare", name=name))

    @app.route('/prepare/<name>', methods=['GET', 'POST'])
    def prepare(name):
        path = uploads / Path(name).name
        if not path.is_file():
            abort(404)
        with Image.open(path) as source:
            width, height = source.size
            if request.method == 'POST':
                try:
                    box = tuple(int(request.form[k]) for k in ('left','top','right','bottom'))
                    assert 0 <= box[0] < box[2] <= width
                    assert 0 <= box[1] < box[3] <= height
                except (ValueError, KeyError, AssertionError):
                    abort(400, 'Choose a crop inside the image.')
                selected = source.convert('RGBA')
                if request.form.get('outline'):
                    try:
                        points = json.loads(request.form['outline'])
                        assert 3 <= len(points) <= 2000
                        for x,y in points:
                            assert math.isfinite(x) and math.isfinite(y)
                            assert 0 <= x <= width and 0 <= y <= height
                        points = [(round(x),round(y)) for x,y in points]
                        assert abs(sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points)))) > 2
                    except (ValueError, TypeError, AssertionError):
                        abort(400, 'Draw an outline with at least three points around the subject.')
                    mask = Image.new('L',source.size,0)
                    ImageDraw.Draw(mask).polygon(points,fill=255)
                    selected.putalpha(ImageChops.multiply(selected.getchannel('A'),mask))
                cropped = selected.crop(box)
                new_name = uuid4().hex + '.png'
                cropped.save(uploads / new_name)
                return redirect(url_for('review',name=new_name))
        return redirect(url_for('artwork_prepare',name=path.name))

    @app.get("/review/<name>")
    def review(name: str):
        path = uploads / Path(name).name
        if not path.exists():
            abort(404)
        analysis = analyze_image(path)
        saved_path = decisions / f"{path.stem}.json"
        saved = json.loads(saved_path.read_text()) if saved_path.exists() else {}
        plans = {region.id: {**asdict(recommend(region, analysis.estimated_dpi, analysis.line_art_mode)), **saved.get(region.id, {})} for region in analysis.regions}
        return render_template("review.html", name=path.name, analysis=analysis, plans=plans)

    @app.post("/review/<name>/decisions")
    def save_decisions(name: str):
        path = uploads / Path(name).name
        if not path.exists():
            abort(404)
        analysis = analyze_image(path)
        choices = {
            region.id: {
                "stitch_type": request.form.get(f"{region.id}-stitch", "fill"),
                "contour": request.form.get(f"{region.id}-contour", "none"),
                "fill": request.form.get(f"{region.id}-fill", "none"),
            }
            for region in analysis.regions
        }
        (decisions / f"{path.stem}.json").write_text(json.dumps(choices, sort_keys=True, indent=2))
        return redirect(url_for("review", name=path.name, saved="1"))

    @app.get("/api/review/<name>")
    def review_api(name: str):
        path = uploads / Path(name).name
        if not path.exists():
            abort(404)
        return jsonify(asdict(analyze_image(path)))

    @app.get("/simulate/<name>")
    def simulate(name: str):
        path = uploads / Path(name).name
        if not path.exists():
            abort(404)
        analysis = analyze_image(path)
        saved_path = decisions / f"{path.stem}.json"
        saved = json.loads(saved_path.read_text()) if saved_path.exists() else {}
        automatic = {region.id: asdict(recommend(region, analysis.estimated_dpi, analysis.line_art_mode)) for region in analysis.regions}
        planned = create_preview(path, analysis, {key: {**automatic[key], **saved.get(key, {})} for key in automatic})
        payload = [asdict(segment) for segment in planned]
        coverage = audit_preview_coverage(path, planned)
        coverage_data = {key: value for key, value in asdict(coverage).items() if key != "missed_mask"}
        scale = 25.4 / analysis.estimated_dpi
        edited = decisions / (path.name + '.editor.json')
        if edited.exists():
            state = json.loads(edited.read_text())
            planned = [PreviewSegment(tuple(tuple(p) for p in s['points']),s['colour'],'sewn') for s in state['paths']]
            scale = state['height_mm'] / analysis.height_px
        planned = apply_colours(path, planned)
        playback = build_playback(planned, root / 'work' / 'machine-preview' / path.stem, scale)
        return render_template("machine.html", name=path.name, playback=playback, scale=scale)

    @app.get('/finished/<name>')
    def finished(name):
        # Compatibility route: still render the written file, never saved plan JSON.
        if Path(name).name != name:
            abort(404)
        return redirect(url_for('thread_mockup', name=name,
            fabric=request.args.get('fabric','#c2baa8'), download='false',
            legacy='false' if request.args.get('engine')=='inkstitch' else 'true'))

    @app.route('/engine/<name>', methods=['GET','POST'])
    def engine_trial(name):
        from .engine import digitize
        path=uploads / Path(name).name
        if not path.is_file():abort(404)
        if request.method=='GET':
            # Prepared artwork belongs to the current workspace. Old shared
            # playback URLs must not unexpectedly reveal the retired UI.
            if path.with_suffix('.prep.json').is_file():
                return redirect(url_for('artwork_prepare',name=path.name,view='stitched'))
            saved = root/'work'/'inkstitch-preview'/path.stem/'playback.json'
            if request.args.get('view')=='1' and saved.is_file():
                return render_template('machine.html',name=path.name,playback=json.loads(saved.read_text()),scale=1)
            return render_template('engine.html',name=path.name)
        try:
            height=float(request.form.get('height_mm','100'))
            if not math.isfinite(height) or not 3<=height<=300:
                raise ValueError(knowledge_message('web.18'))
            config=decisions / (path.name+'.colours.json')
            colours=json.loads(config.read_text()) if config.exists() else None
            payload=digitize(path,root/'work'/'inkstitch-preview'/path.stem,height,colours)
        except (ValueError,TimeoutError) as error:
            return render_template('engine.html',name=path.name,error=str(error)),400
        return render_template('machine.html',name=path.name,playback=payload,scale=1)

    @app.get("/coverage/<name>.png")
    def coverage_mask(name: str):
        path = uploads / Path(name).name
        if not path.exists():
            abort(404)
        analysis = analyze_image(path)
        saved_path = decisions / f"{path.stem}.json"
        saved = json.loads(saved_path.read_text()) if saved_path.exists() else {}
        automatic = {region.id: asdict(recommend(region, analysis.estimated_dpi, analysis.line_art_mode)) for region in analysis.regions}
        audit = audit_preview_coverage(path, create_preview(path, analysis, {key: {**automatic[key], **saved.get(key, {})} for key in automatic}))
        rgba = np.zeros((*audit.missed_mask.shape, 4), dtype=np.uint8)
        rgba[audit.missed_mask] = (230, 49, 49, 210)
        target = (root / "work" / f"{path.stem}-possible-misses.png").resolve()
        Image.fromarray(rgba, "RGBA").save(target)
        return send_from_directory(target.parent, target.name, mimetype="image/png")

    def _line_masks(path: Path) -> tuple[Image.Image, Image.Image]:
        """Line art layers: dark pixels form borders; enclosed light areas form fills."""
        with Image.open(path) as opened:
            source = opened.convert("RGB")
        pixels = np.asarray(source)
        dark = np.all(pixels < 170, axis=2)
        open_space = ~dark
        exterior = np.zeros(open_space.shape, dtype=bool)
        height, width = open_space.shape
        stack = [(y, x) for x in range(width) for y in (0, height - 1)] + [(y, x) for y in range(height) for x in (0, width - 1)]
        while stack:
            y, x = stack.pop()
            if not (0 <= y < height and 0 <= x < width and open_space[y, x] and not exterior[y, x]):
                continue
            exterior[y, x] = True
            stack.extend(((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)))
        enclosed = open_space & ~exterior
        def alpha(mask: np.ndarray) -> Image.Image:
            result = np.zeros((height, width, 4), dtype=np.uint8)
            result[:, :, 3] = np.where(mask, 255, 0)
            return Image.fromarray(result, "RGBA")
        return alpha(enclosed), alpha(dark)

    @app.get("/layers/<name>/<layer>.png")
    def layer_mask(name: str, layer: str):
        path = uploads / Path(name).name
        if not path.exists() or layer not in {"fill", "outline"}:
            abort(404)
        fill, outline = _line_masks(path)
        target = (root / "work" / f"{path.stem}-{layer}.png").resolve()
        (fill if layer == "fill" else outline).save(target)
        return send_from_directory(target.parent, target.name, mimetype="image/png")

    @app.get("/design/<name>")
    def design(name: str):
        path = uploads / Path(name).name
        if not path.exists():
            abort(404)
        return render_template("design.html", name=path.name, line_art_mode=analyze_image(path).line_art_mode)

    @app.get("/uploads/<name>")
    def uploaded_file(name: str):
        return send_from_directory(uploads, Path(name).name)

    @app.post("/demo/export")
    def demo_export():
        result = export_design(sample_design(), exports, "milestone0")
        return jsonify(dst=result.dst_path.name, pes=result.pes_path.name)

    return app


def main() -> None:
    create_app().run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
