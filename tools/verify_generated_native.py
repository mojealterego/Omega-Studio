"""Compile generated Android Java against API surface stubs; does not replace SDK/device test."""
from pathlib import Path
import json
import subprocess
import tempfile
from tools.verify_android_sources import STUBS
from builder.omega_builder import generate_files

ROOT=Path(__file__).resolve().parents[1]
EXTRA={
 'android/content/res/Resources.java':'''package android.content.res;public class Resources{public android.util.DisplayMetrics getDisplayMetrics(){return new android.util.DisplayMetrics();}}''',
 'android/util/DisplayMetrics.java':'''package android.util;public class DisplayMetrics{public float density=1f;}''',
 'android/graphics/Color.java':'''package android.graphics;public class Color{public static int parseColor(String s){return 0;}}''',
 'android/graphics/Typeface.java':'''package android.graphics;public class Typeface{public static final Typeface SERIF=new Typeface();public static final int NORMAL=0,BOLD=1;}''',
 'android/graphics/drawable/GradientDrawable.java':'''package android.graphics.drawable;public class GradientDrawable{public void setColor(int c){}public void setCornerRadius(int r){}}''',
 'android/widget/TextView.java':'''package android.widget;public class TextView extends android.view.View{public TextView(android.content.Context c){}public void setText(String s){}public void setTextSize(int n){}public void setTextColor(int n){}public void setPadding(int a,int b,int c,int d){}public void setTypeface(android.graphics.Typeface t,int n){}public void setBackground(android.graphics.drawable.GradientDrawable d){}}''',
 'android/widget/EditText.java':'''package android.widget;public class EditText extends TextView{public EditText(android.content.Context c){super(c);}public void setSingleLine(boolean b){}public void setHintTextColor(int n){}}''',
 'android/widget/Button.java':'''package android.widget;public class Button extends TextView{public Button(android.content.Context c){super(c);}public void setAllCaps(boolean b){}public void setOnClickListener(android.view.View.OnClickListener l){}}''',
 'android/widget/LinearLayout.java':'''package android.widget;public class LinearLayout extends android.view.View{public static final int VERTICAL=1;public LinearLayout(android.content.Context c){}public void setOrientation(int o){}public void setPadding(int a,int b,int c,int d){}public void addView(android.view.View v){}public void addView(android.view.View v,LayoutParams p){}public static class LayoutParams{public LayoutParams(int a,int b){}public void setMargins(int a,int b,int c,int d){}}}''',
 'android/widget/ScrollView.java':'''package android.widget;public class ScrollView extends android.view.View{public ScrollView(android.content.Context c){}public void setFillViewport(boolean b){}public void setBackgroundColor(int c){}public void addView(android.view.View v){}}''',
 'android/view/View.java':'''package android.view;public class View{public interface OnClickListener{void onClick(View v);}public View(){}public View(android.content.Context c){}public void setBackgroundColor(int c){}}''',
 'android/content/Context.java':'''package android.content;public class Context{public android.content.res.Resources getResources(){return new android.content.res.Resources();}}''',
 'android/app/Activity.java':'''package android.app;public class Activity extends android.content.Context{protected void onCreate(android.os.Bundle b){}public void setContentView(android.view.View v){}}''',
}

def main():
    project=json.loads((ROOT/'builder/examples/premium-app.json').read_text())
    files=generate_files(project)
    with tempfile.TemporaryDirectory(prefix='omega-native-') as tmp:
        root=Path(tmp);paths=[]
        for name,src in {**STUBS,**EXTRA}.items():
            f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(src);paths.append(str(f))
        for name,content in files.items():
            if name.endswith('.java'):
                f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(content);paths.append(str(f))
        p=subprocess.run(['javac','-source','17','-target','17','-d',str(root/'classes'),*paths],capture_output=True,text=True,timeout=30)
        if p.returncode:raise RuntimeError(p.stderr)
    print('PASS: generated native Android Java compiles against local API stubs')

if __name__=='__main__':main()
