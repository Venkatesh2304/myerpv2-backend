
import datetime
from app import models
from app.models import User
from app.company_models import Company
from app.erp_import import GstFilingImport, MarketReturnImport
from app.report_models import DateRangeArgs, EmptyArgs
from custom.classes import IkeaDownloader
import datetime
from dateutil.relativedelta import relativedelta

user = User.objects.get(username="devaki")
print("Starting Monthly GST Import for user:",user.username)
today = datetime.date.today()
prev_month = today - relativedelta(months=1)
fromd = prev_month.replace(day=1)
tod = fromd + relativedelta(day=31)
period = fromd.strftime("%m%Y")
print("Importing GST Filing from",fromd,"to",tod)

args_dict = {
    DateRangeArgs: DateRangeArgs(fromd=fromd,tod=tod),
    EmptyArgs: EmptyArgs(),
}
for company in Company.objects.filter(user=user,name = "devaki_rural"):
    print("Importing for company:",company.name)
    i = IkeaDownloader(company.pk)
    GstFilingImport.run(company=company,args_dict=args_dict)
    models.Sales.objects.filter(type__in = company.gst_types,date__gte = fromd,date_lte = tod).update(gst_period = period)

exit(0)
