"""Private stdin/stdout worker; launched with isolated Python, no API credentials.

One CPU model, up to four encoded images. No HTTP port and no downloads. This
process deliberately does not import the app or its installed libraries.
"""
import base64
import contextlib
import io
import json
import sys


def main():
    # Library diagnostics must never corrupt the JSON response stream.
    channel = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        import numpy as np
        import torch
        from PIL import Image
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        torch.set_num_threads(4)
        model = build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml', sys.argv[1],
                          device='cpu', apply_postprocessing=False)
        predictors = {}
    for line in sys.stdin:
        try:
            request = json.loads(line)
            key = request['key']
            with contextlib.redirect_stdout(sys.stderr), torch.inference_mode():
                if request['op'] == 'encode':
                    if key not in predictors:
                        if len(predictors) >= 4:
                            raise ValueError('Embedding capacity reached; restart the app to release images.')
                        image = Image.open(io.BytesIO(base64.b64decode(request['image']))).convert('RGB')
                        predictor = SAM2ImagePredictor(model, max_hole_area=0, max_sprinkle_area=0)
                        predictor.set_image(np.asarray(image))
                        predictors[key] = predictor
                    result = {'ready': True}
                elif request['op'] == 'predict':
                    args = {k: (np.asarray(v) if v is not None else None)
                            for k,v in request['args'].items() if k != 'multimask_output'}
                    masks, scores, _ = predictors[key].predict(**args, multimask_output=True)
                    result = {'shape': list(masks.shape), 'scores': scores.tolist(),
                              'masks': base64.b64encode(np.packbits(masks.astype(bool)).tobytes()).decode('ascii')}
                else:
                    raise ValueError('Unknown local segmentation operation.')
        except Exception as error:
            result = {'error': str(error)}
        channel.write(json.dumps(result, allow_nan=False) + '\n'); channel.flush()


if __name__ == '__main__':
    main()
