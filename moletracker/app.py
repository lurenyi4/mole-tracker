"""Native, offline Tk application. All image coordinates refer to stored raster."""
import argparse
from datetime import date
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk, font as tkfont
import numpy as np
from PIL import Image, ImageTk
from .store import Store, restore_backup, REGIONS, COVERAGE
from .color import analysis_image, polygon_mask, patch_medians, fit_reference, measure, delta, reference_xyz
from .reference_ui import open_reference_wizard

STATE_NAMES={'pending':'待检查','reviewed':'已目视检查','not_photographed':'未拍摄 / 不方便','needs_retake':'需要重拍'}
STATUS_NAMES={'comparable':'可比较（实验）','uncalibrated':'未校准','retake':'待重拍'}
MODE_NAMES=('浏览 / 拖动','痣内部多边形','邻近正常皮肤','排除毛发 / 反光','色卡块矩形（按配置顺序）')


class PhotoCanvas(ttk.Frame):
    def __init__(self,parent,changed):
        super().__init__(parent);self.changed=changed
        self.canvas=tk.Canvas(self,bg='#202832',highlightthickness=0,width=500,height=120)
        sy=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        sx=ttk.Scrollbar(self,orient='horizontal',command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=sx.set,yscrollcommand=sy.set)
        self.canvas.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
        self.rowconfigure(0,weight=1);self.columnconfigure(0,weight=1)
        self.original=None;self.patch_names=[];self.scale=1.;self.mode=0;self.points=[];self.masks={};self.start=None
        self.canvas.bind('<Button-1>',self.click)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Button-3>',lambda e:self.finish())

    def load(self,path,masks=None):
        # Decode first; failure must not pair an old raster/mask with a new ID.
        with Image.open(path) as image:
            prepared=image.convert('RGB')
        previous=(self.original,self.masks,self.points,self.scale)
        self.original=prepared
        self.masks=masks or {'mole':[],'skin':[],'exclude':[],'patches':[]}
        self.points=[]
        try:
            self.fit()
        except Exception:
            self.original,self.masks,self.points,self.scale=previous
            self.render()
            raise

    def fit(self):
        if self.original:
            width=self.canvas.winfo_width();height=self.canvas.winfo_height()
            self.scale=min((width if width>1 else 400)/self.original.width,
                           (height if height>1 else 300)/self.original.height,1.)
            self.render()
    def zoom(self,factor):
        if self.original:
            # Limit display allocation, independent of full-resolution measurement.
            self.scale=max(.03,min(self.scale*factor,4.,6000/max(self.original.size)))
            self.render()
    def render(self):
        if self.original is None:return
        w,h=self.original.size;size=(max(1,int(w*self.scale)),max(1,int(h*self.scale)))
        self.tkimage=ImageTk.PhotoImage(self.original.resize(size,Image.Resampling.LANCZOS))
        self.canvas.delete('all');self.canvas.create_image(0,0,image=self.tkimage,anchor='nw')
        self.canvas.configure(scrollregion=(0,0,*size));self.outlines()
    def outlines(self):
        self.canvas.delete('mark')
        for key,color in [('mole','#ffcb57'),('skin','#59dfbf')]:
            points=self.masks.get(key,[])
            if len(points)>=3:self.canvas.create_polygon(*[v*self.scale for p in points for v in p],outline=color,fill='',width=2,tags='mark')
        for poly in self.masks.get('exclude',[]):
            self.canvas.create_polygon(*[v*self.scale for p in poly for v in p],outline='#ff6c8b',fill='',width=2,tags='mark')
        for i,r in enumerate(self.masks.get('patches',[])):
            self.canvas.create_rectangle(*[v*self.scale for v in r],outline='#74b6ff',width=2,tags='mark')
            self.canvas.create_text(r[0]*self.scale+5,r[1]*self.scale+5,text=str(i+1)+((': '+self.patch_names[i]) if i<len(self.patch_names) else ''),fill='#74b6ff',anchor='nw',tags='mark')
        if self.points:
            points=[v*self.scale for p in self.points for v in p]
            if len(points)>=4:self.canvas.create_line(*points,fill='white',width=2,tags='mark')
            for x,y in self.points:self.canvas.create_oval(x*self.scale-3,y*self.scale-3,x*self.scale+3,y*self.scale+3,fill='white',tags='mark')
    def coords(self,event):
        w,h=self.original.size
        return [max(0,min(w-1,self.canvas.canvasx(event.x)/self.scale)),max(0,min(h-1,self.canvas.canvasy(event.y)/self.scale))]
    def click(self,event):
        if self.original is None:return
        if self.mode==0:self.canvas.scan_mark(event.x,event.y)
        elif self.mode==4:self.start=self.coords(event)
        else:self.points.append(self.coords(event));self.outlines();self.changed()
    def drag(self,event):
        if self.mode==0:self.canvas.scan_dragto(event.x,event.y,gain=1)
    def release(self,event):
        if self.original is not None and self.mode==4 and self.start:
            end=self.coords(event);x,y=self.start
            self.masks.setdefault('patches',[]).append([min(x,end[0]),min(y,end[1]),max(x,end[0]),max(y,end[1])])
            self.start=None;self.outlines();self.changed()
    def finish(self):
        if self.mode not in (1,2,3) or len(self.points)<3:return
        if self.mode==3:self.masks.setdefault('exclude',[]).append(self.points[:])
        else:self.masks['mole' if self.mode==1 else 'skin']=self.points[:]
        self.points=[];self.outlines();self.changed()
    def undo(self):
        if self.points:self.points.pop()
        elif self.mode==4 and self.masks.get('patches'):self.masks['patches'].pop()
        elif self.mode==3 and self.masks.get('exclude'):self.masks['exclude'].pop()
        elif self.mode in (1,2):self.masks['mole' if self.mode==1 else 'skin']=[]
        self.outlines();self.changed()
    def set_mode(self,mode):
        self.points=[];self.mode=mode;self.outlines()


class App:
    def __init__(self,root,store):
        self.root=root;self.store=store;self.session=None;self.photo=None;self.mole=None;self.dirty=False;self.profile=None
        root.title('痣迹 · 本地照片记录');root.geometry('1400x900');root.minsize(1100,760)
        family=next((f for f in ('Noto Sans CJK SC','Microsoft YaHei','PingFang SC') if f in tkfont.families(root)), 'sans-serif')
        for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont','TkCaptionFont'):
            tkfont.nametofont(name).configure(family=family,size=11)
        style=ttk.Style(root);style.theme_use('clam')
        style.configure('.',font=(family,11));style.configure('TButton',padding=(8,5))
        style.configure('Title.TLabel',font=(family,18,'bold'))
        head=ttk.Frame(root,padding=12);head.pack(fill='x')
        ttk.Label(head,text='痣迹  /  私密本地照片日志',style='Title.TLabel').pack(side='left')
        for label,command in [('拍摄协议',self.guide),('备份到本地',self.backup),('恢复副本',self.restore)]:
            ttk.Button(head,text=label,command=lambda c=command:self.safe(c)).pack(side='right',padx=3)
        tk.Label(root,text='不提供诊断或健康保证。新出现、变化、瘙痒或出血不要等到下个月，请及时咨询皮肤科。',bg='#fff0da',fg='#633e15',pady=8).pack(fill='x')
        self.status=tk.StringVar(value='照片只在本机保存。原件含 EXIF / 位置等元数据；备份未加密，请存放在非同步安全目录。')
        self.status_label=ttk.Label(root,textvariable=self.status,padding=8,wraplength=1000)
        self.status_label.pack(side='bottom',fill='x')
        self.tabs=ttk.Notebook(root);self.tabs.pack(fill='both',expand=True,padx=12,pady=10)
        self.editor=ttk.Frame(self.tabs,padding=10);self.review=ttk.Frame(self.tabs,padding=10);self.cover=ttk.Frame(self.tabs,padding=10)
        self.tabs.add(self.editor,text='  1  导入与标记  ');self.tabs.add(self.review,text='  2  历史与对比  ');self.tabs.add(self.cover,text='  3  覆盖清单  ')
        self.build_editor();self.build_review();self.build_coverage()
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh_sessions();self.refresh_moles()

    def safe(self,fn):
        try:return fn()
        except Exception as exc:messagebox.showerror('未完成',str(exc),parent=self.root)
    def mark_dirty(self):self.dirty=True
    def discard(self):
        if self.dirty and not messagebox.askyesno('未保存标记','切换会丢弃未保存的标记，继续吗？',parent=self.root):return False
        return True
    def selected(self,widget,rows):
        indices=widget.curselection();return rows[indices[0]] if indices else None

    def build_editor(self):
        side=ttk.Frame(self.editor,width=240);side.pack(side='left',fill='y',padx=(0,12))
        ttk.Label(side,text='月份').pack(anchor='w')
        self.month_combo=ttk.Combobox(side,state='readonly',width=27);self.month_combo.pack(fill='x')
        self.month_combo.bind('<<ComboboxSelected>>',lambda e:self.safe(self.select_session))
        ttk.Button(side,text='＋ 新建月份',command=lambda:self.safe(self.new_session)).pack(fill='x',pady=5)
        ttk.Label(side,text='稳定 ID · 位置（不是新生日期）').pack(anchor='w',pady=(12,3))
        self.mole_list=tk.Listbox(side,width=30,height=8,exportselection=False);self.mole_list.pack(fill='both',expand=True)
        self.mole_list.bind('<<ListboxSelect>>',lambda e:self.safe(self.select_mole))
        row=ttk.Frame(side);row.pack(fill='x',pady=5)
        ttk.Button(row,text='＋ 新记录',command=lambda:self.safe(self.add_mole)).pack(side='left')
        ttk.Button(row,text='修改位置',command=lambda:self.safe(self.edit_mole)).pack(side='left')
        ttk.Label(side,text='本月照片 · 概览用于定位，近照用于数值').pack(anchor='w',pady=(10,3))
        self.photo_list=tk.Listbox(side,height=5,exportselection=False);self.photo_list.pack(fill='both',expand=True)
        self.photo_list.bind('<<ListboxSelect>>',lambda e:self.safe(self.select_photo))
        row=ttk.Frame(side);row.pack(fill='x',pady=5)
        ttk.Button(row,text='导入概览',command=lambda:self.safe(lambda:self.import_photos('overview'))).pack(side='left')
        ttk.Button(row,text='导入近照',command=lambda:self.safe(lambda:self.import_photos('detail'))).pack(side='left')
        main=ttk.Frame(self.editor);main.pack(side='left',fill='both',expand=True)
        bar=ttk.Frame(main);bar.pack(fill='x')
        self.mode=ttk.Combobox(bar,values=MODE_NAMES,state='readonly',width=25);self.mode.current(0);self.mode.pack(side='left')
        self.mode.bind('<<ComboboxSelected>>',lambda e:self.canvas.set_mode(self.mode.current()))
        for label,command in [('完成多边形',lambda:self.canvas.finish()),('撤销',lambda:self.canvas.undo()),('−',lambda:self.canvas.zoom(.8)),('＋',lambda:self.canvas.zoom(1.25)),('适合',lambda:self.canvas.fit())]:
            ttk.Button(bar,text=label,command=command).pack(side='left',padx=2)
        ttk.Label(main,text='左键逐点标记，完成多边形；色卡用拖动矩形。浏览模式拖动平移。原始方向显示，不自动旋转。').pack(anchor='w',pady=5)
        self.canvas=PhotoCanvas(main,self.mark_dirty);self.canvas.pack(fill='both',expand=True)
        controls=ttk.Frame(main);controls.pack(fill='x',pady=6)
        self.profile_label=tk.StringVar(value='未载入参考配置：只能保存照片，不能生成可比较数值')
        ttk.Button(controls,text='设置实体色卡',command=lambda:self.safe(lambda:open_reference_wizard(self.root,self.use_profile))).pack(side='left')
        ttk.Button(controls,text='载入配置',command=lambda:self.safe(self.load_profile)).pack(side='left')
        ttk.Button(controls,text='色块顺序',command=lambda:self.safe(self.patch_order)).pack(side='left')
        ttk.Label(controls,textvariable=self.profile_label,wraplength=420).pack(side='left',padx=10)
        flags=ttk.Frame(main);flags.pack(fill='x')
        self.srgb=tk.BooleanVar();self.ordinary=tk.BooleanVar(value=True)
        ttk.Checkbutton(flags,text='无 ICC 时：我已确认来源是 sRGB',variable=self.srgb,command=self.mark_dirty).pack(side='left')
        ttk.Checkbutton(flags,text='普通皮肤（关闭则不计算正常皮肤与 D）',variable=self.ordinary,command=self.mark_dirty).pack(side='left')
        self.qc=[]
        for caption in ['已放大检查清晰度与足够细节','无局部阴影、反光、裁切或明显 HDR','色卡与目标同平面同光照，配置对应实物','身份已核对；掩膜排除毛发、边界和反光']:
            var=tk.BooleanVar();self.qc.append(var)
            ttk.Checkbutton(main,text=caption,variable=var,command=self.mark_dirty).pack(anchor='w')
        ttk.Label(main,text='观察 / 重拍原因 / 设备与灯光变化（选填，但失败需说明）').pack(anchor='w')
        self.notes=tk.Text(main,height=2,wrap='word');self.notes.pack(fill='x');self.notes.bind('<KeyRelease>',lambda e:self.mark_dirty())
        actions=ttk.Frame(main);actions.pack(fill='x',pady=5)
        ttk.Button(actions,text='检查并保存可比较记录',command=lambda:self.safe(self.save_comparable)).pack(side='left')
        ttk.Button(actions,text='保存照片 / 待重拍（无数值）',command=lambda:self.safe(self.save_photo_only)).pack(side='left',padx=8)

    def build_review(self):
        ttk.Label(self.review,text='选择同一 ID 的两条记录对比。数值仅描述照片，不能诊断；设备、照明与周围皮肤变化仍会影响解释。').pack(anchor='w')
        self.history=ttk.Treeview(self.review,columns=('month','quality','l','skin','d','note'),show='headings',height=8,selectmode='extended')
        for name,label,width in [('month','月份',100),('quality','状态',100),('l','痣 L*',85),('skin','皮肤 L*',85),('d','D',85),('note','观察 / 原因',550)]:
            self.history.heading(name,text=label);self.history.column(name,width=width)
        self.history.pack(fill='x',pady=8)
        bar=ttk.Frame(self.review);bar.pack(fill='x')
        ttk.Button(bar,text='对比所选两条',command=lambda:self.safe(self.compare)).pack(side='left')
        ttk.Button(bar,text='载入所选标记，另存新观察',command=lambda:self.safe(self.load_observation)).pack(side='left',padx=6)
        ttk.Button(bar,text='纠正所选观察的身份',command=lambda:self.safe(self.correct)).pack(side='left')
        self.comparison=tk.StringVar(value='请先在工作台选择一个稳定 ID')
        ttk.Label(self.review,textvariable=self.comparison,wraplength=1150,padding=10).pack(fill='x')
        self.images_frame=ttk.Frame(self.review);self.images_frame.pack(fill='both',expand=True)
        self.compare_labels=[ttk.Label(self.images_frame,anchor='center') for _ in range(2)]
        for label in self.compare_labels:label.pack(side='left',fill='both',expand=True,padx=5)

    def build_coverage(self):
        self.cover_scroll=tk.Canvas(self.cover,highlightthickness=0)
        scrollbar=ttk.Scrollbar(self.cover,orient='vertical',command=self.cover_scroll.yview)
        scrollbar.pack(side='right',fill='y')
        self.cover_scroll.pack(side='left',fill='both',expand=True)
        self.cover_scroll.configure(yscrollcommand=scrollbar.set)
        self.cover_content=ttk.Frame(self.cover_scroll)
        window=self.cover_scroll.create_window(0,0,window=self.cover_content,anchor='nw')
        self.cover_content.bind('<Configure>',lambda e:self.cover_scroll.configure(scrollregion=self.cover_scroll.bbox('all')))
        self.cover_scroll.bind('<Configure>',lambda e:self.cover_scroll.itemconfigure(window,width=e.width))
        ttk.Label(self.cover_content,text='目视检查覆盖与已拍摄是不同的。未拍摄 ≠ 没有痣；新记录 ≠ 新长出。可选区域不要求私密照片。').pack(anchor='w',pady=10)
        self.cover_vars={}
        for region in REGIONS:
            row=ttk.Frame(self.cover_content);row.pack(fill='x',pady=3)
            ttk.Label(row,text=region,width=38).pack(side='left')
            combo=ttk.Combobox(row,values=list(STATE_NAMES.values()),state='readonly',width=25);combo.current(0);combo.pack(side='left')
            combo.bind('<<ComboboxSelected>>',lambda e,r=region,c=combo:self.safe(lambda:self.store.set_coverage(self.require_session(),r,COVERAGE[c.current()])))
            self.cover_vars[region]=combo
        self.cover_summary=tk.StringVar()
        ttk.Label(self.cover_content,textvariable=self.cover_summary,wraplength=970,padding=8).pack(anchor='w')
        ttk.Label(self.cover_content,text='建议路线：头面/头皮 → 前侧躯干 → 背部 → 四肢/褶皱 → 手掌/指甲 → 脚底/趾甲\n目标：20–30 处的拍摄、导入、复核 < 1 小时，尚需真实试用验证。\n不要为了完成清单接受模糊、阴影或缺乏参考的照片；明确记录重拍。',wraplength=970).pack(anchor='w',pady=6)

    def refresh_sessions(self):
        self.session_rows=self.store.sessions();self.month_combo['values']=[r['month'] for r in self.session_rows]
        if self.session_rows:
            index=next((i for i,r in enumerate(self.session_rows) if r['id']==self.session),0)
            self.month_combo.current(index);self.session=self.session_rows[index]['id'];self.refresh_photos();self.refresh_coverage()
    def select_session(self):
        index=self.month_combo.current()
        if not self.discard():
            self.month_combo.current(next(i for i,r in enumerate(self.session_rows) if r['id']==self.session));return
        self.session=self.session_rows[index]['id'];self.photo=None;self.clear_canvas();self.refresh_photos();self.refresh_coverage()
    def new_session(self):
        month=simpledialog.askstring('新建月份','月份 YYYY-MM',initialvalue=date.today().strftime('%Y-%m'),parent=self.root)
        if month and self.discard():self.session=self.store.create_session(month);self.photo=None;self.clear_canvas();self.refresh_sessions()
    def require_session(self):
        if not self.session:raise ValueError('请先新建或选择月份')
        return self.session
    def refresh_moles(self):
        self.mole_rows=self.store.moles();self.mole_list.delete(0,'end')
        for row in self.mole_rows:self.mole_list.insert('end',row['id'][:8]+' · '+row['location'])
        if self.mole:
            for i,row in enumerate(self.mole_rows):
                if row['id']==self.mole:self.mole_list.selection_set(i)
        self.refresh_history()
        if self.session:self.refresh_coverage()
    def select_mole(self):
        row=self.selected(self.mole_list,self.mole_rows)
        if row and row['id']!=self.mole:
            if not self.discard():self.refresh_moles();return
            self.mole=row['id'];self.reset_marks(keep_patches=True);self.refresh_history()
    def mole_dialog(self,existing=None):
        dialog=tk.Toplevel(self.root);dialog.title('位置与稳定身份');dialog.transient(self.root);dialog.grab_set()
        ttk.Label(dialog,text='区域').pack(anchor='w',padx=15,pady=5)
        region=ttk.Combobox(dialog,values=REGIONS,state='readonly',width=40);region.pack(padx=15);region.set(existing['region'] if existing else REGIONS[0])
        ttk.Label(dialog,text='具体位置：左/右 + 解剖标志 + 方位（不要只写顺序）').pack(padx=15,pady=8)
        entry=ttk.Entry(dialog,width=55);entry.pack(padx=15);entry.insert(0,existing['location'] if existing else '')
        def save():
            if existing:
                self.store.edit_mole(existing['id'],region.get(),entry.get())
            else:
                new_id=self.store.add_mole(region.get(),entry.get())
                self.reset_marks()
                self.mole=new_id
            dialog.destroy()
            self.refresh_moles()
        ttk.Button(dialog,text='保存',command=lambda:self.safe(save)).pack(pady=15)
    def add_mole(self):
        if self.discard():
            self.mole_dialog()
    def edit_mole(self):
        row=next((r for r in self.mole_rows if r['id']==self.mole),None)
        if row:self.mole_dialog(row)
    def refresh_photos(self):
        self.photo_rows=self.store.photos(self.session);self.photo_list.delete(0,'end')
        for i,row in enumerate(self.photo_rows):self.photo_list.insert('end',f'{i+1:02d} · {"近照" if row["role"]=="detail" else "概览"} · {row["width"]}×{row["height"]}')
        if self.photo:
            for i,r in enumerate(self.photo_rows):
                if r['id']==self.photo:self.photo_list.selection_set(i)
    def import_photos(self,role):
        self.require_session()
        files=filedialog.askopenfilenames(parent=self.root,title='选择 USB / 本地原件，不会上传',filetypes=[('JPEG / PNG','*.jpg *.jpeg *.png'),('所有文件','*')])
        count=0;errors=[]
        for file in files:
            try:self.store.import_photo(file,self.session,role);count+=1
            except ValueError as exc:errors.append(str(exc))
        self.refresh_photos();self.status.set(f'导入 {count} 张原件；失败 {len(errors)} 张。未上传。')
        if errors:messagebox.showwarning('部分文件未导入','\n'.join(errors[:5]),parent=self.root)
    def select_photo(self):
        row=self.selected(self.photo_list,self.photo_rows)
        if not row or row['id']==self.photo:
            return
        dirty=self.dirty
        if not self.discard():
            self.refresh_photos()
            return
        try:
            self.canvas.load(self.store.photo_path(row['id']))
        except Exception:
            self.dirty=dirty
            self.refresh_photos()
            raise
        self.photo=row['id']
        self.reset_qc()

    def clear_canvas(self):
        self.canvas.original=None;self.canvas.canvas.delete('all');self.canvas.masks={};self.canvas.points=[];self.reset_qc()
    def reset_qc(self):
        for var in self.qc:
            var.set(False)
        self.srgb.set(False)
        self.ordinary.set(True)
        self.notes.delete('1.0','end');self.dirty=False
    def reset_marks(self,keep_patches=False):
        patches=self.canvas.masks.get('patches',[]) if keep_patches else []
        self.canvas.masks={'mole':[],'skin':[],'exclude':[],'patches':patches};self.canvas.points=[];self.canvas.outlines();self.reset_qc()
    def load_profile(self):
        path=filedialog.askopenfilename(parent=self.root,filetypes=[('JSON reference profile','*.json')])
        if not path:return
        if Path(path).stat().st_size>100000:raise ValueError('参考配置文件过大')
        profile=json.loads(Path(path).read_text(encoding='utf-8'))
        reference_xyz(profile)
        self.use_profile(profile)
    def use_profile(self,profile):
        reference_xyz(profile)
        self.qc[2].set(False)
        self.canvas.masks['patches']=[]
        self.canvas.patch_names=profile.get('patch_ids',[])
        self.canvas.outlines()
        self.profile=profile
        self.profile_label.set(f'{profile["name"]} · {len(profile["xyz"])} 块')
        self.mark_dirty()
    def patch_order(self):
        if not self.profile:
            raise ValueError('请先设置实体色卡或载入配置')
        dialog=tk.Toplevel(self.root);dialog.title('色卡块顺序与来源');dialog.geometry('700x500')
        text=tk.Text(dialog,wrap='word',padx=15,pady=15);text.pack(fill='both',expand=True)
        names=self.profile.get('patch_ids',[str(i+1) for i in range(len(self.profile['xyz']))])
        text.insert('1.0',self.profile['name']+'\n来源：'+self.profile['source']+'\n布局：'+self.profile.get('layout','原始配置顺序；请核对实物')+'\n\n'+ '\n'.join(f'{i+1} → {name}' for i,name in enumerate(names)))
        text.configure(state='disabled')
    def require_record(self):
        self.require_session()
        if not self.mole or not self.photo:raise ValueError('请选择稳定 ID 和本月照片')
        if self.canvas.points:raise ValueError('请先完成多边形或撤销未完成的点')
    def record(self,measurement,status,notes):
        masks=json.loads(json.dumps(self.canvas.masks));masks['coordinate_system']='original-unrotated-raster'
        masks['capture_context']={'srgb_assumed':self.srgb.get(),'ordinary_skin':self.ordinary.get()}
        self.store.save_observation(self.mole,self.session,self.photo,masks,measurement,status,notes)
        self.dirty=False;self.refresh_history();self.refresh_coverage();self.status.set('已保存新的观察；原件和旧记录均保留。')
    def save_comparable(self):
        self.require_record()
        if not self.profile:raise ValueError('尚未选择可信色卡配置；请先准备实物色卡与配置。没有配置时可保存未校准照片')
        if not all(v.get() for v in self.qc):raise ValueError('请逐项检查质控；发现问题应重新拍摄，不要勾选不符合的项目')
        image,space=analysis_image(self.store.photo_path(self.photo),self.srgb.get())
        masks=self.canvas.masks;size=(image.shape[1],image.shape[0]);exclude=masks.get('exclude',[])
        mole=polygon_mask(size,masks.get('mole',[]),exclude)
        skin=polygon_mask(size,masks.get('skin',[]),exclude) if self.ordinary.get() else None
        fit=fit_reference(patch_medians(image,masks.get('patches',[])),self.profile)
        result=measure(image,mole,skin,fit,self.ordinary.get());result['color_source']=space;result['manual_qc']=[True]*4
        self.record(result,'comparable',self.notes.get('1.0','end').strip())
    def save_photo_only(self):
        self.require_record()
        notes=self.notes.get('1.0','end').strip()
        reason=simpledialog.askstring('照片记录（无比较数值）','说明缺少参考 / 重拍原因。此记录不代表检查通过。',initialvalue=notes,parent=self.root)
        if not reason:return
        retake=messagebox.askyesno('是否需要重拍','存在模糊、阴影、反光、像素不足等拍摄问题吗？\n是：标记待重拍；否：标记未校准。',parent=self.root)
        self.record(None,'retake' if retake else 'uncalibrated',reason)
    def refresh_coverage(self):
        for region,state in self.store.coverage(self.session).items():self.cover_vars[region].current(COVERAGE.index(state))
        missing=self.store.missing(self.session)
        observations=self.store.rows('SELECT status,COUNT(*) AS n FROM observations WHERE session_id=? GROUP BY status',(self.session,))
        self.cover_summary.set(f'已登记 {len(self.store.moles())} 个稳定 ID；本月尚无照片观察 {len(missing)} 个：'+', '.join(m[:8] for m in missing)+'\n本月观察记录：'+', '.join(f'{STATUS_NAMES[r["status"]]}: {r["n"]}' for r in observations)+'\n已有照片也可能仍需要重拍，不等于已获得可比较记录。')
    def refresh_history(self):
        if not hasattr(self,'history'):return
        self.comparison.set(('当前 ID：'+self.mole+' · 按 Ctrl / Command 选择两条记录') if self.mole else '请先在工作台选择一个稳定 ID')
        for label in self.compare_labels:label.configure(image='')
        self.history.delete(*self.history.get_children());self.history_rows=self.store.observations(self.mole) if self.mole else []
        for row in self.history_rows:
            m=row['measurement'] or {};value=lambda k:'—' if m.get(k) is None else f'{m[k]:.2f}'
            self.history.insert('','end',iid=row['id'],values=(row['month'],STATUS_NAMES[row['status']],value('mole_l'),value('skin_l'),value('d'),row['notes']))
    def history_selected(self,count):
        ids=self.history.selection()
        if len(ids)!=count:raise ValueError(f'请选择 {count} 条观察记录')
        return [r for r in self.history_rows if r['id'] in ids]
    def compare(self):
        before,after=self.history_selected(2)
        change=delta(before['measurement'],after['measurement'])
        if before['month']==after['month']:summary='同月记录：仅目视对比，不展示月度差值。'
        elif change is None:summary='不可作数值比较：需要两条合格记录，且方法、参考配置和组织类型一致。建议核对或重拍。'
        else:summary='后次 − 前次：'+', '.join(f'{dict(mole_l="痣 L*",skin_l="皮肤 L*",d="D")[k]}: {v:+.2f}' if v is not None else f'{k}: 不适用' for k,v in change.items())+'。没有临床阈值；请检查照明、设备和皮肤本身变化。'
        prepared_summary=f'{before["month"]} → {after["month"]} / ID {self.mole}\n{summary}'
        prepared_images=[]
        try:
            for row in [before,after]:
                with Image.open(self.store.photo_path(row['photo_id'])) as im:
                    im=im.convert('RGB')
                    poly=row['masks'].get('mole',[])
                    if poly:
                        xs,ys=zip(*poly)
                        pad=max(max(xs)-min(xs),max(ys)-min(ys))*.5
                        im=im.crop((max(0,min(xs)-pad),max(0,min(ys)-pad),min(im.width,max(xs)+pad),min(im.height,max(ys)+pad)))
                    im.thumbnail((530,380))
                    prepared_images.append(ImageTk.PhotoImage(im))
        except Exception:
            self.compare_images=[]
            for label in self.compare_labels:
                label.configure(image='')
            self.comparison.set('对比不可用：原件无法读取或校验失败。请恢复可信原件后重试。')
            raise
        self.compare_images=prepared_images
        for label,photo in zip(self.compare_labels,prepared_images):
            label.configure(image=photo)
        self.comparison.set(prepared_summary)
    def load_observation(self):
        row=self.history_selected(1)[0]
        dirty=self.dirty
        if not self.discard():
            return
        try:
            self.canvas.load(self.store.photo_path(row['photo_id']),json.loads(json.dumps(row['masks'])))
        except Exception:
            self.dirty=dirty
            raise
        self.session=row['session_id']
        self.photo=row['photo_id']
        self.refresh_sessions()
        self.reset_qc()
        self.notes.insert('1.0',row['notes'])
        self.dirty=True
        context=row['masks'].get('capture_context',{})
        self.srgb.set(context.get('srgb_assumed',False))
        self.ordinary.set(context.get('ordinary_skin',True))
        if row['measurement']:
            measurement=row['measurement']
            self.profile=measurement['fit']['profile']
            self.profile_label.set(self.profile['name'])
            self.canvas.patch_names=self.profile.get('patch_ids',[])
            self.canvas.outlines()
            self.ordinary.set(measurement['ordinary_skin'])
            self.srgb.set(measurement['color_source']=='explicit-sRGB-assumption')
        self.tabs.select(self.editor)

    def correct(self):
        row=self.history_selected(1)[0]
        dialog=tk.Toplevel(self.root);dialog.title('纠正身份，保留审计记录');dialog.transient(self.root);dialog.grab_set()
        choices=self.store.moles();combo=ttk.Combobox(dialog,state='readonly',values=[m['id'][:8]+' · '+m['location'] for m in choices],width=55);combo.pack(padx=15,pady=15)
        reason=ttk.Entry(dialog,width=55);reason.pack(padx=15);reason.insert(0,'视觉核对后更正')
        def save():
            if combo.current()<0:raise ValueError('请选择正确的稳定 ID')
            self.store.correct_identity(row['id'],choices[combo.current()]['id'],reason.get());dialog.destroy();self.refresh_history();self.refresh_coverage()
        ttk.Button(dialog,text='确认纠正',command=lambda:self.safe(save)).pack(pady=15)
    def backup(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='备份含原件与敏感元数据，未加密；请选择非同步目录',defaultextension='.zip',initialfile='mole-backup-'+date.today().isoformat()+'.zip')
        if path:self.store.backup(path);self.status.set('本地备份完成，包含所有原件、标记、参考与历史。未加密，未上传。')
    def restore(self):
        source=filedialog.askopenfilename(parent=self.root,title='选择本地备份',filetypes=[('ZIP','*.zip')])
        if not source:return
        parent=filedialog.askdirectory(parent=self.root,title='选择恢复副本的父目录')
        if not parent:return
        name=simpledialog.askstring('恢复副本','新文件夹名称（不能已存在）',initialvalue='mole-restored',parent=self.root)
        if not name:return
        if name in ('.','..') or '/' in name or '\\' in name:raise ValueError('请输入单一文件夹名称')
        restore_backup(source,Path(parent)/name)
        messagebox.showinfo('恢复成功','副本已恢复。使用 python -m moletracker --data <恢复目录> 打开；当前资料未覆盖。',parent=self.root)
    def guide(self):
        dialog=tk.Toplevel(self.root);dialog.title('拍摄协议与边界');dialog.geometry('850x650')
        widget=tk.Text(dialog,wrap='word',padx=18,pady=18);widget.pack(fill='both',expand=True)
        widget.insert('1.0','固定路线、固定灯光、后置相机 + 三脚架 / 定时器 / 家人帮助。使用 USB 原件。\n概览用于定位，近照用于测量；多痣共图仅在每处细节与参考充分时使用。\n从头皮到脚底逐区记录；手脚缝、指甲、背部与褶皱不要遗漏。可选外部交界区从不要求私密或侵入式拍摄。\n实物哑光多色块色卡需与目标同平面同光照；灰卡不能替代完整标定。没有可信配置时只保存照片。\n阴影、反光、模糊与 HDR 不能靠色卡保证消除。请重拍。\n痣内部黄色、邻近皮肤绿色、排除区粉色、色卡蓝色；标记始终使用原图坐标。\n非普通皮肤（黏膜、指甲等）请关闭普通皮肤选项，不套用正常皮肤 D。\n原件含 EXIF/ICC；本地备份未加密，操作系统同步服务由你管理。\n\n'+self.protocol_text())
        widget.configure(state='disabled')
    def protocol_text(self):
        path=Path(__file__).parents[1]/'docs'/'CAPTURE_PROTOCOL.md'
        return path.read_text(encoding='utf-8') if path.exists() else '详细协议随源代码 docs/CAPTURE_PROTOCOL.md 提供。'
    def close(self):
        if self.discard():self.store.close();self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description='Offline manual mole photo journal')
    parser.add_argument('--data',type=Path,default=Path.home()/'.moletracker',help='Local non-synced data directory')
    args=parser.parse_args();root=tk.Tk();App(root,Store(args.data));root.mainloop()
