"""Original-coordinate annotation with reversible display transforms."""
from copy import deepcopy
import gc
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from .canvas_tools import display_point, original_point


def prepare_photo(path):
    with Image.open(path) as image:
        original=image.convert('RGB')
    preview=original.copy();preview.thumbnail((1600,1600))
    return original,preview


def display_image(image,rotation,size):
    # Resize before rotating to keep the transient display allocation bounded.
    target=size[::-1] if rotation%2 else size
    raster=image.resize(target,Image.Resampling.LANCZOS)
    return raster.rotate(-90*rotation,expand=True) if rotation else raster


class PhotoCanvas(ttk.Frame):
    def __init__(self,parent,changed,executor=None):
        super().__init__(parent);self.changed=changed;self.executor=executor
        self.canvas=tk.Canvas(self,bg='#202832',highlightthickness=0,width=500,height=180)
        sy=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        sx=ttk.Scrollbar(self,orient='horizontal',command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=sx.set,yscrollcommand=sy.set)
        self.canvas.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
        self.rowconfigure(0,weight=1);self.columnconfigure(0,weight=1)
        self.original=None;self.preview=None;self.patch_names=[];self.scale=1.;self.mode=0;self.points=[];self.masks={};self.start=None
        self.locked=False;self.rotation=0;self.undo_stack=[];self.redo_stack=[];self.handle=None;self.selected_handle=None
        self.render_token=0;self.render_timer=None
        self.rendering=False
        self.canvas.bind('<Button-1>',self.click)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',lambda e:self.finish())
        self.canvas.bind('<Control-z>',lambda e:self.undo())
        self.canvas.bind('<Control-y>',lambda e:self.redo())
        self.canvas.bind('<Delete>',lambda e:self.delete_vertex())
        self.canvas.bind('<Return>',lambda e:self.finish())
        self.bind('<Destroy>',self.cleanup,add='+')

    def cleanup(self,event):
        if event.widget is self:
            self.render_token+=1
            if self.render_timer:self.after_cancel(self.render_timer);self.render_timer=None

    def load(self,path,masks=None):
        self.set_prepared(prepare_photo(path),masks)

    def clear(self):
        self.render_token+=1
        if self.render_timer:self.after_cancel(self.render_timer);self.render_timer=None
        self.original=None;self.preview=None;self.points=[];self.masks={};self.rendering=False
        self.reset_history();self.canvas.delete('all')

    def set_prepared(self,prepared,masks=None):
        previous=(self.original,self.preview,self.masks,self.points,self.scale,self.rotation)
        self.original,self.preview=prepared
        self.masks=deepcopy(masks) if masks is not None else {'mole':[],'skin':[],'exclude':[],'patches':[]}
        self.points=[];self.rotation=0;self.undo_stack=[];self.redo_stack=[];self.selected_handle=None
        try:self.fit()
        except Exception:
            self.original,self.preview,self.masks,self.points,self.scale,self.rotation=previous
            self.render();raise

    def fit(self):
        if self.original:
            w,h=self.original.size
            if self.rotation%2:w,h=h,w
            self.scale=min(max(1,self.canvas.winfo_width())/w,max(1,self.canvas.winfo_height())/h,1.)
            self.render()

    def zoom(self,factor):
        if self.original:
            self.scale=max(.03,min(self.scale*factor,4.,6000/max(self.original.size)))
            self.render()

    def rotate(self):
        if self.locked or not self.original:return
        self.rotation=(self.rotation+1)%4;self.fit()

    def render(self):
        if self.original is None:return
        w,h=self.original.size
        if self.rotation%2:w,h=h,w
        size=(max(1,int(w*self.scale)),max(1,int(h*self.scale)))
        self.render_token+=1;token=self.render_token
        if self.render_timer:self.after_cancel(self.render_timer);self.render_timer=None
        self.canvas.configure(scrollregion=(0,0,*size))
        def publish(image):
            if token!=self.render_token:return
            self.rendering=False
            self.tkimage=ImageTk.PhotoImage(image)
            self.canvas.delete('raster');self.canvas.create_image(0,0,image=self.tkimage,anchor='nw',tags='raster')
            self.canvas.tag_lower('raster');self.outlines()
        base=self.preview if self.preview is not None and max(size)<=1600 else self.original
        if self.executor and max(size)>1600:
            gc.collect()  # Retired Tk callback cycles must be collected on their owning thread.
            self.rendering=True;self.canvas.delete('raster')
            self.canvas.create_text(10,10,text='正在准备显示，标记暂时锁定…',anchor='nw',fill='white',tags='raster')
            future=self.executor.submit(display_image,base,self.rotation,size)
            def poll():
                self.render_timer=None
                if token!=self.render_token:return
                if not future.done():self.render_timer=self.after(25,poll);return
                try:publish(future.result())
                except Exception:
                    self.canvas.delete('raster')
                    self.canvas.create_text(10,10,text='显示未完成，请点击适合或缩小重试。',anchor='nw',fill='white',tags='raster')
            self.render_timer=self.after(25,poll)
        else:publish(display_image(base,self.rotation,size))
        self.outlines()

    def projected(self,point):
        return [v*self.scale for v in display_point(point,self.original.size,self.rotation)]

    def outlines(self):
        self.canvas.delete('mark')
        if self.original is None:return
        for key,color in [('mole','#ffcb57'),('skin','#59dfbf')]:
            points=self.masks.get(key,[])
            if len(points)>=3:self.canvas.create_polygon(*[v for p in points for v in self.projected(p)],outline=color,fill='',width=2,tags='mark')
        for poly in self.masks.get('exclude',[]):
            if len(poly)>=3:self.canvas.create_polygon(*[v for p in poly for v in self.projected(p)],outline='#ff6c8b',fill='',width=2,tags='mark')
        for i,r in enumerate(self.masks.get('patches',[])):
            a,b=self.projected(r[:2]),self.projected(r[2:])
            self.canvas.create_rectangle(*a,*b,outline='#74b6ff',width=2,tags='mark')
            caption=str(i+1)+((': '+self.patch_names[i]) if i<len(self.patch_names) else '')
            self.canvas.create_text(min(a[0],b[0])+5,min(a[1],b[1])+5,text=caption,fill='#74b6ff',anchor='nw',tags='mark')
        if self.points:
            points=[v for p in self.points for v in self.projected(p)]
            if len(points)>=4:self.canvas.create_line(*points,fill='white',width=2,tags='mark')
        for _,point in self.handles():
            x,y=self.projected(point)
            self.canvas.create_oval(x-3,y-3,x+3,y+3,fill='white',tags='mark')

    def handles(self):
        if self.points:return [(('points',i),point) for i,point in enumerate(self.points)]
        if self.mode in (1,2):
            key='mole' if self.mode==1 else 'skin'
            return [((key,i),point) for i,point in enumerate(self.masks.get(key,[]))]
        if self.mode==3:
            return [(('exclude',j,i),p) for j,poly in enumerate(self.masks.get('exclude',[])) for i,p in enumerate(poly)]
        if self.mode==4:
            return [(('patches',j,i),rect[i:i+2]) for j,rect in enumerate(self.masks.get('patches',[])) for i in (0,2)]
        return []

    def coords(self,event):
        w,h=self.original.size
        point=original_point([self.canvas.canvasx(event.x)/self.scale,self.canvas.canvasy(event.y)/self.scale],self.original.size,self.rotation)
        return [max(0,min(w-1,point[0])),max(0,min(h-1,point[1]))]

    def snapshot(self):return deepcopy((self.masks,self.points,self.mode))
    def remember(self):
        self.undo_stack.append(self.snapshot());self.undo_stack=self.undo_stack[-100:];self.redo_stack=[]
    def reset_history(self):
        self.undo_stack=[];self.redo_stack=[];self.selected_handle=None

    def click(self,event):
        if self.original is None or self.locked or self.rendering:return
        self.canvas.focus_set();self.selected_handle=None
        if self.mode==0:self.canvas.scan_mark(event.x,event.y);return
        x,y=self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)
        for handle,point in self.handles():
            px,py=self.projected(point)
            if (px-x)**2+(py-y)**2<=81:
                self.remember();self.handle=handle;self.selected_handle=handle;return
        self.remember()
        if self.mode==4:self.start=self.coords(event)
        else:self.points.append(self.coords(event));self.outlines();self.changed()

    def drag(self,event):
        if self.locked or self.rendering or self.original is None:return
        if self.mode==0:self.canvas.scan_dragto(event.x,event.y,gain=1);return
        if self.handle:
            point=self.coords(event);key,*indices=self.handle
            if key=='points':self.points[indices[0]]=point
            elif key=='exclude':self.masks[key][indices[0]][indices[1]]=point
            elif key=='patches':self.masks[key][indices[0]][indices[1]:indices[1]+2]=point
            else:self.masks[key][indices[0]]=point
            self.outlines()

    def release(self,event):
        if self.locked or self.rendering:return
        if self.handle:
            if self.handle[0]=='patches':
                rect=self.masks['patches'][self.handle[1]];x1,y1,x2,y2=rect
                if x1==x2 or y1==y2:self.undo();self.handle=None;return
                rect[:]=[min(x1,x2),min(y1,y2),max(x1,x2),max(y1,y2)]
            self.handle=None;self.outlines();self.changed();return
        if self.original is not None and self.mode==4 and self.start:
            end=self.coords(event);x,y=self.start
            if x!=end[0] and y!=end[1]:
                self.masks.setdefault('patches',[]).append([min(x,end[0]),min(y,end[1]),max(x,end[0]),max(y,end[1])])
                self.changed()
            self.start=None;self.outlines()

    def finish(self):
        if self.locked or self.rendering or self.mode not in (1,2,3) or len(self.points)<3:return
        self.remember()
        if self.mode==3:self.masks.setdefault('exclude',[]).append(self.points[:])
        else:self.masks['mole' if self.mode==1 else 'skin']=self.points[:]
        self.points=[];self.outlines();self.changed()

    def delete_vertex(self):
        if self.locked or not self.selected_handle:return
        self.remember();key,*indices=self.selected_handle
        if key=='points':self.points.pop(indices[0])
        elif key=='patches':self.masks[key].pop(indices[0])
        elif key=='exclude':
            poly=self.masks[key][indices[0]]
            if len(poly)<=3:self.masks[key].pop(indices[0])
            else:poly.pop(indices[1])
        else:
            poly=self.masks[key]
            if len(poly)<=3:self.points=poly[:];self.points.pop(indices[0]);self.masks[key]=[]
            else:poly.pop(indices[0])
        self.selected_handle=None;self.outlines();self.changed()

    def undo(self):
        if self.locked:return
        self.redo_stack.append(self.snapshot())
        if self.undo_stack:self.masks,self.points,self.mode=self.undo_stack.pop()
        elif self.points:self.points.pop()
        elif self.mode==4 and self.masks.get('patches'):self.masks['patches'].pop()
        elif self.mode==3 and self.masks.get('exclude'):self.masks['exclude'].pop()
        elif self.mode in (1,2):
            key='mole' if self.mode==1 else 'skin';self.points=self.masks.get(key,[])[:-1];self.masks[key]=[]
        self.selected_handle=None;self.outlines();self.changed()

    def redo(self):
        if self.locked or not self.redo_stack:return
        self.undo_stack.append(self.snapshot());self.masks,self.points,self.mode=self.redo_stack.pop()
        self.selected_handle=None;self.outlines();self.changed()

    def set_mode(self,mode):
        if mode==self.mode:return
        if self.points:raise ValueError('请先完成多边形或撤销未完成的点，再切换标记工具')
        self.mode=mode;self.selected_handle=None;self.outlines()
