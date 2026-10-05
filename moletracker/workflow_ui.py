"""Photo selection and explicit tracking controls for the journal editor."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from .store import Store
from .photo_canvas import PhotoCanvas, prepare_photo


def tracking_dialog(app):
    if not app.mole:raise ValueError('请先选择稳定 ID')
    row=next(m for m in app.store.moles() if m['id']==app.mole)
    dialog=tk.Toplevel(app.root);dialog.title('定位与追踪范围');dialog.transient(app.root);dialog.grab_set()
    ttk.Label(dialog,text='纳入月份表示开始记录，不表示新生日期。\n归档从填写月份起生效，历史原件和观察保留。').pack(padx=16,pady=10)
    fields=[]
    for label,value in [('纳入月份 YYYY-MM（旧资料留空表示未限定）',row['start_month']),('归档月份 YYYY-MM（留空表示继续追踪）',row['end_month'])]:
        ttk.Label(dialog,text=label).pack(anchor='w',padx=16)
        entry=ttk.Entry(dialog,width=50);entry.insert(0,value);entry.pack(padx=16,pady=4);fields.append(entry)
    photos=app.store.rows("SELECT p.id,s.month,COALESCE(n.filename,substr(p.hash,1,8)) AS filename FROM photos p JOIN sessions s ON s.id=p.session_id LEFT JOIN photo_names n ON n.photo_id=p.id WHERE p.role='overview' ORDER BY s.month DESC,p.created DESC")
    ttk.Label(dialog,text='定位概览（可选以前月份）').pack(anchor='w',padx=16)
    selector=ttk.Combobox(dialog,state='readonly',width=56,values=['未关联']+[p['month']+' · '+p['filename'] for p in photos]);selector.pack(padx=16,pady=5)
    selector.current(next((i+1 for i,p in enumerate(photos) if p['id']==row['overview_photo']),0))
    def save():
        photo=photos[selector.current()-1]['id'] if selector.current()>0 else None
        app.store.set_tracking(row['id'],fields[0].get().strip(),fields[1].get().strip(),photo)
        app.refresh_moles();dialog.destroy();app.status.set('定位关联与追踪范围已保存。')
    ttk.Button(dialog,text='保存范围与定位',command=lambda:app.safe(save)).pack(pady=12)


def show_overview(app):
    if not app.mole:raise ValueError('请先选择稳定 ID')
    mole=next(m for m in app.store.moles() if m['id']==app.mole)
    photo=mole['overview_photo'];caption='关联定位概览'
    if not photo:
        history=app.store.observations(app.mole)
        if not history:raise ValueError('尚无定位概览或历史观察，请先关联概览照片')
        photo=history[-1]['photo_id'];caption='上次观察（尚未关联概览）'
    data_root=app.store.root
    def work():
        store=Store(data_root)
        try:app.progress('读取定位参考');return prepare_photo(store.photo_path(photo))
        finally:store.close()
    def complete(prepared):
        dialog=tk.Toplevel(app.root);dialog.title(caption+' · '+mole['location']);dialog.geometry('850x600')
        ttk.Label(dialog,text=mole['id'][:8]+' · '+mole['location']+' · '+caption).pack()
        canvas=PhotoCanvas(dialog,lambda:None,app.executor);canvas.pack(fill='both',expand=True)
        for text,factor in [('缩小',.8),('放大',1.25)]:ttk.Button(dialog,text=text,command=lambda f=factor:canvas.zoom(f)).pack(side='left')
        dialog.update_idletasks();canvas.set_prepared(prepared)
    app.run_job('打开定位参考',work,complete)


def pick_photo(app,page=0):
    app.require_session();rows=app.store.photos(app.session)
    if not rows:raise ValueError('本月尚未导入照片')
    page=max(0,min(page,(len(rows)-1)//24));batch=rows[page*24:(page+1)*24];data_root=app.store.root
    def work():
        store=Store(data_root);result=[]
        try:
            for index,row in enumerate(batch):
                app.progress('生成缩略图',index,len(batch))
                try:
                    path=store.photo_path(row['id'])
                    with Image.open(path) as original:
                        thumb=original.convert('RGB');thumb.thumbnail((150,110))
                    result.append((row,thumb,None))
                except (OSError,ValueError) as exc:result.append((row,None,str(exc)))
            return result
        finally:store.close()
    def complete(result):
        if app.photo_picker and app.photo_picker.winfo_exists():app.photo_picker.destroy()
        dialog=tk.Toplevel(app.root);app.photo_picker=dialog;dialog.title('本月缩略图选片');dialog.geometry('780x620')
        viewport=tk.Canvas(dialog,highlightthickness=0);scroll=ttk.Scrollbar(dialog,orient='vertical',command=viewport.yview)
        scroll.pack(side='right',fill='y');viewport.pack(fill='both',expand=True);viewport.configure(yscrollcommand=scroll.set)
        content=ttk.Frame(viewport);viewport.create_window(0,0,window=content,anchor='nw')
        content.bind('<Configure>',lambda e:viewport.configure(scrollregion=viewport.bbox('all')))
        dialog.thumbnails=[]
        for index,(row,thumb,error) in enumerate(result):
            box=ttk.Frame(content,padding=6);box.grid(row=index//4,column=index%4,sticky='n')
            if thumb:
                photo=ImageTk.PhotoImage(thumb);dialog.thumbnails.append(photo)
                def choose(key=row['id']):
                    app.refresh_photos();i=next(i for i,p in enumerate(app.photo_rows) if p['id']==key)
                    app.photo_list.selection_clear(0,'end');app.photo_list.selection_set(i);app.safe(app.select_photo);dialog.destroy()
                ttk.Button(box,image=photo,command=choose).pack()
            ttk.Label(box,text=row['filename']+'\n'+('概览' if row['role']=='overview' else '近照')+(('\n'+error) if error else ''),wraplength=165).pack()
        bar=ttk.Frame(dialog);bar.pack(fill='x')
        ttk.Label(bar,text=f'第 {page+1}/{(len(rows)-1)//24+1} 页；点击缩略图打开').pack(side='left')
        for label,number,enabled in [('上一页',page-1,page>0),('下一页',page+1,(page+1)*24<len(rows))]:
            ttk.Button(bar,text=label,state='normal' if enabled else 'disabled',command=lambda n=number:app.safe(lambda:pick_photo(app,n))).pack(side='right')
    app.run_job('准备缩略图',work,complete)
