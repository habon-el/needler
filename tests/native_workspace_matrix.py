"""Real font -> check -> workspace -> approve -> DST/PES, isolated from designs."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from embroiderly.web import create_app


def main():
    output=Path('work/native-workspace-verification')
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    cases=[(word,size) for word in ('Hello World','tiny') for size in (4,5,6)]
    cases += [('jesus is\nkings',4),('jesus is\nkings',5),('Baby 0689',4),('i j . , :',4)]
    with TemporaryDirectory(prefix='native-workspace-') as temp:
        client=create_app(Path(temp)).test_client()
        for text,size in cases:
            started=time.monotonic()
            body=dict(text=text,font='small_font',height_mm=size,available_width_mm=60,align='center',colour='#202020')
            response=client.post('/lettering/native/check',json=body)
            assert response.status_code==200,response.json
            data=response.json;key=data['id']
            assert data['checks_passed'],data['issues']
            view=client.get('/lettering/native/'+key+'/workspace-data')
            assert view.status_code==200,view.json
            assert view.json['result']['recipe']==data['recipe']
            assert view.json['playback']['stitch_count']==data['reports']['dst']['stitches']
            assert client.post('/lettering/native/'+key+'/approve',json={'approve':True}).status_code==200
            hashes={}
            for fmt in ('dst','pes'):
                files=[client.get('/lettering/native/'+key+'/download/'+fmt) for _ in range(3)]
                assert all(r.status_code==200 for r in files)
                assert files[0].data==files[1].data==files[2].data
                hashes[fmt]=hashlib.sha256(files[0].data).hexdigest()
            assert data['reports']['dst']['trims']==data['reports']['pes']['trims']
            row=dict(text=text,size=size,reports=data['reports'],seconds=round(time.monotonic()-started,2),
                     repeat_downloads_identical=True,hashes=hashes)
            results.append(row)
            print(json.dumps({k:v for k,v in row.items() if k!='hashes'}),flush=True)
            (output/'results.json').write_text(json.dumps(results,indent=2))
        assert not list((Path(temp)/'work/uploads').iterdir()),'Typed letters became uploaded pictures'
    print('PASS: all cases; both formats; no raster uploads; identical repeated downloads. Sew-out pending.')


if __name__=='__main__':
    main()
