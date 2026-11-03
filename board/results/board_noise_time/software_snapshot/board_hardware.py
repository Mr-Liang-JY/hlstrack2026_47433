"""PYNQ-only driver. Timeouts/errors never silently fall back to software."""
from pathlib import Path
import hashlib
import json
import time
import numpy as np

class Hardware:
    def __init__(self,bit,timeout=5):
        from pynq import Overlay,Clocks,allocate,MMIO
        self.timeout=timeout;self.buffers=[];self.dmas=[]
        path=Path(bit)
        manifest=json.loads(path.with_name('manifest.json').read_text())
        for name,expected in manifest['hardware_sha256'].items():
            if hashlib.sha256(path.with_name(name).read_bytes()).hexdigest()!=expected:
                raise ValueError('Hardware hash mismatch: '+name)
        self.overlay=Overlay(str(path));Clocks.fclk0_mhz=100.0
        def mmio(name):
            ip=self.overlay.ip_dict[name]
            return MMIO(ip['phys_addr'],ip['addr_range'])
        self.control=mmio('axi_gpio_ctrl');self.stats=mmio('axi_gpio_stats')
        self.roi=mmio('axi_gpio_roi');self.display=mmio('display_control')
        self.sobel_dma=self.overlay.axi_dma_0;self.display_dma=self.overlay.display_dma
        self.dmas=[self.sobel_dma,self.display_dma]
        self.control.write(4,0);self.roi.write(4,0);self.display.write(4,0)
        self.display.write(0,0)
        self.control.write(0,0);time.sleep(0.002);self.control.write(0,1)
        self.wait(lambda:self.display.read(8)&6==6,'video clock lock')
        if self.display.read(8)>>24!=0xA8 or self.control.read(8)>>28!=0xD:
            raise RuntimeError('Unexpected hardware signatures')
        self.tx=allocate((128,128),dtype=np.uint32);self.buffers.append(self.tx)
        self.rx=allocate((128,128),dtype=np.uint32);self.buffers.append(self.rx)
        self.screen=allocate((8448,),dtype=np.uint32);self.buffers.append(self.screen)
    def wait(self,predicate,label,dmas=()):
        end=time.monotonic()+self.timeout
        while True:
            for dma,rx in dmas:
                status=dma.mmio.read(0x34 if rx else 0x04)
                if status&0x70:raise RuntimeError('%s DMA error 0x%08X'%(label,status))
            if predicate():return
            if time.monotonic()>end:raise TimeoutError(label+' timed out')
            time.sleep(0.0001)
    def sobel(self,frame,threshold,roi):
        start=time.perf_counter();before=self.control.read(8)
        if before&2:raise RuntimeError('Sobel busy before new frame')
        expected=(((before>>24)&15)+1)&15
        x0,y0,x1,y1=roi
        self.roi.write(0,x0|(y0<<8)|(x1<<16)|(y1<<24))
        self.tx[:]=frame;self.tx.flush()
        # Arm receive first; then start the accelerator and the send channel.
        self.sobel_dma.recvchannel.transfer(self.rx)
        for bits in (1,3,1):self.control.write(0,(int(threshold)<<8)|bits)
        self.sobel_dma.sendchannel.transfer(self.tx)
        def complete():
            status=self.control.read(8)
            if (status>>20)&15:raise RuntimeError('Sobel framing/ROI error')
            return ((status&3)==1 and (status>>24)&15==expected and
                    bool(self.sobel_dma.mmio.read(4)&2) and bool(self.sobel_dma.mmio.read(0x34)&2))
        self.wait(complete,'Sobel',[(self.sobel_dma,False),(self.sobel_dma,True)])
        self.sobel_dma.sendchannel.wait();self.sobel_dma.recvchannel.wait();self.rx.invalidate()
        raw=np.array(self.rx,copy=True)
        if np.any(raw>>16):raise ValueError('Unexpected packed Sobel upper bits')
        edge=(raw&255).astype(np.uint8);mag=((raw>>8)&255).astype(np.uint8)
        return edge,mag,int(self.stats.read(0)),int(self.stats.read(8)),time.perf_counter()-start
    def show(self,canvas):
        if canvas.shape!=(8448,) or canvas.dtype!=np.dtype('<u4'):raise ValueError('Display needs 8448 little-endian uint32 words')
        status=self.display.read(8)
        if status&128:raise RuntimeError('Framebuffer protocol error')
        if status&64:raise RuntimeError('Previous frame still pending')
        expected=(((status>>8)&65535)+1)&65535
        # Explicit little-endian WORD VIEW avoids four uint32 conversions and
        # three shift/OR temporaries for every frame on the small ARM CPU.
        # Assignment to the native DMA buffer preserves values on either endian.
        self.screen[:]=canvas
        self.screen.flush();self.display.write(0,1)
        self.display_dma.sendchannel.transfer(self.screen)
        def done():
            status=self.display.read(8)
            if status&128:raise RuntimeError('Framebuffer rejected frame')
            return ((status>>8)&65535)==expected and not status&64 and bool(self.display_dma.mmio.read(4)&2)
        self.wait(done,'display frame swap',[(self.display_dma,False)])
        self.display_dma.sendchannel.wait()
        return self.display.read(8)
    def blank(self):self.display.write(0,0)
    def close(self):
        self.blank();self.control.write(0,0)
        safe=True
        for dma in self.dmas:
            # Reset stops memory accesses before releasing physically contiguous buffers.
            dma.mmio.write(0,4)
            try:self.wait(lambda:not(dma.mmio.read(0)&4),'DMA reset')
            except Exception:safe=False
        if safe:
            for buffer in self.buffers:buffer.freebuffer()
            self.buffers=[]
        else:raise RuntimeError('DMA reset incomplete; buffers retained until board restart')
