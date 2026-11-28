"""One-page PDF for EcoSite preliminary comparison (including site-outline map).

No network, tiles, external fonts or print services required. The map is an
honestly labeled footprint overview rather than a georeferenced street map.
"""
from __future__ import annotations

from html import escape
from io import BytesIO
from math import cos, radians

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from shapely.geometry import shape

from experience import best_preliminary_option

GREEN = colors.HexColor('#104F46')
DARK = colors.HexColor('#132B25')
MUTED = colors.HexColor('#345246')
PALE = colors.HexColor('#EAF3ED')
BORDER = colors.HexColor('#C4D5CA')
RED = colors.HexColor('#922D3C')
SITE_COLORS = ['#147E70','#B86B23','#625BB1','#3376AA','#A84B7B']
GRADE_COLORS = {'A':'#12583D','B':'#0A5358','C':'#765014','D':'#963E18','F':'#9A2638','N/A':'#3D4E4E'}


def para(c, text, x, top, width, font_size=9, leading=11.6, color=DARK, max_height=60, bold=False):
    style=ParagraphStyle('p', fontName='Helvetica-Bold' if bold else 'Helvetica',
        fontSize=font_size, leading=leading, textColor=color, spaceAfter=0,
        allowWidows=0, allowOrphans=0, alignment=TA_LEFT)
    p=Paragraph(escape(str(text)).replace('\n','<br/>'), style)
    _, h=p.wrap(width, max_height)
    if h > max_height:
        # Long notes should not overlap another box; truncate by words.
        words=str(text).split()
        while words and h>max_height:
            words=words[:-4]
            p=Paragraph(escape(' '.join(words)+' ...'),style)
            _,h=p.wrap(width,max_height)
    p.drawOn(c,x,top-h)
    return h


def clipped(text: str, limit: int) -> str:
    return str(text) if len(str(text))<=limit else str(text)[:limit-3].rsplit(' ',1)[0]+'...'


def draw_outline_map(c, sites: list[dict], x: float, y: float, w: float, h: float):
    """Draw relative positions and actual rectangle/polygon geometry, not basemap."""
    c.setFillColor(colors.white);c.setStrokeColor(BORDER)
    c.roundRect(x,y,w,h,8,fill=1,stroke=1)
    c.setFont('Helvetica-Bold',9);c.setFillColor(DARK)
    c.drawString(x+11,y+h-18,'CANDIDATE FOOTPRINTS')
    c.setFont('Helvetica',7.8);c.setFillColor(MUTED)
    c.drawString(x+11,y+9,'Site symbols enlarged; no streets or habitat basemap')
    inner_x,inner_y=x+12,y+26
    inner_w,inner_h=w-24,h-57
    geoms=[]
    for site in sites:
        try: geoms.append(shape(site['feature']['geometry']))
        except Exception: pass
    if not geoms:
        c.drawString(inner_x,inner_y+inner_h/2,'No usable site outlines')
        return
    lat_center=sum(g.centroid.y for g in geoms)/len(geoms)
    squash=max(.15,cos(radians(lat_center)))
    all_coords=[]
    for geom in geoms:
        all_coords.extend([(lon*squash,lat) for lon,lat in geom.exterior.coords])
    minx,maxx=min(a for a,_ in all_coords),max(a for a,_ in all_coords)
    miny,maxy=min(b for _,b in all_coords),max(b for _,b in all_coords)
    xrange=max(maxx-minx,0.00015);yrange=max(maxy-miny,0.00015)
    scale=min((inner_w-35)/xrange,(inner_h-26)/yrange)
    def xy(lon,lat):
        return (inner_x+inner_w/2+(lon*squash-(minx+maxx)/2)*scale,
                inner_y+inner_h/2+(lat-(miny+maxy)/2)*scale)
    c.setStrokeColor(colors.HexColor('#DCE8DF'));c.setLineWidth(.5)
    for frac in (.25,.5,.75):
        c.line(inner_x+frac*inner_w,inner_y,inner_x+frac*inner_w,inner_y+inner_h)
        c.line(inner_x,inner_y+frac*inner_h,inner_x+inner_w,inner_y+frac*inner_h)
    for i,site in enumerate(sites):
        try: geom=shape(site['feature']['geometry'])
        except Exception:continue
        coords=list(geom.exterior.coords)
        # A normal building footprint is tiny relative to a map of a town;
        # enlarge its footprint symbol visibly while preserving site position.
        pts=[xy(lon,lat) for lon,lat in coords]
        midx=(min(xx for xx,yy in pts)+max(xx for xx,yy in pts))/2
        midy=(min(yy for xx,yy in pts)+max(yy for xx,yy in pts))/2
        width=max(16.,max(xx for xx,yy in pts)-min(xx for xx,yy in pts))
        height=max(13.,max(yy for xx,yy in pts)-min(yy for xx,yy in pts))
        p=c.beginPath()
        p.moveTo(midx-width/2,midy-height/2)
        p.lineTo(midx+width/2,midy-height/2)
        p.lineTo(midx+width/2,midy+height/2)
        p.lineTo(midx-width/2,midy+height/2)
        p.close()
        col=colors.HexColor(SITE_COLORS[i%len(SITE_COLORS)])
        c.setFillColor(col);c.setStrokeColor(col);c.setLineWidth(1.7)
        c.drawPath(p,stroke=1,fill=0)
        cx,cy=xy(geom.centroid.x,geom.centroid.y)
        c.setFillColor(col);c.circle(cx,cy,9,fill=1,stroke=0)
        c.setFillColor(colors.white);c.setFont('Helvetica-Bold',9)
        c.drawCentredString(cx,cy-3,str(i+1))
    c.setFont('Helvetica-Bold',8);c.setFillColor(MUTED)
    c.drawString(x+w-20,y+h-18,'N')
    c.line(x+w-16,y+h-33,x+w-16,y+h-23)


def build_one_page_report(sites: list[dict], results: dict, *, community: str,
                          restoration_plan: dict | None=None, demo: bool=False) -> bytes:
    """Return exactly one printable US Letter page with site grades and map."""
    if len(sites)<2 or len(sites)>5 or any(s['id'] not in results for s in sites):
        raise ValueError('Save and compare two to five sites before exporting a report.')
    buffer=BytesIO();c=canvas.Canvas(buffer,pagesize=letter,pageCompression=1)
    W,H=letter
    c.setTitle('EcoSite AI - One-page community screening summary')
    # Masthead
    c.setFillColor(GREEN);c.rect(0,H-88,W,88,fill=1,stroke=0)
    c.setFillColor(colors.white);c.setFont('Helvetica-Bold',21)
    c.drawString(34,H-40,'EcoSite AI')
    c.setFont('Helvetica-Bold',11)
    c.drawString(34,H-60,'Biodiversity site comparison | Community brief')
    c.setFont('Helvetica',8)
    c.drawRightString(W-34,H-35,'FIRST LEGO LEAGUE  /  RESEARCH PROTOTYPE')
    c.drawRightString(W-34,H-52,'Two map layers only: USGS land cover + USFWS NWI')
    if demo:
        c.setFillColor(colors.HexColor('#FFE5AA'));c.setFont('Helvetica-Bold',9)
        c.drawString(34,H-77,'FICTIONAL DEMONSTRATION - ALL GRADES AND MEASUREMENTS ARE INVENTED')
    c.setFillColor(DARK);c.setFont('Helvetica-Bold',12)
    c.drawString(34,H-112,clipped(community,68))
    c.setFont('Helvetica',8.5);c.setFillColor(MUTED)
    c.drawRightString(W-34,H-112,f'{len(sites)} candidate locations  |  A = less mapped concern')

    draw_outline_map(c,sites,34,487,250,179)
    summary=best_preliminary_option(sites,results)
    x,y,w,h=296,487,282,179
    c.setFillColor(PALE);c.setStrokeColor(BORDER)
    c.roundRect(x,y,w,h,8,stroke=1,fill=1)
    c.setFillColor(DARK);c.setFont('Helvetica-Bold',9)
    c.drawString(x+12,y+h-18,'PRELIMINARY FINDING')
    if summary.get('winner'):
        winner=summary['winner'];r=summary['result']
        c.setFillColor(GREEN);c.setFont('Helvetica-Bold',13)
        c.drawString(x+12,y+h-40,clipped(f"Investigate {winner['name']} first (Grade {r['grade']['grade']})",34))
        t=y+h-53
        for i,reason in enumerate(summary['reasons'][:2]):
            c.setFillColor(GREEN);c.setFont('Helvetica-Bold',10)
            c.drawString(x+12,t-7,f'{i+1}.')
            used=para(c,clipped(reason,172),x+30,t,w-43,8.6,11,max_height=35)
            t-=used+11
        para(c,'Not an approval: species, connectivity, water, infrastructure and other risks are unassessed.',x+12,y+42,w-24,8.4,11,color=MUTED,max_height=35)
    else:
        c.setFont('Helvetica-Bold',13);c.setFillColor(RED)
        c.drawString(x+12,y+h-42,'No justified single winner')
        para(c,summary['reason'],x+12,y+h-57,w-24,9.3,12,max_height=80)
        para(c,'Review data gaps and additional site alternatives before a decision.',x+12,y+42,w-24,8.4,11,color=MUTED,max_height=35)

    # Comparison table
    c.setFillColor(DARK);c.setFont('Helvetica-Bold',12)
    c.drawString(34,468,'SITE COMPARISON')
    c.setFillColor(PALE);c.roundRect(34,444,544,17,4,stroke=0,fill=1)
    c.setFillColor(DARK);c.setFont('Helvetica-Bold',8)
    c.drawString(43,450,'SITE')
    c.drawString(139,450,'GRADE')
    c.drawString(197,450,'WHY IT RECEIVED THIS GRADE')
    row_h=38 if len(sites)==5 else 42
    row_top=443
    for i,site in enumerate(sites):
        r=results[site['id']];grade=r['grade']['grade']
        bottom=row_top-(i+1)*row_h
        if i%2==0:
            c.setFillColor(colors.HexColor('#F7FAF7'));c.rect(34,bottom,544,row_h,stroke=0,fill=1)
        c.setFillColor(colors.HexColor(SITE_COLORS[i]));c.circle(44,bottom+row_h/2,4,stroke=0,fill=1)
        para(c,clipped(site['name'],25),54,bottom+row_h-10,82,9,10.5,max_height=row_h-12,bold=True)
        c.setFillColor(colors.HexColor(GRADE_COLORS.get(grade,'#344')))
        c.setFont('Helvetica-Bold',15);c.drawString(145,bottom+row_h/2-5,grade)
        explanation=r['grade'].get('explanation','No explanation available.')
        para(c,clipped(explanation,205),197,bottom+row_h-6,365,8.4,10.2,max_height=row_h-8)
        c.setStrokeColor(BORDER);c.setLineWidth(.6);c.line(34,bottom,578,bottom)
    bottom_table=row_top-row_h*len(sites)

    # Optional restoration recommendations, compact enough to fit below 5 sites
    rest_top=bottom_table-18
    c.setFillColor(DARK);c.setFont('Helvetica-Bold',11)
    c.drawString(34,rest_top,'RESTORATION OPPORTUNITIES (OPTIONAL)')
    if restoration_plan:
        place=clipped(restoration_plan.get('restoration_location','Selected area'),65)
        para(c,f"Potential area: {place} ({restoration_plan.get('restoration_acres',0):.2f} acres examined).",34,rest_top-11,544,8.8,11,max_height=17)
        items=[item['title'] for item in restoration_plan.get('actions',[])][:2]
        plants=[p['common'] for p in restoration_plan.get('native_plant_guidance',{}).get('items',[])][:3]
        note=('Ideas: '+'; '.join(items)+'.') if items else 'A site visit is needed to identify a suitable restoration action.'
        para(c,clipped(note,200),34,rest_top-27,544,8.4,10.5,max_height=26)
        if plants:
            para(c,'Possible Iowa natives (verify site): '+', '.join(plants)+'.',34,rest_top-53,544,8.1,10,max_height=20)
        else:
            para(c,'Plant list pending: select site sunlight and soil moisture to get region-appropriate candidates.',
                 34,rest_top-53,544,8.1,10,max_height=20)
    else:
        para(c,'No restoration area analyzed yet. Optionally explore on-site landscaping or another candidate parcel. Restore only where ecologically appropriate.',34,rest_top-12,544,8.9,11.5,max_height=34)

    # Footer - constant and deliberately readable; no tiny legal footnotes
    c.setFillColor(colors.HexColor('#F0F5F0'));c.rect(0,0,W,76,stroke=0,fill=1)
    c.setFillColor(DARK);c.setFont('Helvetica-Bold',8.7)
    c.drawString(34,58,'IMPORTANT SCIENTIFIC LIMITATIONS')
    para(c,'Grades are provisional educational thresholds for two mapped layers, not measured biodiversity impact, a permit, a verified offset or proof of construction feasibility.',34,53,544,8.3,10.5,max_height=28)
    c.setFillColor(MUTED);c.setFont('Helvetica',7.6)
    c.drawString(34,12,'Sources: USGS Annual NLCD; USFWS National Wetlands Inventory. Site outlines are schematic.')
    if demo:
        c.setFillColor(RED);c.setFont('Helvetica-Bold',8)
        c.drawRightString(W-34,12,'SAMPLE DATA - NOT FOR PLANNING')
    c.showPage();c.save()
    return buffer.getvalue()
