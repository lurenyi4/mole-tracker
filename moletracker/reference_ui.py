"""Small native wizard for verified vendor CSV/CGATS files."""
import json
import hashlib
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .reference import read_reference, build_profile, FORMATS


class ReferenceWizard:
    def __init__(self,parent,table,on_created):
        self.table=table;self.on_created=on_created
        self.window=tk.Toplevel(parent);self.window.title('设置实体色卡 · 厂商参考导入')
        self.window.geometry('850x760');self.window.transient(parent);self.window.grab_set()
        body=ttk.Frame(self.window,padding=12);body.pack(fill='both',expand=True)
        ttk.Label(body,text='只导入与你手中型号 / 版本对应的厂商或实测参考。软件不验证来源真实性。\n不选择购买型号，不附带任何商业色卡数值；合成测试值不能用于真实照片。',wraplength=810).pack(anchor='w',pady=(0,8))
        self.fields={}
        labels={'manufacturer':'制造商','model':'实物型号','edition':'版本 / 批次（不能只写新款）','source':'来源网址 / 厂商文档标识','layout':'色块布局 / 如何按标签找到每块'}
        for key,label in labels.items():
            row=ttk.Frame(body);row.pack(fill='x',pady=2)
            ttk.Label(row,text=label,width=29).pack(side='left')
            entry=ttk.Entry(row);entry.pack(side='left',fill='x',expand=True);self.fields[key]=entry
        row=ttk.Frame(body);row.pack(fill='x',pady=6)
        for key,label,values in [('white','厂商光源',['D50']),('observer','观察者',['2']),('kind','数值类型 / 单位',FORMATS)]:
            ttk.Label(row,text=label).pack(side='left',padx=3)
            combo=ttk.Combobox(row,state='readonly',values=values,width=17 if key=='kind' else 8)
            combo.pack(side='left');self.fields[key]=combo
        ttk.Label(body,text='根据原文件列名匹配 ID 和三个分量。Lab 为 L*,a*,b*；XYZ 为 X,Y,Z。\nXYZ 0–100 会自动除以 100；Lab D50 会按 CIE 公式转 XYZ。其他光源 / 观察者不支持。',wraplength=810).pack(anchor='w')
        row=ttk.Frame(body);row.pack(fill='x',pady=6);self.columns=[]
        aliases=[('sample_id','patch','id'),('lab_l','l','xyz_x','x'),('lab_a','a','xyz_y','y'),('lab_b','b','xyz_z','z')]
        lower={c.lower():c for c in table['columns']}
        for label,names in zip(('色块 ID','分量 1','分量 2','分量 3'),aliases):
            ttk.Label(row,text=label).pack(side='left',padx=3)
            combo=ttk.Combobox(row,state='readonly',values=table['columns'],width=13);combo.pack(side='left')
            combo.set(next((lower[n] for n in names if n in lower),''));self.columns.append(combo)
        self.confirmed=tk.BooleanVar()
        ttk.Checkbutton(body,text='我已核对实物版本、厂商来源、D50 / 2°、数值单位与标签顺序',variable=self.confirmed).pack(anchor='w',pady=6)
        frame=ttk.Frame(body);frame.pack(fill='both',expand=True)
        self.preview=ttk.Treeview(frame,columns=('order','id','xyz'),show='headings',height=7)
        for key,label,width in [('order','标记顺序',80),('id','厂商色块标签',170),('xyz','转换后的 XYZ（Y=1）',470)]:
            self.preview.heading(key,text=label);self.preview.column(key,width=width)
        self.preview.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=self.preview.yview);scroll.pack(side='right',fill='y');self.preview.configure(yscrollcommand=scroll.set)
        ttk.Label(body,text='预览顺序就是照片中框选色块的顺序，不猜测左右或上下。若参考文件与实物标签不能对应，请停止并询问厂商。',wraplength=810).pack(anchor='w',pady=5)
        actions=ttk.Frame(body);actions.pack(fill='x')
        ttk.Button(actions,text='验证并预览',command=lambda:self.safe(self.show_preview)).pack(side='left')
        ttk.Button(actions,text='保存本地配置并使用',command=lambda:self.safe(self.save)).pack(side='left',padx=8)
        ttk.Button(actions,text='取消',command=self.window.destroy).pack(side='right')

    def safe(self,command):
        try:command()
        except Exception as exc:messagebox.showerror('未完成',str(exc),parent=self.window)
    def profile(self):
        meta={k:self.fields[k].get() for k in ('manufacturer','model','edition','source','layout','white','observer')}
        return build_profile(self.table,[c.get() for c in self.columns],self.fields['kind'].get(),meta,self.confirmed.get())
    def show_preview(self):
        profile=self.profile();self.preview.delete(*self.preview.get_children())
        for number,(name,xyz) in enumerate(zip(profile['patch_ids'],profile['xyz']),1):
            self.preview.insert('','end',values=(number,name,', '.join(f'{v:.5f}' for v in xyz)))
    def save(self):
        profile=self.profile();self.show_preview()
        path=filedialog.asksaveasfilename(parent=self.window,title='保存新的本地参考配置',defaultextension='.json',initialfile='my-card-profile.json')
        if not path:return
        with Path(path).open('x',encoding='utf-8') as file:
            json.dump(profile,file,ensure_ascii=False,indent=2,allow_nan=False)
        self.on_created(profile);self.window.destroy()


def open_reference_wizard(parent,on_created):
    path=filedialog.askopenfilename(parent=parent,title='选择厂商的 CSV / CGATS / TXT 参考文件',filetypes=[('参考文本','*.csv *.txt *.cgats'),('所有文件','*')])
    if not path:return
    file=Path(path)
    if file.stat().st_size>1_000_000:raise ValueError('参考文件超过 1 MB')
    raw=file.read_bytes()
    table=read_reference(raw.decode('utf-8-sig'))
    table['sha256']=hashlib.sha256(raw).hexdigest()
    return ReferenceWizard(parent,table,on_created)
