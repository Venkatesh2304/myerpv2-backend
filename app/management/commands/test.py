from app.company_models import Group
from app.erp_import import *
from app.report_models import *
import datetime

from custom.classes import Gst, IkeaDownloader

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
company,_ = Company.objects.get_or_create(name="devaki_urban",group = group)
company.save()
i = IkeaDownloader()
exit()

# GstFilingImport.run(company=company,args_dict=args_dict)
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