import yfinance as yf
from datetime import datetime

# الأسهم التي سنختبر عليها النظام
TICKERS = ["JZ", "CANF"]


def check_stock(ticker):
    print("=" * 60)
    print(f"السهم: {ticker}")

    stock = yf.Ticker(ticker)

    # جلب بيانات التقسيمات
    splits = stock.splits

    if splits.empty:
        print("لا توجد تقسيمات مسجلة.")
        return

    found_reverse = False

    for date, ratio in splits.items():

        # التقسيم العكسي يكون عادة نسبة أقل من 1
        # مثال: 1 مقابل 10 = 0.1
        if ratio < 1:

            found_reverse = True

            split_date = date.to_pydatetime().date()
            today = datetime.now().date()

            days_passed = (today - split_date).days

            print(f"نوع التقسيم: تقسيم عكسي")
            print(f"تاريخ التقسيم: {split_date}")
            print(f"نسبة التقسيم: {ratio}")
            print(f"عدد الأيام منذ التقسيم: {days_passed}")

            if days_passed >= 20:
                print("🟢 دخل الرادار: مر عليه 20 يومًا أو أكثر")
            else:
                print("🟡 لم يصل إلى 20 يومًا بعد")

    if not found_reverse:
        print("لا يوجد تقسيم عكسي مسجل في البيانات.")


for ticker in TICKERS:
    try:
        check_stock(ticker)
    except Exception as e:
        print(f"حدث خطأ مع {ticker}: {e}")
