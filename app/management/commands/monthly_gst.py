
import datetime
from app import models
from app.models import User
from app.company_models import Company
from app.erp_import import GstFilingImport, MarketReturnImport
from app.report_models import DateRangeArgs, EmptyArgs
from custom.classes import IkeaDownloader
import datetime
from dateutil.relativedelta import relativedelta
import sys
from django.db.models import Q

GST_PERIOD_FILTER = {
    "devaki_urban" : lambda qs : qs.exclude(type = "damage", party_id  = "P150") #NAIDU HALL DAMAGE EXCLUDE
}

usernames_or_companies = sys.argv[2:]
companies = Company.objects.filter(Q(user_id__in = usernames_or_companies) | Q(name__in = usernames_or_companies)).distinct()

today = datetime.date.today()
prev_month = today - relativedelta(months=1)
fromd = prev_month.replace(day=1)
tod = fromd + relativedelta(day=31)
period = fromd.strftime("%m%Y")

args_dict = {
    DateRangeArgs: DateRangeArgs(fromd=fromd,tod=tod),
    EmptyArgs: EmptyArgs(),
}

for company in companies :
    print(f"Processing GST for Company: {company.name} for Period: {period}")
    i = IkeaDownloader(company.pk)
    GstFilingImport.run(company=company,args_dict=args_dict)
    qs = models.Sales.objects.filter(type__in = company.gst_types,date__gte = fromd,date__lte = tod)
    if company.name in GST_PERIOD_FILTER :
        qs = GST_PERIOD_FILTER[company.name](qs)
    qs.update(gst_period = period)
    
exit(0)
