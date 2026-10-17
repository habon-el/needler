"""Explicit source-space origin shared by generator, playback and release checks.

The generator otherwise centres its stitch bounds, which can differ from the
artwork bounds after short/tiny shapes are omitted. SVG standalone origin is a
document command, not a sewn object. Coordinates here are SVG user units.
"""
import xml.etree.ElementTree as ET


def set_origin(document, origin_mm, scale):
    defs = ET.SubElement(document, 'defs')
    ET.SubElement(defs, 'symbol', id='inkstitch_origin')
    ET.SubElement(document, 'use', {
        '{http://www.w3.org/1999/xlink}href': '#inkstitch_origin',
        'x': str(float(origin_mm[0])/scale),
        'y': str(float(origin_mm[1])/scale),
    })
