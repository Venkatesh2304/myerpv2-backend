import time
from app.company_models import Group
from app.erp_import import *
from app.report_models import *
from app.erp_models import *
import datetime

from custom.classes import Gst, IkeaDownloader
from django.db import connection
import tracemalloc

cur = connection.cursor()


# objs = list(IkeaGSTR1Report.objects.all())
# Inventory.objects.all().delete()

# s  = time.time()
# tracemalloc.start()  # start tracking memory
# new_objs = [ 
#     Inventory(company_id = obj.company_id, bill_id = obj.inum, stock_id = obj.stock_id, qty = obj.qty, txval = obj.txval,  rt = obj.rt)
#     for obj in objs
# ]
# current, peak = tracemalloc.get_traced_memory()
# print(f"Current memory usage: {current / 1024 / 1024:.2f} MB")
# print(f"Peak memory usage: {peak / 1024 / 1024:.2f} MB")

# tracemalloc.stop()
# Inventory.objects.bulk_create(new_objs,batch_size=1000)


# cur.execute(f"""
#             INSERT INTO app_inventory (company_id,bill_id, stock_id, qty, txval, rt)
#             SELECT gstr1.company_id, gstr1.inum, gstr1.stock_id, gstr1.qty, gstr1.txval, gstr1.rt
#             FROM ikea_gstr1_report as gstr1
#         """)
# e  = time.time() 
# print( e - s )
# exit(0)

fromd = datetime.date(2025,9,1)
# fromd = datetime.date(2025,9,1)
tod = datetime.date(2025,9,30)
# PartyReport.update_db(IkeaDownloader(),fromd,tod)
# SalesImport.run(fromd,tod)
# StockHsnRateReport.update_db(IkeaDownloader(),fromd,tod)
# StockImport.run(fromd,tod)
# PartyImport.run(fromd,tod)
args_dict = {
    DateRangeArgs: DateRangeArgs(fromd=fromd,tod=tod),
    EmptyArgs: EmptyArgs(),
}
group,_ = Group.objects.get_or_create(name="devaki")
company,_ = Company.objects.get_or_create(name="devaki_hul",group = group)
company.save()

# i = IkeaDownloader()
GstFilingImport.run(company=company,args_dict=args_dict)
exit(0)

# exit(0)

g = Gst()
while not g.is_logged_in():
    with open("captcha.png",'wb+') as f : 
        f.write(g.captcha())
    status = g.login(input("Enter captcha: "))
    print("login status :",status)

month_arg = MonthArgs(month=9,year=2025)
GSTR1Portal.update_db(g,group,month_arg)


# GstFilingImport.run(args_dict=args_dict)

# SalesRegisterReport.update_db(IkeaDownloader(),fromd,tod)
# IkeaDownloader().product_hsn_master().to_excel("a.xlsx")

# SalesImport.run(fromd,tod)
# MarketReturnReport.update_db(IkeaDownloader(),fromd,tod)
# MarketReturnImport.run(fromd,tod)
exit(0)