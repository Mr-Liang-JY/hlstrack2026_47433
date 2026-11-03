"""Render the checked-in technical report; requires a local Chinese TrueType font."""
from pathlib import Path
import argparse,html,re,os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,Preformatted,KeepTogether
from PIL import Image as PILImage
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--font');args=parser.parse_args()
    font=Path(args.font or os.environ.get('PROJECT_CJK_FONT','C:/Windows/Fonts/msyh.ttc'))
    if not font.is_file():raise FileNotFoundError('Pass --font with a Chinese TrueType font file')
    pdfmetrics.registerFont(TTFont('body',str(font)))
    bold=font.with_name('msyhbd.ttc')
    pdfmetrics.registerFont(TTFont('body-bold',str(bold if bold.exists() else font)))
    pdfmetrics.registerFontFamily('body',normal='body',bold='body-bold',italic='body',boldItalic='body-bold')
    styles={
      'body':ParagraphStyle('body',fontName='body',fontSize=10,leading=17,spaceAfter=8,wordWrap='CJK',splitLongWords=True),
      'h1':ParagraphStyle('h1',fontName='body-bold',fontSize=18,leading=27,spaceAfter=12,keepWithNext=True),
      'h2':ParagraphStyle('h2',fontName='body-bold',fontSize=13,leading=21,spaceBefore=12,spaceAfter=8,keepWithNext=True),
      'cell':ParagraphStyle('cell',fontName='body',fontSize=8.4,leading=13,wordWrap='CJK',splitLongWords=True),
      'head':ParagraphStyle('head',fontName='body-bold',fontSize=8.4,leading=13,textColor=colors.white,wordWrap='CJK'),
      'code':ParagraphStyle('code',fontName='body',fontSize=8,leading=12,wordWrap='CJK')}
    def inline(s):
        s=html.escape(s.strip())
        s=re.sub(r'\[([^]]+)\]\(([^)]+)\)',r'\1',s)
        s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
        return s.replace('`','')
    lines=(ROOT/'report/design_report.md').read_text(encoding='utf-8').splitlines();story=[];i=0;width=A4[0]-96
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('# '):story.append(Paragraph(inline(line[2:]),styles['h1']));i+=1;continue
        if line.startswith('## '):story.append(Paragraph(inline(line[3:]),styles['h2']));i+=1;continue
        if line.startswith('!['):
            match=re.match(r'!\[[^]]*\]\(([^)]+)\)',line);path=ROOT/'report'/match.group(1)
            with PILImage.open(path) as image:iw,ih=image.size
            story.append(Image(str(path),width=width,height=width*ih/iw));story.append(Spacer(1,7));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.match(r'^:?-+:?$',x) for x in cells):rows.append(cells)
                i+=1
            count=len(rows[0]);weights=([1.15,1,2] if count==3 else [1.4]+[1]*(count-1))
            columns=[width*x/sum(weights) for x in weights]
            content=[[Paragraph(inline(c),styles['head' if k==0 else 'cell']) for c in row] for k,row in enumerate(rows)]
            table=Table(content,colWidths=columns,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#31445a')),('VALIGN',(0,0),(-1,-1),'TOP'),
                 ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
                 ('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#cbd2d8')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f5f7')])]))
            block=[table,Spacer(1,10)]
            if len(rows)<=6:story.append(KeepTogether(block))
            else:story.extend(block)
            continue
        paragraph=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('#','|','![')):
            paragraph.append(lines[i].strip());i+=1
        story.append(Paragraph(inline(' '.join(paragraph)),styles['body']))
    output=ROOT/'report/design_report.pdf'
    doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=48,bottomMargin=45,
                           title='运动频谱的自适应边缘检测系统',author='Project contributors',subject='Design and verification report',pageCompression=1)
    def decorate(canvas,document):
        canvas.saveState();canvas.setFillColor(colors.HexColor('#59636f'));canvas.setFont('body',8)
        canvas.drawString(48,A4[1]-28,'运动频谱的自适应边缘检测系统  |  设计与验证')
        canvas.setStrokeColor(colors.HexColor('#d4d9de'));canvas.setLineWidth(.4);canvas.line(48,36,A4[0]-48,36)
        canvas.drawRightString(A4[0]-48,23,str(document.page));canvas.restoreState()
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    print('Rendered',output.name)
if __name__=='__main__':main()
