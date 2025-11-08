from collections import defaultdict
import copy
import datetime
from io import BytesIO
import warnings
import dateutil.relativedelta as relativedelta
import json
import random
import numpy as np
from functools import lru_cache
import pandas as pd 
import base64
from .std import moc_range
from pathlib import Path
import zipfile
from dateutil.parser import parse as date_parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
from pathlib import Path    
from multiprocessing.pool import ThreadPool
from tqdm import tqdm
from urllib.parse import parse_qsl, urljoin
import hashlib
import json
import os
from io import StringIO
from .secondarybills import main as secondarybills
from .curl import get_curl , curl_replace 
from .Session import Session,StatusCodeError
from bs4 import BeautifulSoup
from PyPDF2 import PdfMerger
from .std import add_image_to_bills
from urllib.parse import urlencode
import requests 
from PyPDF2 import PdfReader
import os

warnings.filterwarnings("ignore", category=UserWarning, module=re.escape('openpyxl.styles.stylesheet'))



class WrongCredentials(Exception) :
    pass

class IkeaPasswordExpired(WrongCredentials) :
    pass

class IkeaWrongCredentails(WrongCredentials) :
    pass



class BaseIkea(Session) : 
          
      key = "ikea"
      IKEA_GENERATE_REPORT_URL = "/rsunify/app/reportsController/generatereport"
      IKEA_DOWNLOAD_REPORT_URL = "/rsunify/app/reportsController/downloadReport?filePath="
      load_cookies = True 
      force_base_url = True 
      
      def date_epochs(self) :
        return int((datetime.datetime.now() - datetime.datetime(1970, 1, 1)
                        ).total_seconds() * 1000) - (330*60*1000)
      
      @lru_cache(maxsize=None)
      def report(self,key,pat,replaces,fname = None,is_dataframe =True) :
          r  = get_curl(key)
          if isinstance(r.data,str) :
             r.data = dict(parse_qsl( r.data ))
          if "jsonObjWhereClause" in r.data :
                r.data['jsonObjWhereClause'] =  curl_replace(  pat , replaces ,  r.data['jsonObjWhereClause'] )
                if "jsonObjforheaders" in r.data  : del r.data['jsonObjforheaders']
          durl = r.send(self).text
          if durl == "" : return None 
          res = self.download_file( durl , fname )
          return pd.read_excel(res) if is_dataframe else res 

      def download_file(self,durl,fname = None) -> BytesIO:
          if durl == "" :
              raise Exception("Download URL is empty") 
          response_buffer = self.get_buffer(durl)
          if fname is not None :
             with open(fname, "wb+") as f:
                f.write(response_buffer.getbuffer())          
          return response_buffer 
      
      def download_dataframe(self,key,skiprows=0,sheet=None) -> pd.DataFrame : 
          kwargs = {} if sheet is None else {"sheet_name":sheet}
          durl = get_curl(key).send(self).text
          return pd.read_excel( self.get_buffer(durl) , skiprows = skiprows , **kwargs , engine="openpyxl")
       
      def is_logged_in(self) :
         try : 
           self.get("/rsunify/app/billing/getUserId",timeout=15)
           self.logger.info("Login Check : Passed")
           return True 
         except StatusCodeError as e :
           self.logger.error("Login Check : Failed")
           return False 
    
      def login(self) : 
          self.logger.info("Login Initiated")
          self.cookies.clear()
          time_epochs = self.date_epochs()
          preauth_res_text = self.post("/rsunify/app/user/authentication",data={'userId': self.username , 'password': self.password, 'dbName': self.config["dbName"], 'datetime': time_epochs , 'diff': -330}).text
          if ("CLOUD_LOGIN_PASSWORD_EXPIRED" == preauth_res_text) or ("Invalid Password" == preauth_res_text) : 
             raise IkeaPasswordExpired("Ikea Password Expired")
          elif "<body>" in preauth_res_text : 
             raise IkeaWrongCredentails("Ikea Wrong Credentials")
          else : 
             pass 
          response = self.post("/rsunify/app/user/authenSuccess",{})
          if response.status_code == 200 : 
             self.logger.info("Logged in successfully")
             print("Login Success")
             self.user.update_cookies(self.cookies)
          else : 
             raise Exception("Login Failed")

      def __init__(self,user:str) : 
          super().__init__(user)
          self.headers.update({'accept': 'application/json, text/javascript, */*; q=0.01'})
          self.base_url = self.config["home"]
          retry_count = 1
          while not self.is_logged_in() : 
             print(f"Retry Count : {retry_count} , Trying to Login ikea") 
             self.login()
             retry_count += 1
             
      def get_buffer(self,relative_url) :
          return super().get_buffer( self.IKEA_DOWNLOAD_REPORT_URL + relative_url )
      
      def parllel(self,fn,list_of_args,max_workers=10,show_progress=False,is_async=False) : 
          pool = ThreadPool(max_workers) 
          list_of_args = [ [self] + list(args) for args in list_of_args ]
          if show_progress : 
             pbar = tqdm(total = len(list_of_args)) 
          def progress_function(*args) : 
              fn(*args)
              pbar.update(1) 
          overloaded_fn = progress_function if show_progress else fn
          results =  pool.starmap_async(overloaded_fn,list_of_args) if is_async else pool.starmap(overloaded_fn,list_of_args)
          return results

class IkeaDownloader(BaseIkea) :  
      MOC_PAT = r'(":val1":").{7}'

      def gstr_report(self,fromd,tod,gstr_type=1) -> pd.DataFrame :
          r = get_curl("ikea/gstr")
          r.url = curl_replace(r"(pramFromdate=).{10}(&paramToDate=).{10}(&gstrValue=).", 
                                  (fromd.strftime("%d/%m/%Y") ,tod.strftime("%d/%m/%Y"),str(gstr_type)) , r.url )

          durl = r.send(self).text
          return pd.read_csv( self.get_buffer(durl))

      def collection(self,fromd,tod) : 
          df = self.report( "ikea/collection" , r'(":val10":").{10}(",":val11":").{10}(",":val12":".{10}",":val13":").{10}', 
                       ( fromd.strftime("%Y/%m/%d")  , tod.strftime("%Y/%m/%d") , tod.strftime("%Y/%m/%d") ) )
          return df 
      
      def crnote(self,fromd,tod) : 
          crnote =  self.report("ikea/crnote" , r'(":val3":").{10}(",":val4":").{10}', ((fromd - datetime.timedelta(weeks=12)).strftime("%d/%m/%Y"),
                                                                                     tod.strftime("%d/%m/%Y")) )
          date_column = "Adjusted/Collected/Cancelled Date"
          crnote[date_column] = pd.to_datetime(crnote[date_column],format="%Y-%m-%d")
          crnote = crnote[crnote[date_column].dt.date >= fromd][crnote[date_column].dt.date <= tod]
          return crnote
      
      def outstanding(self,date:datetime.date) -> dict : 
          return self.report("ikea/outstanding",r'(":val9":").{10}(.{34}).{10}', (date.strftime("%Y-%m-%d"),date.strftime("%Y-%m-%d"))  ) 
      
      def download_manual_collection(self)  : 
          return self.report("ikea/download_manual_collection",r'(":val10":").{10}', (datetime.date.today().strftime("%d/%m/%Y"),)  ) 
      
      def upload_manual_collection(self,file : BytesIO) -> dict :
          files = {
            'file': ('upload.xlsx', file , 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
           }
          return self.post("/rsunify/app/collection/collectionUpload",files = files,data = {}).json()

      def download_settle_cheque(self,type="PENDING",fromd = datetime.date.today(),tod = datetime.date.today())  : 
          return self.report("ikea/download_settle_cheque",r'(":val1":").*(",":val2":").{10}(",":val3":").{10}(.{32}).{10}', 
                             (type,fromd.strftime("%d/%m/%Y"),tod.strftime("%d/%m/%Y"),datetime.date.today().strftime("%d/%m/%Y")) ) 
         
      def upload_settle_cheque(self,file : BytesIO) -> dict :
          files = {
            'file': ('upload.xlsx', file , 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
           }
          return self.post("/rsunify/app/chequeMaintenance/chequeUpload",files = files,data = {}).json()

      def product_wise_purchase(self,fromd,tod) : 
          return self.report("ikea/product_wise_purchase",r'(":val1":").{10}(",":val2":").{10}',(fromd.strftime("%d/%m/%Y"),tod.strftime("%d/%m/%Y")))
      
      def stock_ledger(self,fromd,tod) : 
          return self.report("ikea/stock_ledger",r'(":val3":").{10}(",":val4":").{10}',(fromd.strftime("%d/%m/%Y"),tod.strftime("%d/%m/%Y")))
      
      def current_stock(self ,date) :
          return self.report("ikea/current_stock",r'(":val16":").{10}', (date.strftime("%Y-%m-%d"),))
      
      def sales_reg(self,fromd,tod) : 
          df = self.report("ikea/sales_reg",r'(":val1":").{10}(",":val2":").{10}' ,
                                                       (fromd.strftime("%d/%m/%Y"),tod.strftime("%d/%m/%Y")) )
          date_column = "BillDate/Sales Return Date"
          try :
              date_series = pd.to_datetime(df[date_column],format="%Y-%m-%d")
          except : 
              date_series = pd.to_datetime(df[date_column],format="%d/%m/%Y")
          df[date_column] = date_series.dt.date
          return df 
      
      
      def download_moc(self,fromd,tod,key,pat,sheet_name,date_column,is_slash=True,date_checker = None) :
          dfs = []
          for moc in moc_range(fromd,tod,slash=is_slash) : 
              try : 
                 dfs.append( pd.read_excel( self.report(key,pat,(moc,),is_dataframe=False) , sheet_name=sheet_name , engine="openpyxl" )   )
              except Exception as e : 
                  pass 
          df = pd.concat(dfs)
          if date_column is not None :
             if date_column not in df.columns : return None 
             df[date_column] = pd.to_datetime(df[date_column]).dt.date
             if date_checker is None :
                df = df[ (df[date_column] >= fromd) & (df[date_column] <= tod) ]
             else : 
                 df = df[ date_checker(df,date_column) ]
          return df 
      
      def damage_proposals(self,fromd,tod,type) :
          """type = sales or purchase"""
          _fromd = fromd - relativedelta.relativedelta(months=3)
          date_checker = lambda df,date_column : (df[date_column] >= fromd) & (df[date_column] <= tod)
          column_map = { "sales" : (" TRANSACTION DETAILS","TRANS DATE"),
                         "purchase" : ("STOCK OUT WITH CLAIM","TRANS REF DATE") }
          if type not in column_map : raise Exception("Type should be sales or purchase")
          return self.download_moc(_fromd,tod,"ikea/damage_proposal",self.MOC_PAT, column_map[type][0] , column_map[type][1] ,
                                            date_checker=date_checker)
        #   self.download_moc(_fromd,tod,"ikea/damage_proposal",self.MOC_PAT,"STOCK OUT WITHOUT CLAIM","TRANS REF DATE")

      def claim_status(self,fromd,tod) : 
          return self.download_moc(fromd - relativedelta.relativedelta(months=6) , tod , "ikea/claim_status",
                            self.MOC_PAT,"SUMMARY",None)
                            
      def product_hsn_master(self) : 
          dfs = []
          for i in range(1,11) : 
              try : 
                 dfs.append( self.report("ikea/product_master",r'(val2":")[0-9]*', (str(i),) ) )  
              except Exception as e : print(e) 
          return pd.concat(dfs)
       
      def dse(self,fromd,tod) : 
          return pd.read_excel( self.report("ikea/dse",r'(":val1":").{10}(",":val2":").{10}',
                                            (fromd.strftime("%d/%m/%Y") , tod.strftime("%d/%m/%Y")) , is_dataframe= False)  , 
                                sheet_name = "DSE" )
      
      def damage_debitnote(self,fromd,tod) : 
          return self.download_moc(fromd,tod,"ikea/damage_debitnote",r'(":val1":").{6}',"Damage Debite Note Report","DEBIT NOTE DATE",is_slash=False)
           
      def pending_bills(self,date:datetime.date) -> dict : 
          return self.report("ikea/pending_bills",r'(":val8":").{10}', (date.strftime("%Y-%m-%d"),) , is_dataframe = True ) 
      
      def beat_mapping(self) -> dict : 
          return self.report("ikea/beat_mapping","","",is_dataframe = True ) 
      
      def product_hsn(self) -> dict : 
          return get_curl("ikea/list_of_products").send(self).json() 
      
      def party_master(self) -> pd.DataFrame : 
          return self.download_dataframe("ikea/party_master",skiprows=9)
      
      def stock_master(self) -> pd.DataFrame : 
          return self.download_dataframe("ikea/stock_master",skiprows=9)
      
      def basepack(self,is_dataframe = False) : 
          return self.report("ikea/basepack","","",is_dataframe = is_dataframe) 
      
      def loading_sheet(self,bills = []) : 
          two_days_before = datetime.date.today() - datetime.timedelta(days=2)
          today = datetime.date.today() 
          bytesio = self.report("ikea/loading_sheet",r'(":val12":"\').{10}(\'",":val13":"\').{10}(\'",":val14":").{0}' ,
                                            (two_days_before.strftime("%d/%m/%Y") , today.strftime("%d/%m/%Y") , ",".join(bills) ),is_dataframe = False)
          df1 = pd.read_excel(bytesio,dtype = "str",sheet_name="Loading Sheet")
          df2 = pd.read_excel(bytesio,dtype = "str",sheet_name="Party Wise Sales Report")
          return (df1,df2)
      
      def einvoice_json(self,fromd,tod,bills) : 
           return self.report( "ikea/einvoice_json",r'(":val1":").{8}(",":val2":").{8}(.*":val9":")[^"]*' , 
                              (fromd.strftime("%Y%m%d"),tod.strftime("%Y%m%d"),",".join(bills)) , is_dataframe = False )
      
      def eway_excel(self,bills:list[str]) :
          fromd = datetime.date.today() - datetime.timedelta(days=7)
          tod = datetime.date.today()
          bills.sort()
          df = self.report( "ikea/eway_excel",r'(":val1":").{8}(",":val2":").{8}(.*":val5":")[^"]*(",":val6":")[^"]*' , 
                              (fromd.strftime("%Y%m%d"),tod.strftime("%Y%m%d"),bills[0],bills[-1]) )
          return df[df["Doc.No"].isin(bills)]
      
      def pending_statement_pdf(self,beats,date) : 
            r = get_curl("ikea/pending_statement_pdf")
            r.data["strJsonParams"] = curl_replace(r'(beatVal":").{0}(.*colToDate":").{10}(.*colToDateHdr":").{10}', 
                                  (",".join(beats),date.strftime("%Y-%m-%d") ,date.strftime("%d/%m/%Y")) , r.data["strJsonParams"])
            durl = r.send(self).text
            return self.download_file(durl)

      def pending_statement_excel(self,beats,date) : 
            r = get_curl("ikea/pending_statement_excel")
            r.data["jsonObjWhereClause"] = curl_replace(r'(":val5":").{0}(.*":val8":").{10}', 
                                  (",".join(beats),date.strftime("%Y-%m-%d")) , r.data["jsonObjWhereClause"])
            durl = r.send(self).text
            return self.download_file(durl)
      
      def upload_irn(self,bytesio) : 
          files = {'file': ( "IRNGenByMe.xlsx" , bytesio )}
          res = self.post("/rsunify/app/stockmigration/eInvoiceIRNuploadFile",files=files)
          return res.json()
      
      def sync_impact(self,from_date,to_date,bills,vehicle_name):
          login_data = self.post("/rsunify/app/impactDeliveryUrl").json()
          url = login_data["url"]
          del login_data["url"]
          url = url + "ikealogin.do?" + urlencode(login_data)
          s = requests.Session() 
          s.get(url)
          s.get("https://shogunlite.com/")
          s.get("https://shogunlite.com/login.do") 
          html = s.get("https://shogunlite.com/deliveryupload_home.do?meth=viewscr_home_tripplan&hid_id=&dummy=").text 
          form = extractForm(html,all_forms=True)
          form =  {"org.apache.struts.taglib.html.TOKEN": form["org.apache.struts.taglib.html.TOKEN"],
                  "actdate": from_date.strftime("%d-%m-%Y") + " - " + to_date.strftime("%d-%m-%Y") , 
                  "selectedspid": "493299",
                  "meth":"ajxgetDetailsTrip"} #warning: spid is vehicle A1 (so we keep it default)
          html = s.get(f"https://shogunlite.com/deliveryupload_home.do",params=form).text 
          soup = BeautifulSoup(html,"html.parser")      
          vehicle_codes = { option.text : option.get("value")  for option in soup.find("select",{"id":"mspid"}).find_all("option") }
          all_bill_codes = [ code.get("value") for code in soup.find_all("input",{"name":"selectedOutlets"}) ]
          all_bill_numbers = list(pd.read_html(html)[-1]["BillNo"].values)
          bill_to_code_map = dict(zip(all_bill_numbers,all_bill_codes))      
          form = extractForm(html)
          form["exedate"] = datetime.date.today().strftime("%d-%m-%Y")
          form["mspid"] = vehicle_codes[vehicle_name]
          form["meth"] = "ajxgetMovieBillnumber"
          form["selectedspid"] = "493299"
          form["selectedOutlets"] = [ bill_to_code_map[bill] for bill in bills if bill in bill_to_code_map ] 
          del form["beat"]
          del form["sub"]
          s.post("https://shogunlite.com/deliveryupload_home.do",data = form).text

      def upi_statement(self,fromd,tod) :  
          return self.report("ikea/upi_statement",r'(":val3":"\').{10}(\'",":val4":"\').{10}' ,
                                                       (fromd.strftime("%Y-%m-%d"),tod.strftime("%Y-%m-%d")) )

class Billing(IkeaDownloader) :

    lines = 100
    lines_count = {}
    creditrelease = {}
    
    def __init__(self,order_date = datetime.date.today(),filter_orders_fn = (lambda : False)):
        super().__init__()
        self.filter_orders_fn = filter_orders_fn
        self.prev_collection = []
        self.today = datetime.date.today()
        self.order_date = order_date
        
    def client_id_generator(self): 
        return np.base_repr(self.date_epochs(), base=36).lower() + np.base_repr(random.randint(pow(10, 17), pow(10, 18)),
                 base=36).lower()[:11]

    def get_plg_maps(self) :
        # with open("a.html","w+") as f : f.write(self.get("/rsunify/app/rssmBeatPlgLink/loadRssmBeatPlgLink").text)
        html = self.get("/rsunify/app/rssmBeatPlgLink/loadRssmBeatPlgLink").text
        soup = BeautifulSoup(html) 
        plg_maps = soup.find("input", {"id" : "hiddenSmBeatLnkMap"}).get("value")

        salesman_ids = [ i.get("value") for i in soup.find("tbody", {"id" : "blockEvt"}).findChildren("input",recursive=True) ][::3]
        salesman_table = pd.read_html(html)[0].rename(columns={"Salesperson Code":"salesman_code","Salesperson Name":"salesman_name"})
        salesman_table["salesman_id"] = pd.Series(salesman_ids).apply(int)
        plg_maps = json.loads(plg_maps)
        plg_maps = [ [sal_id] + beat_data for sal_id in plg_maps for beat_data in plg_maps[sal_id] ] 
        
        plg_maps = pd.DataFrame(plg_maps).astype({ 0  : int }).rename(columns={0:"salesman_id",1:"id",2:"name",3:"plg"})
        plg_maps["days"] = ""
        for col,day in zip(range(6,13),["monday","tuesday","wednesday","thursday","friday","saturday"]) : 
            plg_maps["days"] += plg_maps[col].apply(lambda x : day + "," if int(x) else "")
        plg_maps["days"] = plg_maps["days"].str.strip(",")
        beats = pd.merge(plg_maps,salesman_table,on="salesman_id",how="outer")
        self.logger.log_dataframe(plg_maps)
        beats = beats[["id","salesman_id","salesman_name","salesman_code","name","plg","days"]]
        beats = beats.dropna(subset="id")
    
        return beats
          
    def get_creditlock(self,party_data) : 
        get_crlock_url = f'/rsunify/app/billing/partyplgdatas?partyCode={party_data["partyCode"]}&parCodeRef={party_data["parCodeRef"]}&parHllCode={party_data["parHllCode"]}&plgFlag=true&salChnlCode=&showPLG={party_data["showPLG"]}&isMigration=true'
        return self.get(get_crlock_url).json()
    
    def release_creditlock(self, party_data):
        party_credit = self.get_creditlock(party_data)
        credit_limit = party_credit["creditLimit"]
        new_credit_limit = (round(party_credit["creditLimitUtilised"] + party_data["order_value"]) + 10) if credit_limit else 0 
        new_credit_bills = int(party_credit["creditBillsUtilised"]) + party_data["increase_count"]
        set_url = f'/rsunify/app/billing/updatepartyinfo?partyCodeRef={party_data["partyCode"]}&creditBills={new_credit_bills}&creditLimit={new_credit_limit}&creditDays=0&panNumber=&servicingPlgValue={party_data["showPLG"]}&plgPartyCredit=true&parHllCode={party_data["parHllCode"]}'
        self.get(set_url)

    def release_creditlocks(self,party_datas : list):
        self.parllel( Billing.release_creditlock , ((party_data,) for party_data in party_datas) )
        #warning : parllel threadpool not efficient

    def Sync(self): 
        return self.post('/rsunify/app/fileUploadId/download')

    def Prevbills(self):
        delivery_req = get_curl("ikea/billing/getdelivery")
        delivery = delivery_req.send(self).json()["billHdBeanList"] or []
        self.prevbills = [ bill['blhRefrNo'] for bill in delivery ]
        print( self.prevbills )
        self.logger.info(f"Previous Delivery :: {self.prevbills}")

    def Collection(self):

        self.get("/rsunify/app/quantumImport/init")
        self.get("/rsunify/app/quantumImport/filterValidation")
        self.get(f"/rsunify/app/quantumImport/futureDataValidation?importDate={self.today.strftime('%d/%m/%Y')}")

        self.import_dates = {"importDate": (self.today - datetime.timedelta(days=1)).strftime("%Y-%m-%d") + "T18:30:00.000Z",
                             "orderDate": (self.order_date - datetime.timedelta(days=1)).strftime("%Y-%m-%d") + "T18:30:00.000Z"}
        get_collection_req = get_curl("ikea/billing/getmarketorder")
        get_collection_req.url = self.base_url + "/rsunify/app/quantumImport/validateloadcollection"
        get_collection_req.json |= self.import_dates 
        self.market_collection = get_collection_req.send(self).json()
        self.get("/rsunify/app/quantumImport/processcheck")
        
        collection_data = self.market_collection["mcl"]
        for coll in collection_data : 
            coll["ck"] = (coll["pc"] not in self.prev_collection)
            coll["bf"] = True
        self.pushed_collection_party_ids = [ coll["pc"] for coll in collection_data if coll["ck"]  ]

        coll_payload = {"mcl": collection_data, "id": self.today.strftime("%d/%m/%Y"), "CLIENT_REQ_UID": self.client_id_generator() , "ri" : 0 }
        self.logger.info(f"Imported Collection :: {self.pushed_collection_party_ids}")
        postcollection = self.post("/rsunify/app/quantumImport/importSelectedCollection", json=coll_payload).json()
        
    def Order(self,delete_order_numbers = []):
        get_shikhar = get_curl("ikea/billing/getshikhar")
        get_shikhar.json["importDate"] =  self.today.strftime("%d/%m/%Y")
        shikhar_data = get_shikhar.send(self).json()["shikharOrderList"]
        shikhar_ids = [order[11] for order in shikhar_data[1:]] #no date condition on shikar if order[9] == self.order_date.strftime("%d/%m/%Y")]
    
        get_order_req = get_curl("ikea/billing/getmarketorder")
        get_order_req.json |= (self.import_dates | {"qtmShikharList" : shikhar_ids})
        self.market_order = get_order_req.send(self).json()
    
        order_data = self.market_order["mol"]
        

        if delete_order_numbers :
            delete_orders_data = copy.deepcopy(order_data)
            for order in delete_orders_data :
                order["ck"] = (order["on"] in delete_order_numbers)
            delete_market_order = get_curl("ikea/billing/delete_orders")
            delete_market_order.json |= {"mol": delete_orders_data , "id": self.today.strftime("%d/%m/%Y")}
            delete_market_order.send(self).text
            order_data = [order for order in order_data if order["on"] not in delete_order_numbers] 
        
        self.all_orders = pd.DataFrame(order_data)
        self.all_orders.to_excel("all_orders.xlsx",index=False)
        self.logger.log_dataframe(self.all_orders,"All orders : ")      
        if len(self.all_orders.index) : 
            orders = self.all_orders.groupby("on", as_index=False)
            orders = orders.filter(self.filter_orders_fn)
            self.filtered_orders = orders
            self.logger.log_dataframe(self.filtered_orders,"Filtered orders : ")
        else : 
            return       

        # billwise_lines_count = orders.groupby("on")["cq"].count().to_dict()
        # self.logger.info(f"Bill Wise Line Count : {billwise_lines_count}") #Need to Prettify

        # orders["billvalue"], orders["status"] = orders.t * orders.cq , False
        # orders.p = orders.p.apply(lambda x: x.replace(" ", "")) # party spacing problem prevention
        # orders["on_str"] = orders.on.astype(str) + ","

        # cr_lock_parties = orders.groupby("on").filter(lambda x :  ("Credit Exceeded" in x.ar.values) ).groupby("p").agg(
        #                  {"pc": "first", "ph": "first", "pi": "first", "s": "first", "billvalue": "sum", "mi":  "first" , "on_str" : "sum"})
        # cr_lock_parties.rename(columns={"pc": "partyCode", "ph": "parHllCode","s": "salesman", "pi": "parId", "mi": "beatId"}, inplace=True)
        # cr_lock_parties["billvalue"]  = cr_lock_parties["billvalue"].round(2)
        # cr_lock_parties["parCodeRef"] = cr_lock_parties["partyCode"].copy()
        # cr_lock_parties["orders"] = cr_lock_parties["on_str"].apply(lambda x: list(set( x.split(",")[:-1] ))  )
        # del cr_lock_parties["on_str"]
        # self.creditlock = self.interpret(cr_lock_parties.to_dict(orient="index"))

            
            
        for order in order_data :
            order["ck"] = (order["on"] in orders.on.values)

        uid = self.client_id_generator()
        post_market_order = get_curl("ikea/billing/postmarketorder")
        post_market_order.json |= {"mol": order_data , "id": self.today.strftime("%d/%m/%Y"), "CLIENT_REQ_UID": uid}
        log_durl = post_market_order.send(self).json()["filePath"]
        # log_file = self.get_buffer(log_durl).read().decode()  # get text from string
        # self.interpret(cr_lock_parties.to_dict(orient="index"))
        #return self.creditlock_data

    def Delivery(self):
        if not self.config["auto_delivery_process"] : 
            self.bills = []
            return 
        delivery = get_curl("ikea/billing/getdelivery").send(self).json()["billHdBeanList"] or []
        if len(delivery) == 0 : 
           self.bills = []
           return 
        delivery = pd.DataFrame(delivery)
        self.logger.debug(f"All Delivery Bills :: {list(delivery.blhRefrNo)}")
        delivery = delivery[ ~delivery.blhRefrNo.isin(self.prevbills) ]
        self.bills = list(delivery.blhRefrNo)
        self.logger.info(f"Final Bills :: {self.bills}")
        delivery["vehicleId"] = 1
        data = {"deliveryProcessVOList": delivery.to_dict(orient="records"), "returnPickList": []}
        self.post("/rsunify/app/deliveryprocess/savebill",json=data).json()

    def group_consecutive_bills(self,bills):

        def extract_serial(bill_number):
            match = re.search(r'(\D+)(\d{5})$', bill_number)
            if match:
                return match.group(1), int(match.group(2))  # Return prefix and serial number as a tuple
            return None, None

        sorted_bills = sorted(bills, key=lambda x: extract_serial(x))

        groups = []
        current_group = []
        prev_prefix, prev_serial = None, None

        for bill in sorted_bills:
            prefix, serial = extract_serial(bill)
            if not prefix:
                continue

            if prev_prefix == prefix and prev_serial is not None and serial == prev_serial + 1:
                current_group.append(bill)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [bill]

            prev_prefix, prev_serial = prefix, serial

        if current_group:
            groups.append(current_group)

        return groups

    def Download(self,bills = None,pdf=True,txt=True,cash_bills = []):
        if bills is not None : self.bills = bills 
        if len(self.bills) == 0 : return
        get_bill_durl = lambda billfrom,billto,report_type : self.get(f"/rsunify/app/commonPdfRptContrl/pdfRptGeneration?strJsonParams=%7B%22billFrom%22%3A%22{billfrom}%22%2C%22billTo%22%3A%22{billto}%22%2C%22reportType%22%3A%22{report_type}%22%2C%22blhVatFlag%22%3A2%2C%22shade%22%3A1%2C%22pack%22%3A%22910%22%2C%22damages%22%3Anull%2C%22halfPage%22%3A0%2C%22bp_division%22%3A%22%22%2C%22salesMan%22%3A%22%22%2C%22party%22%3A%22%22%2C%22market%22%3A%22%22%2C%22planset%22%3A%22%22%2C%22fromDate%22%3A%22%22%2C%22toDate%22%3A%22%22%2C%22veh_Name%22%3A%22%22%2C%22printId%22%3A0%2C%22printerName%22%3A%22TVS+MSP+250+Star%22%2C%22Lable_position%22%3A2%2C%22billType%22%3A2%2C%22printOption%22%3A%220%22%2C%22RptClassName%22%3A%22BILL_PRINT_REPORT%22%2C%22reptName%22%3A%22billPrint%22%2C%22RptId%22%3A%22910%22%2C%22freeProduct%22%3A%22Default%22%2C%22shikharQrCode%22%3Anull%2C%22rptTypOpt%22%3A%22pdf%22%2C%22gstTypeVal%22%3A%221%22%2C%22billPrint_isPrint%22%3A0%2C%22units_only%22%3A%22Y%22%7D").text
        pdfs , txts = [], []
        for group in self.group_consecutive_bills(self.bills) :
            if txt: txts.append( self.download_file( get_bill_durl(group[0],group[-1],"txt")) )

        for group in self.group_consecutive_bills(set(self.bills) - set(cash_bills)) :
            if pdf : 
                pdf1 = self.download_file( get_bill_durl(group[0],group[-1],"pdf"))
                pdf2 = self.download_file( get_bill_durl(group[0],group[min(1,len(group)-1)],"pdf"))
                
                reader1 = PdfReader(pdf1).pages
                reader2 = PdfReader(pdf2).pages
                for page_no in range(len(reader2)) :
                    if reader2[page_no].extract_text() != reader1[page_no].extract_text() :
                        pdf1.seek(0)
                        pdf2.seek(0) 
                        with open("a.pdf","wb+") as f : 
                            f.write(pdf1.getvalue())
                        with open("b.pdf","wb+") as f : 
                            f.write(pdf2.getvalue())        
                        raise Exception("Print PDF Problem. Canceled First Copy Printing")
                
                pdf1.seek(0)
                pdfs.append(pdf1)

        for group in self.group_consecutive_bills(cash_bills) :
            if pdf : pdfs.append( add_image_to_bills( self.download_file( get_bill_durl(group[0],group[-1],"pdf")) ,
                                                          'cash_bill.png' , 8, 24, 1.9, 1.9 ) )

        if pdf :     
            merger = PdfMerger()
            for pdf_bytesio in pdfs:
                pdf_bytesio.seek(0)  #Ensure each BytesIO stream is at the start
                merger.append(pdf_bytesio)
            with open(f"{FILES_DIR}/bill.pdf", "wb+") as f:
                merger.write(f)
            merger.close()
        if txt : 
            with open(f"{FILES_DIR}/bill.txt", "wb+") as merged_file:
                for text_bytesio in txts :
                    text_bytesio.seek(0) 
                    merged_file.write(text_bytesio.read())
                    merged_file.write(b"\n")

    def Printbill(self,bills = None,print_files = ["bill.pdf","bill.txt"]):
        if bills is not None : self.bills = bills 
        if len(self.bills) == 0 : return
        try:
            import win32api
            for print_file in print_files : 
                win32api.ShellExecute(0, 'print', print_file , None, '.', 0)
            return True
        except Exception as e:
            print("Win32 Failed . Printing Failed")
            print(e)
            return False


## Needs to checked 
class GstWrongCredentails(WrongCredentials) :
    pass

class GstExpiredCredentails(WrongCredentials) :
    pass

class GstMultipleWrongAttempts(WrongCredentials) :
    pass

class Gst(Session) : 
     key = "gst"
     base_url = "https://gst.gov.in"
     home = "https://gst.gov.in"
     load_cookies = True
     rtn_types_ext = {"gstr1":"zip","gstr2a":"zip","gstr2b":"json"}

     def __init__(self,user:str) : 
          super().__init__(user)
          base_path = Path(__file__).parent
          self.dir = str( (base_path / ("data/gst/" + self.user.user)).resolve() )

     def captcha(self) : 
          self.cookies.clear()
          self.get('https://services.gst.gov.in/services/login')
          login = self.get('https://services.gst.gov.in/pages/services/userlogin.html')
          captcha = self.get('https://services.gst.gov.in/services/captcha?rnd=0.7395713643528166').content
          self.user.update_cookies(self.cookies)
          return captcha
          
     def login(self,captcha) :
          data =  { "captcha": captcha , "deviceID": None ,"mFP": "{\"VERSION\":\"2.1\",\"MFP\":{\"Browser\":{\"UserAgent\":\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.115 Safari/537.36\",\"Vendor\":\"Google Inc.\",\"VendorSubID\":\"\",\"BuildID\":\"20030107\",\"CookieEnabled\":true},\"IEPlugins\":{},\"NetscapePlugins\":{\"PDF Viewer\":\"\",\"Chrome PDF Viewer\":\"\",\"Chromium PDF Viewer\":\"\",\"Microsoft Edge PDF Viewer\":\"\",\"WebKit built-in PDF\":\"\"},\"Screen\":{\"FullHeight\":864,\"AvlHeight\":816,\"FullWidth\":1536,\"AvlWidth\":1536,\"ColorDepth\":24,\"PixelDepth\":24},\"System\":{\"Platform\":\"Win32\",\"systemLanguage\":\"en-US\",\"Timezone\":-330}},\"ExternalIP\":\"\",\"MESC\":{\"mesc\":\"mi=2;cd=150;id=30;mesc=739342;mesc=770243\"}}" ,
                    "password": self.password , "type": "username" , "username": self.username }
          res = self.post("https://services.gst.gov.in/services/authenticate" ,headers = {'Content-type': 'application/json'},json = data).json()
          if "errorCode" in res.keys() : 
              if res["errorCode"] == "SWEB_9000" : 
                 return False 
              elif res["errorCode"] == "AUTH_9002" : 
                  raise GstWrongCredentails("Invalid Username or Password")
              elif res["errorCode"] == "AUTH_9033" : 
                  raise GstExpiredCredentails("Password Expired , kindly change password")
              elif res["errorCode"] == "SWEB_9014" :
                  raise GstMultipleWrongAttempts("You have entered a wrong password for 3 consecutive times")
              else : 
                  print(res)
                  raise Exception("Unknown Exception")
          auth =  self.get("https://services.gst.gov.in/services/auth/",headers = {'Referer': 'https://services.gst.gov.in/services/login'})
          self.user.update_cookies(self.cookies)
     
     def is_logged_in(self) : 
         return len(self.getuser()) != 0 

     def getuser(self) : 
           try : 
            data = self.get("https://services.gst.gov.in/services/api/ustatus",
            headers = {"Referer": "https://services.gst.gov.in/services/auth/fowelcome"}).json()
           except Exception as e : 
               print("Exception Occured on get user :",e)
               print("Bypassing get_user and returning empty user list")
               return []
           return data 
     
     def getinvs(self,period,types,gstr_type="gstr1") :
         uploaded_by = 'OE' if 'B2CS' in types.upper()  else 'SU'
         data = self.get(f"https://return.gst.gov.in/returns/auth/api/{gstr_type}/invoice?rtn_prd={period}&sec_name={types.upper()}&uploaded_by={uploaded_by}",
                        headers = {"Referer": "https://return.gst.gov.in/returns/auth/gstr1"}).json()
         if "error" in data.keys()  :
             return []
         invs = data["data"]["processedInvoice"]
         return invs 
     
     def multi_downloader(self,periods,rtn_type="gstr1") :  
         """User function to download zips / jsons for multi period and different rtn_types"""
         rtn_type = rtn_type.lower()
         downloader_functions = {"zip":self.download_zip,"json":self.download_json}
         fname_ext = self.rtn_types_ext[rtn_type]
         downloader_function = downloader_functions[fname_ext]
         dir = self.dir + "/" + rtn_type
         downloads = []
         with ThreadPoolExecutor(max_workers=9) as executor:
              for period in periods :
                  if not os.path.exists(f"{dir}/{period}.{fname_ext}") : 
                         downloads.append(executor.submit( downloader_function,period,dir,rtn_type))
              for future in as_completed(downloads): pass 

     def download_zip(self,period,dir,rtn_type) :
         get_status = lambda flag : self.get(f"https://return.gst.gov.in/returns/auth/api/offline/download/generate?flag={flag}&rtn_prd={period}&rtn_typ={rtn_type.upper()}",
                                    headers={"Referer":"https://return.gst.gov.in/returns/auth/gstr/offlinedownload"}).json()     
         while True :  
             try : status = get_status(0)
             except : 
                time.sleep(60) 
                continue
             if "data" in  status and "token" not in status["data"] : #already download generated 
                 if datetime.now() - date_parse(status["data"]["timeStamp"])  >= datetime.timedelta(hours=24) : 
                    get_status(1)
                 else : 
                    os.makedirs(dir,exist_ok=True)
                    with open(f"{dir}/{period}.zip","wb+") as f : 
                        f.write( self.get( status["data"]["url"][0] ).content )
                        print(f"{period} donwloaded...")
                    break 
             time.sleep(60)

     def download_json(self,period,dir = None,rtn_type = None) :  
        if dir : 
            os.makedirs(dir,exist_ok=True)
        data = self.get(f"https://gstr2b.gst.gov.in/gstr2b/auth/api/gstr2b/getjson?rtnprd={period}",
                    headers = {"Referer": "https://gstr2b.gst.gov.in/gstr2b/auth/"}).json()
        if "error" in data : 
            if data["error"]["error_cd"] == "RET2B1016" : data = {}
            else : 
                print(data) 
                raise Exception("Error on Download Json")
        else  : 
            data = data["data"]["docdata"]
        if dir : 
            json.dump( data , open(f"{dir}/{period}.json","w+") )
        return data
          
     def read_json(self,period,rtn_type,dir=None) :
         fname_ext = self.rtn_types_ext[rtn_type]
         if dir is None : dir = self.dir 
         dir = dir + "/" + rtn_type
         fname = f"{dir}/{period}.{fname_ext}"
         json_file = fname
         if not os.path.exists(fname) : return None 

         if fname_ext == "zip" : 
            json_file = zipfile.ZipFile(fname).namelist()[0]
            os.system(f"unzip -o {fname}")

         data = defaultdict(list , json.load( open(json_file) ) )
         dfs = {}
         for (type,key) in [("b2b","inv"),("cdnr","nt")] : 
             if rtn_type in ["gstr1"] :  
                df  = pd.DataFrame( [  j | k["itm_det"] | {"ctin":i["ctin"]}  for i in data[type] for j in i[key] for k in j["itms"] ] )
                if len(df.index) : del df["itms"]
             if rtn_type in ["gstr2a","gstr2b"] :
                df  = pd.DataFrame( [  j | k | {"ctin":i["ctin"]}  for i in data[type] for j in i[key] for k in j["items"] ] )
                if len(df.index) : del df["items"]
             df["period"] = period 
             dfs[type] = df
         for type in ["b2cs"] :
             df = pd.DataFrame( data["b2cs"] ) 
             df["period"] = period 
             dfs["b2cs"] = df
         dfs["period"] = period
         return dfs 
     
     def make_report(self,periods,rtn_type,dir_report,filter_func=None,) :
         data = [ self.read_json(month,rtn_type) for month in periods  ]
         data = [ i for i in data if i is not None ]         
         agg = {"txval":sum,"camt":sum,"samt":sum}
         all = []
         for (k,inum_column) in [("b2b","inum"),("cdnr","nt_num"),("b2cs","rt")] :
             df = pd.concat([ i[k] for i in data ] ,axis=0)
             if len(df.index) == 0 : continue 
             if filter_func is not None : 
                if k not in filter_func : continue 
                df = filter_func[k](df)
             t = pd.to_datetime(df['period'],format="%m%Y").dt.to_period('Q-OCT').dt
             if rtn_type in ["gstr2b"] : 
                 df = df.rename(columns={"cgst":"camt","sgst":"samt","ntnum":"nt_num"})

             df["year"] = (t.qyear-1).astype(str) + "-" + t.qyear.astype(str)
             df["count"] = df[inum_column]
             if "nt_num" in df.columns : df = df.rename(columns = {"nt_num" : "inum"})

             writer = pd.ExcelWriter(f"{dir_report}/{rtn_type}_{k}.xlsx") 
             df.groupby("period").aggregate(agg | {"count":"nunique"}).to_excel( writer , sheet_name="Monthly")
             df.groupby("year").aggregate(agg | {"count":"nunique"}).to_excel( writer , sheet_name="Yearly")
             if "ctin" in df.columns : 
                 df_party_sum = df.pivot_table(index=["ctin","period"] , values = agg.keys() , aggfunc=agg, margins=True)
                 df_party_sum.to_excel( writer , sheet_name="Party-Wise")
             df.to_excel(writer,sheet_name="Detailed",index=False)
             writer.close()
             df["type"] = k 
             all.append( df[["period","year","txval","camt","samt","type"]] )
         all = pd.concat(all,axis=0)
         writer = pd.ExcelWriter(f"{dir_report}/{rtn_type}_all.xlsx") 
         all.groupby(["period","type"]).aggregate(agg).to_excel( writer , sheet_name="Monthly")
         all.groupby(["year","type"]).aggregate(agg).to_excel( writer , sheet_name="Yearly")
         all.to_excel(writer,sheet_name="Detailed",index=False)
         writer.close()   
     
     def get_einv_data(self,seller_gstin,period,doctype,inum) : 
         p = datetime.datetime.strptime( "01" + period , "%d%m%Y" )
         year = (p.year - 1) if p.month < 4 else p.year 
         fy = f"{year}-{(year+1)%100}"
         params = {'stin': seller_gstin ,'fy': fy ,'doctype': doctype ,'docnum': str(inum) ,'usertype': 'seller'}
         data = self.get('https://einvoice.gst.gov.in/einvoice/auth/api/getIrnData',
             params=params, headers = { 'Referer': 'https://einvoice.gst.gov.in/einvoice/jsonDownload' }
         ).json()
         if "error" in data : return None     
         data = json.loads(data["data"])["data"]
         signed_inv = data["SignedInvoice"]
         while len(signed_inv) % 4 != 0: signed_inv += "="
         payload = base64.b64decode(signed_inv.split(".")[1] + "==").decode("utf-8")
         inv = json.loads( json.loads(payload)["data"] )
         qrcode = data["SignedQRCode"]
         return inv | { "qrcode" : qrcode }
     
     def upload(self,period,fname) : 
           input(self.getuser()["bname"])
           files = {'upfile': ( "gst.json" , open(fname) , 'application/json', { 'Content-Disposition': 'form-data' })}
           ret_ref = {"Referer": "https://return.gst.gov.in/returns/auth/gstr/offlineupload"}
           ref_id =  self.post(f"https://return.gst.gov.in/returndocs/offline/upload",
                  headers = ret_ref | {"sz" : "304230" }, 
                  data = {  "ty": "ROUZ" , "rtn_typ": "GSTR1" , "ret_period": period } ,files=files).json()
           ref_id = ref_id['data']['reference_id']
           res = self.post("https://return.gst.gov.in/returns/auth/api/gstr1/upload" , headers = ret_ref,
                           json = {"status":"1","data":{"reference_id":ref_id},"fp":period}) 
       
           for times in range(0,90) : 
              time.sleep(1)
              status_data = self.get(f"https://return.gst.gov.in/returns/auth/api/offline/upload/summary?rtn_prd={period}&rtn_typ=GSTR1",
                       headers = ret_ref).json()["data"]["upload"] 
              for status in status_data : 
                  if status["ref_id"] == ref_id : 
                     print( status )
                     if status["status"] == "PE" : 
                         self.get(f" https://return.gst.gov.in/returns/auth/api/offline/upload/error/generate?ref_id={ref_id}&rtn_prd={period}&rtn_typ=GSTR1",headers = ret_ref)
                     return status     

     def get_error(self,period,ref_id,fname) : 
         for times in range(0,40) : 
            time.sleep(1)
            res = self.get(f"https://return.gst.gov.in/returns/auth/api/offline/upload/summary?rtn_prd={period}&rtn_typ=GSTR1",
                     headers = {"Referer": "https://return.gst.gov.in/returns/auth/gstr/offlineupload"}).json()  
            status_data = res["data"]["upload"]
            for status in status_data : 
                if status["ref_id"] == ref_id :
                  if status["er_status"] == "P" : 
                    res = self.get(f"https://return.gst.gov.in/returns/auth/api/offline/upload/error/report/url?token={status['er_token']}&rtn_prd={period}&rtn_typ=GSTR1",
                              headers = {"Referer": "https://return.gst.gov.in/returns/auth/gstr/offlineupload"}) 
                    with open(fname,"wb") as f  : 
                          f.write(res.content) 
                    return None 
         raise Exception("GST Get error timed out")          
     
     def get_period_summary(self,period) : 
         #https://return.gst.gov.in/returns/auth/api/gstr1/summary?rtn_prd=012025
            data = self.get(f"https://return.gst.gov.in/returns/auth/api/gstr1/summary?rtn_prd={period}",
                        headers = {"Referer": "https://return.gst.gov.in/returns/auth/gstr1"}).json()
            if data is not None  : 
                data = { i["sec_nm"] : { "txval" : i.get("ttl_tax",None), 
                                          "cgst" : i.get("ttl_cgst",None) , 
                                          "sgst" : i.get("ttl_sgst",None)
                                          } for i in data["data"]["sec_sum"] }
                return data
            else : 
                raise Exception("GST Get Summary Failed Json data is None")
            
          
def myHash(str) : 
  hash_object = hashlib.md5(str.encode())
  md5_hash = hash_object.hexdigest()
  return hashlib.sha256(md5_hash.encode()).hexdigest()

def sha256_hash(input_str):
    return hashlib.sha256(input_str.encode()).hexdigest()

def extractForm(html,all_forms = False) :
    soup = BeautifulSoup(html, 'html.parser')
    if all_forms : 
      form = {  i["name"]  : i.get("value","") for form in soup.find_all("form") for i in form.find_all('input', {'name': True}) }
    else : 
      form = {  i["name"]  : i.get("value","") for i in soup.find("form").find_all('input', {'name': True}) }
    return form 

class EinvoiceWrongCredentials(WrongCredentials) :  
    pass

class Einvoice(Session) : 
      key = "einvoice"
      base_url = "https://einvoice1.gst.gov.in"
      home = "https://einvoice1.gst.gov.in"
      load_cookies = True
 
      def captcha(self) : 
          self.cookies.clear()
          self.cookies.set("ewb_ld_cookie",value = "292419338.20480.0000" , domain = "ewaybillgst.gov.in")             
          self.form = extractForm( self.get( self.base_url ).text )
          img = self.get("/get-captcha-image").content
          self.user.update_cookies( self.cookies )
          self.user.config["form"] = self.form 
          self.user.save()
          return img 
          
      def login(self,captcha) :
          r = get_curl("einvoice/login")
          salt = self.get("/Home/GetKey").json()["key"]
          md5pwd = hashlib.sha256((myHash(self.password) + salt).encode()).hexdigest()       
          sha_pwd =  sha256_hash(self.password)
          sha_salt_pwd =  sha256_hash(sha_pwd + salt)
          form:dict = self.config.get("form",{}) # type: ignore
          r.data =  form | {'UserLogin.UserName': self.username, 
                                 'UserLogin.Password': sha_salt_pwd , 
                                 "CaptchaCode" : captcha, 
                                 "UserLogin.HiddenPasswordSha":sha_pwd,
                                 "UserLogin.PasswordMD5":md5pwd}
          response  = r.send(self)
          with open("a.html","w+") as f : f.write(response.text)
          is_success = (response.url == f"{self.base_url}/Home/MainMenu")
          error_div  = BeautifulSoup(response.text, 'html.parser').find("div",{"class":"divError"})
          error = error_div.text.strip() if (not is_success) and (error_div is not None) else ""
          if is_success : 
              self.user.update_cookies(self.cookies)
          else : 
              if "captcha" not in error.lower() : 
                  raise EinvoiceWrongCredentials(error)
          return is_success 

      def is_logged_in(self) : 
          try : 
            res = self.get("/Home/MainMenu")
          except Exception as e :
              print("Exception Occured on is_logged_in :",e) 
              return False
          return "/Home/MainMenu" in res.url

      def upload(self,json_data:str)  :  
          bulk_home = self.get("/Invoice/BulkUpload").text
          files = { "JsonFile" : ("eway.json", StringIO(json_data) ,'application/json') }
          form = extractForm(bulk_home)
          upload_home = self.post("/Invoice/BulkUpload" ,  files = files , data = form ).text
          with open("a.html","w+") as f : f.write(upload_home)
          success = pd.read_excel( self.get("/Invoice/ExcelUploadedInvoiceDetails").content )
          failed = pd.read_excel( self.get("/Invoice/FailedInvoiceDetails").content )
          return success , failed 
      
      def get_filed_einvs(self,date) -> pd.DataFrame : 
          """This functions works on today - 2 to today (Only 3 past days data available)"""
          form = extractForm( self.get("/MisRpt").text )
          form["submit"] = "Date"
          form["irp"] = "NIC1"
          form["ToDate"] = date.strftime("%d/%m/%Y")
          table_html = self.post("/MisRpt/MisRptAction",data=form).text
          irn_gen_by_me_excel_bytesio = self.get('/MisRpt/ExcelGenerratedIrnDetails?noofRec=1&Actn=GEN').content
          return pd.read_excel(BytesIO(irn_gen_by_me_excel_bytesio))
          
      #Unverified
      def getinvs(self) : 
          form = extractForm( self.get("/MisRpt").text )
          form["submit"] = "Date"
          form["irp"] = "NIC1"
          fdate = datetime.datetime.strptime(form["FromDate"] ,"%d/%m/%Y")
          todate = datetime.datetime.strptime(form["ToDate"] ,"%d/%m/%Y")
          print(fdate,todate)
          df = []
          while todate >= fdate : 
             table_html = self.post("/MisRpt/MisRptAction",data=form | 
                                        {"ToDate":todate.strftime("%d/%m/%Y")}).text
             tables = pd.read_html( table_html )
             df = pd.read_excel( BytesIO(self.get('/MisRpt/ExcelGenerratedIrnDetails?noofRec=1&Actn=GEN').content) )
             print(df)
             print(tables)
             if len(tables) : 
                table = tables[0] 
                if "Ack No." in table.columns : 
                   df.append(table) 
             todate -= datetime.timedelta(days=1)
          return pd.concat(df) if len(df) > 0 else None
      
      ## Only works in Linux
      #Not working use gst module instead
      def getpdf(self,irn) : 
          form = extractForm( self.get("https://einvoice1.gst.gov.in/Invoice/EInvoicePrint/Print").text )
          form = form | {"ModeofPrint": "IRN" , "PrintOption": "IRN","submit": "Print",
          "InvoiceView.InvoiceDetails.Irn": irn }
          html = self.post("https://einvoice1.gst.gov.in/Invoice/EInvoicePrintAction",data=form).text
          html = re.sub(r'src=".*/(.*?)"','src="\\1"',html)
          html = re.sub(r'href=".*/(.*?)"','href="\\1"',html)
          with open("print_includes/bill.html","w+") as f  : f.write(html)
        #   os.system("google-chrome --headless --disable-gpu --print-to-pdf=print_includes/bill.pdf print_includes/bill.html")
      
      #Unverified
      def upload_eway_bill(self,json_path) : 
        self.get("/SignleSignon/EwayBill").text
        res = self.get("https://ewaybillgst.gov.in/BillGeneration/BulkUploadEwayBill.aspx")
        
        buffer = open(json_path)
        files = { "ctl00$ContentPlaceHolder1$FileUploadControl" : ("eway.json", buffer  ,'application/json') }

        form = extractForm(res.text)        
        res = self.post("https://ewaybillgst.gov.in/BillGeneration/BulkUploadEwayBill.aspx",files = files,data =form)
        with open("a.html","w+") as f : f.write(res.text)

        buffer.seek(0)
        form = extractForm(res.text) | {"ctl00$ContentPlaceHolder1$hdnConfirm": "Y"}
        res = self.post("https://ewaybillgst.gov.in/BillGeneration/BulkUploadEwayBill.aspx",files = files,data =form)        
        with open("a.html","w+") as f : f.write(res.text)
