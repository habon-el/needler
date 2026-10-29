"""White parts inside the subject are kept, and stay apart from a pale sky.

Found Oct 2026: with the white background left out, white parts of the subject (a cloud
in the sky, a sheep on a hill) were removed with it, and a kept white part merged with the
pale sky next to it. Enclosed parts of the removed colour are now marked when they lie
well inside the subject; Digitize for me keeps those, and a kept colour is its own thread.
A letter's counter is not inside: the stroke around it is thin.
"""
import numpy as np
from PIL import Image, ImageDraw

from embroiderly.auto_digitize import AutoDigitizer, classify, plan
from embroiderly.colour_knockout import proposal_patch, remove_colour
from embroiderly.preparation import prepare
from embroiderly.web import create_app

SKY = '#dcefff'   # pale blue, 12 Delta-E from white


def landscape():
    image = Image.new('RGB', (400, 400), 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 360, 360), fill='#203060')     # dark ring
    draw.ellipse((60, 60, 340, 340), fill=SKY)
    draw.chord((60, 60, 340, 340), 30, 150, fill='#3c8c3c')  # green hill
    draw.ellipse((110, 100, 230, 160), fill='white')     # cloud in the sky
    draw.ellipse((150, 250, 250, 300), fill='white')     # sheep on the hill
    return image


def letter_o():
    image = Image.new('RGB', (400, 400), 'white')
    ImageDraw.Draw(image).ellipse((120, 80, 280, 320), outline='#202020', width=14)
    return image


def test_a_cloud_is_inside_the_subject_and_a_letter_counter_is_not():
    for picture, expected in ((landscape(), {True}), (letter_o(), {False})):
        rgb = np.asarray(picture)
        operation = proposal_patch(picture, {})['colour_knockouts'][0]
        _, _, report = remove_colour(rgb, np.ones(rgb.shape[:2], bool), operation, 100)
        assert {p['inside'] for p in report['parts']} == expected


def test_digitize_for_me_keeps_white_parts_apart_from_the_pale_sky(tmp_path):
    app = create_app(tmp_path)
    picture = landscape()
    path = tmp_path/'work/uploads/sky.png'
    picture.save(path)
    kind, facts = classify(picture)
    options = plan(kind, facts, {}, picture.size, {})
    options.update(proposal_patch(picture, options))
    assert AutoDigitizer(app, tmp_path)._keep_inside(path, options) == 2
    image, swatches, report = prepare(path, options)
    rgba = np.asarray(image.convert('RGBA'))
    cloud, sheep, sky, background = rgba[130, 170], rgba[275, 200], rgba[120, 300], rgba[10, 10]
    assert background[3] == 0
    assert cloud[3] == sheep[3] == 255 and tuple(cloud[:3]) == tuple(sheep[:3]) == (255, 255, 255)
    # The sky keeps its own thread: not merged into white, not removed as background.
    assert sky[3] == 255 and tuple(sky[:3]) != (255, 255, 255)
    assert report['colours_after'] == options['count'] + 1
    # White is kept as a colour, not shown as a lock the person set.
    assert len(swatches) == options['count'] + 1 and not any(s['locked'] for s in swatches)
