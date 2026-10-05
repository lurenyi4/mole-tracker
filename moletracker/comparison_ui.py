"""Linked visual browsing; zoom ratios do not imply comparable physical size."""
import tkinter as tk
from tkinter import ttk
from .photo_canvas import PhotoCanvas, prepare_photo
from .store import Store


def local_crop(image,row):
    polygon=row['masks'].get('mole',[])
    if not polygon:return image
    xs,ys=zip(*polygon);pad=max(max(xs)-min(xs),max(ys)-min(ys))*.5
    return image.crop((max(0,int(min(xs)-pad)),max(0,int(min(ys)-pad)),
                       min(image.width,int(max(xs)+pad)+1),min(image.height,int(max(ys)+pad)+1)))


def interactive_compare(app):
    rows=app.history_selected(2);data_root=app.store.root
    def work():
        store=Store(data_root);prepared=[]
        try:
            for index,row in enumerate(rows):
                app.progress('读取对比原件',index,2)
                original,preview=prepare_photo(store.photo_path(row['photo_id']))
                crop=local_crop(original,row);thumb=crop.copy();thumb.thumbnail((1600,1600))
                prepared.append(((original,preview),(crop,thumb)))
            return prepared
        finally:store.close()
    def complete(prepared):
        dialog=tk.Toplevel(app.root);dialog.title('联动目视对比');dialog.geometry('1100x760');dialog.minsize(760,500)
        ttk.Label(dialog,text='显示比例是照片像素比例；两次拍摄距离、分辨率与光照可能不同，不能据此判断物理尺寸。',wraplength=1000).pack(fill='x',padx=10,pady=8)
        bar=ttk.Frame(dialog);bar.pack(fill='x',padx=10)
        local=tk.BooleanVar(value=True);linked=tk.BooleanVar(value=True)
        panels=ttk.Frame(dialog);panels.pack(fill='both',expand=True)
        canvases=[];labels=[]
        for row in rows:
            panel=ttk.Frame(panels,padding=8);panel.pack(side='left',fill='both',expand=True)
            label=ttk.Label(panel);label.pack(fill='x');labels.append(label)
            canvas=PhotoCanvas(panel,lambda:None,app.executor);canvas.pack(fill='both',expand=True);canvases.append(canvas)
            notes=tk.Text(panel,height=4,wrap='word');notes.pack(fill='x');notes.insert('1.0',row['notes'] or '无拍摄备注');notes.configure(state='disabled')
        def captions():
            for label,canvas,row in zip(labels,canvases,rows):label.configure(text=f'{row["month"]} · 显示 {canvas.scale*100:.1f}% · '+('局部' if local.get() else '原图'))
        def fit():
            for canvas in canvases:canvas.fit()
            captions()
        def zoom(factor):
            for canvas in canvases:canvas.zoom(factor)
            captions()
        def change_view():
            for canvas,images in zip(canvases,prepared):canvas.set_prepared(images[1 if local.get() else 0])
            captions()
        ttk.Checkbutton(bar,text='显示标记附近局部',variable=local,command=change_view).pack(side='left')
        ttk.Checkbutton(bar,text='联动拖动',variable=linked).pack(side='left')
        for label,command in [('缩小',lambda:zoom(.8)),('放大',lambda:zoom(1.25)),('适合',fit)]:ttk.Button(bar,text=label,command=command).pack(side='left',padx=4)
        for index,canvas in enumerate(canvases):
            def drag(event,index=index):
                source=canvases[index];source.drag(event)
                if linked.get():
                    other=canvases[1-index]
                    other.canvas.xview_moveto(source.canvas.xview()[0]);other.canvas.yview_moveto(source.canvas.yview()[0])
            canvas.canvas.bind('<B1-Motion>',drag)
        dialog.update_idletasks();change_view()
    app.run_job('准备联动对比',work,complete)
