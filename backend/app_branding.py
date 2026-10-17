"""Public installation metadata, sourced from the same company as login branding."""
import base64
import hashlib
import io
from functools import lru_cache
from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw, ImageFont, ImageOps
from starlette.concurrency import run_in_threadpool


def version(company):
    return hashlib.sha256(((company.get('app_name') or 'BIG Mobile') + '\0' + (company.get('logo') or '')).encode()).hexdigest()[:24]


@lru_cache(maxsize=16)
def icon_png(logo, app_name, size):
    canvas=Image.new('RGBA', (size,size), 'white')
    if logo:
        try:
            header, encoded=logo.split(',',1)
            if header!='data:image/png;base64': raise ValueError('Unexpected logo format')
            content=base64.b64decode(encoded,validate=True)
            if len(content)>2*1024*1024: raise ValueError('Logo too large')
            with Image.open(io.BytesIO(content)) as source:
                if source.width*source.height>16_000_000: raise ValueError('Logo too large')
                image=ImageOps.exif_transpose(source).convert('RGBA')
                image=ImageOps.contain(image,(max(1,int(size*.84)),max(1,int(size*.84))),Image.Resampling.LANCZOS)
                canvas.alpha_composite(image,((size-image.width)//2,(size-image.height)//2))
        except Exception:
            # A bad saved logo must be corrected rather than advertised as a valid icon.
            raise HTTPException(422,'Logo aplikasi tidak valid. Unggah ulang logo PNG pada Pengaturan.')
    else:
        canvas=Image.new('RGBA',(size,size),'#0066ff')
        text=''.join(word[0] for word in app_name.split()[:2]).upper() or 'B'
        draw=ImageDraw.Draw(canvas)
        font=ImageFont.load_default(size=max(10,int(size*.35)))
        draw.text((size/2,size/2),text,font=font,fill='white',anchor='mm')
    result=io.BytesIO();canvas.save(result,format='PNG');return result.getvalue()


def register(router,runtime):
    @router.get('/branding/manifest.webmanifest')
    async def manifest():
        company=await runtime.db.companies.find_one({}, {'app_name':1,'logo':1}) or {}
        name=company.get('app_name') or 'BIG Mobile'
        revision=version(company)
        return JSONResponse({'id':'/','name':name,'short_name':name,'lang':'id','start_url':'/','scope':'/','display':'standalone','theme_color':'#0066ff','background_color':'#F5F9FF','icons':[{'src':f'/api/branding/icon/{size}.png?v={revision}','sizes':f'{size}x{size}','type':'image/png','purpose':'any'} for size in (192,512)]},media_type='application/manifest+json',headers={'Cache-Control':'no-store'})

    @router.get('/branding/icon/{size}.png')
    async def icon(size:int):
        if size not in (32,180,192,512):raise HTTPException(404,'Ukuran ikon tidak tersedia')
        company=await runtime.db.companies.find_one({}, {'app_name':1,'logo':1}) or {}
        content=await run_in_threadpool(icon_png,company.get('logo') or '',company.get('app_name') or 'BIG Mobile',size)
        return Response(content,media_type='image/png',headers={'Cache-Control':'no-cache'})
