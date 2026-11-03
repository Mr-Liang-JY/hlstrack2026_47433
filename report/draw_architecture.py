"""Draw the implemented data/control path as repository-native SVG and PNG."""
from pathlib import Path
import html,math
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
 width,height=1120,550
 image=Image.new('RGB',(width,height),'white');draw=ImageDraw.Draw(image)
 font=ImageFont.truetype(str(ROOT/'data/input/dejavu_sans.ttf'),21)
 small=ImageFont.truetype(str(ROOT/'data/input/dejavu_sans.ttf'),16)
 svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="550" viewBox="0 0 1120 550">',
 '<defs><marker id="arrow" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto"><polygon points="0,0 9,3.5 0,7" fill="#53667b"/></marker></defs>', '<rect width="1120" height="550" fill="white"/>']
 def box(x,y,w,h,label):
  draw.rounded_rectangle((x,y,x+w,y+h),radius=6,outline='#64758a',fill='#eef2f6',width=2)
  svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#eef2f6" stroke="#64758a" stroke-width="2"/>')
  lines=label.split('\n');cy=y+h/2-(len(lines)-1)*14
  for line in lines:
   draw.text((x+w/2,cy),line,font=font,fill='#1f3145',anchor='mm')
   svg.append(f'<text x="{x+w/2}" y="{cy+7}" text-anchor="middle" font-family="sans-serif" font-size="21" fill="#1f3145">{html.escape(line)}</text>');cy+=28
 def arrow(points,label='',label_at=None):
  draw.line(points,fill='#53667b',width=3);a,b=points[-2:];angle=math.atan2(b[1]-a[1],b[0]-a[0]);triangle=[b,(b[0]-10*math.cos(angle-.45),b[1]-10*math.sin(angle-.45)),(b[0]-10*math.cos(angle+.45),b[1]-10*math.sin(angle+.45))];draw.polygon(triangle,fill='#53667b')
  points_text=' '.join(f'{x},{y}' for x,y in points);svg.append(f'<polyline points="{points_text}" fill="none" stroke="#53667b" stroke-width="3" marker-end="url(#arrow)"/>')
  if label:
   x,y=label_at;draw.text((x,y),label,font=small,fill='#31445a',anchor='mm');svg.append(f'<text x="{x}" y="{y+5}" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#31445a">{html.escape(label)}</text>')
 box(20,40,150,90,'MP4\nFILE');box(220,40,250,90,'PS DECODE\nPRE-PROCESS');box(550,40,250,90,'PL STREAMING\nSOBEL + ROI')
 box(550,220,250,95,'PS MAD / CENTROID\nFFT / THRESHOLD');box(220,220,250,95,'PS DISPLAY PACKET\nFILE CACHE')
 box(220,405,250,95,'PL DOUBLE BUFFER\nNATIVE UI');box(550,405,250,95,'PL TMDS\nOSERDESE2');box(865,405,230,95,'HDMI OUT\n720P60')
 arrow([(170,85),(220,85)]);arrow([(470,85),(550,85)],'AXI DMA',(510,60));arrow([(675,130),(675,220)],'DMA + GPIO',(735,174))
 arrow([(550,268),(470,268)]);arrow([(345,130),(345,220)],'GRAY',(382,175));arrow([(345,315),(345,405)],'DISPLAY DMA',(415,360))
 arrow([(800,265),(835,265),(835,85),(800,85)],'NEXT-FRAME GPIO',(947,175));arrow([(470,452),(550,452)]);arrow([(800,452),(865,452)])
 draw.text((560,525),'128x128 PROCESSING  |  OFFLINE ANALYSIS THEN 30 FPS PLAYBACK',font=small,anchor='mm',fill='#526070')
 svg.append('<text x="560" y="530" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#526070">128x128 PROCESSING | OFFLINE ANALYSIS THEN 30 FPS PLAYBACK</text></svg>')
 folder=ROOT/'report/figures';image.save(folder/'architecture.png');(folder/'architecture.svg').write_text('\n'.join(svg),encoding='utf-8')
if __name__=='__main__':main()
