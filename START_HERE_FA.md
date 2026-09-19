# شروع پروژه در VS Code

مرحله صفر و پایلوت تصویری GlioTrace اجرا شده‌اند. از تاریخ ۱۹ سپتامبر ۲۰۲۶، پروژه برای حذف وابستگی به بازبین انسانی بازطراحی شده است. ارزیابی کمی روی برچسب‌های مرجع موجود U373 و سپس T98G انجام می‌شود؛ GlioTrace فقط مطالعهٔ موردی اکتشافی باقی می‌ماند. [تصمیم تغییر مسیر](docs/pivot-2026-09-19.md) و [رودمپ جدید](docs/roadmap.md) مبنای ادامهٔ کار هستند.

## باز کردن پروژه

1. فایل ZIP پروژه را دریافت و از حالت فشرده خارج کنید.
2. در VS Code از **File → Open Folder** پوشه `gbm-tracking-uncertainty` را انتخاب کنید.
3. [افزونه رسمی Codex](https://developers.openai.com/codex/ide) را در VS Code نصب کنید و وارد حساب خود شوید. هنوز هیچ نیازی به بارگیری مجموعه ۵٫۶ گیگابایتی نیست.
4. در VS Code از **Terminal → New Terminal** یک ترمینال باز کنید. Python باید نسخه 3.11 تا 3.13 باشد.

در macOS یا Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/fetch_pilot_rois.py
```

در Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/fetch_pilot_rois.py
```

اسکریپت آخر فقط برای مطالعهٔ موردی GlioTrace است: دو ROI کوچک را با بازه‌های بایتی مشخص می‌گیرد، صحت فایل‌ها را می‌سنجد و در `data/raw/glio_trace/` می‌گذارد. فایل‌های خام وارد Git نمی‌شوند. اگر شبکه یا نسخه داده با این بازه‌ها سازگار نباشد، اسکریپت با خطا متوقف می‌شود.

برای بازبینی داده‌های این مرحله:

```bash
python -m gbm_audit.roi data/raw/glio_trace/Set_67/exp_333_roi_84_stack.npz --output results/set67.json
python -m gbm_audit.roi data/raw/glio_trace/Set_68/exp_337_roi_63_stack.npz --expected-frames 68 --output results/set68.json
```

قبل از HMM یا Koopman، باید benchmark مرجع U373، خطاهای کنترل‌شده و baseline tracking به‌ترتیب gateهای رودمپ پاس شوند. هیچ خروجی ماشینی GlioTrace به‌عنوان Ground Truth استفاده نمی‌شود.

## قراردادن پروژه در GitHub

یک مخزن **خالی** با نام `gbm-tracking-uncertainty` در حساب خود بسازید؛ هنگام ساخت، گزینه‌های README و `.gitignore` را فعال نکنید چون این فایل‌ها آماده‌اند. پس از باز کردن پوشه پروژه در VS Code، در ترمینال آن اجرا کنید:

```bash
git init -b main
git add .
git commit -m "Initialize feasibility pilot"
git remote add origin https://github.com/YOUR_USERNAME/gbm-tracking-uncertainty.git
git push -u origin main
```

به جای `YOUR_USERNAME` نام کاربری حساب خود را بگذارید. GitHub ممکن است در اولین `push` ورود به حساب را درخواست کند. فایل‌های خام و خروجی‌ها طبق `.gitignore` وارد Git نمی‌شوند. اگر Git نام و ایمیل خواست، قبل از `git commit` دستورهای `git config user.name "نام شما"` و `git config user.email "ایمیل گیت‌هاب شما"` را بزنید و سپس commit را تکرار کنید.
