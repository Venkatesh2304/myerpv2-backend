from app.erp_import import *
from app.report_models import *
import datetime

from custom.classes import IkeaDownloader

fromd = datetime.date(2025,9,1)
# fromd = datetime.date(2025,9,1)
tod = datetime.date(2025,9,30)
# PartyReport.update_db(IkeaDownloader(),fromd,tod)
# SalesImport.run(fromd,tod)
# StockHsnRateReport.update_db(IkeaDownloader(),fromd,tod)
# StockImport.run(fromd,tod)
# PartyImport.run(fromd,tod)
SalesRegisterReport.update_db(IkeaDownloader(),fromd,tod)
# GstFilingImport.run(fromd,tod)

# SalesRegisterReport.update_db(IkeaDownloader(),fromd,tod)
# IkeaDownloader().product_hsn_master().to_excel("a.xlsx")

# SalesImport.run(fromd,tod)
# MarketReturnReport.update_db(IkeaDownloader(),fromd,tod)
# MarketReturnImport.run(fromd,tod)
exit(0)