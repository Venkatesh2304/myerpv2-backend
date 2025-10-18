from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import connection,transaction
import app.models as models
from custom.classes import IkeaDownloader
from app.sql import engine
from app.report_models import ReportModel
#TODO: Strict checks 

class BaseImport :
    reports:list[ReportModel] = []
    model:models.models.Model = None 
    @classmethod
    def update_reports(cls,fromd,tod) : 
        #Update the Reports
        inserted_row_counts = {}
        for report in cls.reports :
            #TODO: Better ways to log and handle errors
            inserted_row_counts[report.__name__] = report.update_db(IkeaDownloader(),fromd,tod)

    @classmethod
    def basic_run(cls,fromd,tod)  :
        raise NotImplementedError("Basic Run method not implemented")
    
    @classmethod
    def run_atomic(cls,fromd,tod) :
        raise NotImplementedError("Run Atomic method not implemented")

    @classmethod
    def run(cls,fromd,tod) :
        cls.update_reports(fromd,tod)
        cls.run_atomic(fromd,tod)
    
class DateImport(BaseImport) :
    @classmethod
    def basic_run(cls,fromd,tod) :
        #Delete the existing rows in the date range (cascading delete)
        deleted_count, _ = cls.model.objects.filter(date__gte=fromd,date__lte=tod).delete()
        cur = connection.cursor()
        fromd_str = fromd.strftime('%Y-%m-%d')
        tod_str = tod.strftime('%Y-%m-%d')
        
        #Create a temp tables for the report tables (with the filtered date)
        #Temp table name : eg: salesregister_report => salesregister_temp
        #The table exists only for the duration of the transaction
        for report in cls.reports : 
            db_table = report._meta.db_table
            cur.execute(f"""CREATE TEMP TABLE {db_table.replace("_report","_temp")} ON COMMIT DROP AS 
                                SELECT * FROM {db_table} WHERE date >= '{fromd_str}' AND date <= '{tod_str}'""")
        return cur

class SimpleImport(BaseImport) :
    delete_all = False
    @classmethod
    def basic_run(cls, fromd, tod):
        if cls.delete_all :
            cls.model.objects.all().delete()
        cur = connection.cursor()
        return cur

class SalesImport(DateImport) : 
    reports = [models.SalesRegisterReport,models.IkeaGSTR1Report]
    model  = models.Sales
    TDS_PERCENT = 2

    @staticmethod
    def insert_gstr(cur,type) : 
        cur.execute(f"""
            INSERT INTO app_stock (name, hsn, rt)
            SELECT DISTINCT ON(stock_id)  gstr1.stock_id, gstr1.hsn, gstr1.rt
            FROM {type}_gstr1 as gstr1
            ON CONFLICT (name) DO UPDATE SET hsn = EXCLUDED.hsn , rt = EXCLUDED.rt
        """)
        cur.execute(f"""
            INSERT INTO app_inventory (bill_id, stock_id, qty, txval, rt)
            SELECT gstr1.inum, gstr1.stock_id, gstr1.qty, gstr1.txval, gstr1.rt
            FROM {type}_gstr1 as gstr1
        """)
        
    @staticmethod
    def insert_sr(cur,type) : 
        #Insert Sales  
        cur.execute(f"""
            INSERT INTO app_sales (type,inum,date,party_id,amt,ctin,discount,roundoff,tcs,tds)
            SELECT '{type}' as type , sr.inum, sr.date, sr.party_id, -sr.amt, sr.ctin, 
                    -COALESCE(sr.btpr + sr.outpyt + sr.ushop + sr.pecom + sr.other_discount,0) as discount,
                    sr.roundoff,sr.tcs,-1
            FROM {type}_sr as sr
        """)

        #Insert Discount
        discount_types = ['btpr','outpyt','ushop','pecom','other_discount']
        for sub_type in discount_types:
            cur.execute(f"""
            INSERT INTO app_discount (bill_id, sub_type, amt)
            SELECT sr.inum as bill_id , '{sub_type}', -COALESCE(sr.{sub_type}, 0) as amt
            FROM  {type}_sr as sr
            """)

    @staticmethod
    def create_type_tables(cur,type) :
        """Create temp tables for type_sr and type_gstr1 for the given type"""
        cur.execute(f"""CREATE TEMP TABLE {type}_sr ON COMMIT DROP AS 
                                   SELECT * FROM salesregister_temp WHERE type = '{type}'""")
        cur.execute(f"""CREATE TEMP TABLE {type}_gstr1 ON COMMIT DROP AS 
                                    SELECT * FROM ikea_gstr1_temp WHERE type = '{type}'""")
        
    @classmethod
    @transaction.atomic
    def run_atomic(cls,fromd,tod) : 
        cur = cls.basic_run(fromd,tod)
        cls.create_type_tables(cur,'sales')
        cls.insert_sr(cur,'sales')
        cls.insert_gstr(cur,'sales')

        cls.create_type_tables(cur,'salesreturn')
        #Insert salesreturn to app_sales
        cur.execute(f"""
            WITH modified_gstr1 AS (
                SELECT 
                    ROW_NUMBER() OVER (PARTITION BY date, original_invoice_no ORDER BY inv_amt) AS row_number, 
                    credit_note_no, 
                    date, 
                    original_invoice_no 
                FROM salesreturn_gstr1
            ),   
            sr_with_rownum AS (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY date, inum ORDER BY amt) AS row_number
                FROM salesreturn_sr
            )
                    
            UPDATE salesreturn_sr AS sr
            SET 
                roundoff = -sr.roundoff,
                inum = mg.credit_note_no
            FROM modified_gstr1 AS mg
            JOIN sr_with_rownum AS swr 
            ON swr.date = mg.date
            AND swr.inum = mg.original_invoice_no
            AND swr.row_number = mg.row_number
            WHERE sr.id = swr.id;            
        """)
        cur.execute(f"UPDATE salesreturn_gstr1 SET inum = credit_note_no , txval = -txval")
        cls.insert_sr(cur,'salesreturn')
        cls.insert_gstr(cur,'salesreturn')
        
        cls.create_type_tables(cur,'claimservice')
        cur.execute(f"""
            INSERT INTO app_sales (type,inum,date,party_id,ctin,amt,tds)
            SELECT distinct on (inum) 'claimservice' , inum , date , 'HUL' , ctin ,
                    -(select ROUND(sum(txval*(100+2*rt-{cls.TDS_PERCENT})/100),3) from claimservice_gstr1 as cs where cs.inum = claimservice_gstr1.inum) as amt, 
                    -(select ROUND(sum(txval*{cls.TDS_PERCENT}/100),3) from claimservice_gstr1 as cs where cs.inum = claimservice_gstr1.inum) as tds
            FROM claimservice_gstr1 
        """)
        cls.insert_gstr(cur,'claimservice')

class MarketReturnImport(DateImport):
    reports = [models.DmgShtReport]
    model = models.Sales

    @classmethod
    @transaction.atomic
    def run_atomic(cls,fromd,tod) : 
        #TODO: Dependency on stock and party details
        cur = cls.basic_run(fromd,tod)
        cur.execute(f"""
            CREATE TEMP TABLE marketreturn ON COMMIT DROP AS 
                SELECT type , inum , date , party_id  , 
                       -amt as amt , 
                       (SELECT ctin FROM app_sales WHERE party_id = mr.party_id order by date DESC limit 1) as ctin ,
                       (SELECT rt FROM app_inventory where stock_id = mr.stock_id order by id DESC limit 1) as rt ,
                        0 as txval , 
                        stock_id , qty   
                FROM dmgsht_temp as mr WHERE return_from = 'market'
        """)
        cur.execute("UPDATE marketreturn SET txval = ROUND((amt*100/(100 + 2*rt))::numeric ,3)")
        cur.execute(f"""
            INSERT INTO app_sales (type,inum,date,party_id,ctin,amt)
            SELECT  DISTINCT ON(inum) 
                    type , inum, date, party_id , ctin ,
                    (SELECT sum(amt) from marketreturn where inum = mr.inum) as amt
            FROM marketreturn as mr
        """)
        cur.execute(f"""
            INSERT INTO app_inventory (bill_id, stock_id, qty, rt, txval)
            SELECT inum , stock_id , qty , rt , txval 
            FROM marketreturn as mr
        """
        )

class StockImport(SimpleImport):
    reports = [models.StockHsnRateReport]
    model = models.Stock
    delete_all = False

    @classmethod
    @transaction.atomic
    def run_atomic(cls,fromd,tod) :
        cur = cls.basic_run(fromd,tod)
        cur.execute(f"""
            INSERT INTO app_stock (name, hsn, rt)
            SELECT stock_id, hsn , rt
            FROM stockhsnrate_report
            ON CONFLICT (name) DO UPDATE SET hsn = EXCLUDED.hsn , rt = EXCLUDED.rt
        """)

class PartyImport(SimpleImport):
    reports = [models.PartyReport]
    model = models.Party
    delete_all = False

    @classmethod
    @transaction.atomic
    def run_atomic(cls,fromd,tod) :
        cur = cls.basic_run(fromd,tod)
        cur.execute(f"""
            INSERT INTO app_party (name,addr,code,master_code,phone,ctin)
            SELECT name,addr,code,master_code,phone,ctin
            FROM party_report
            ON CONFLICT (code) DO UPDATE SET addr = EXCLUDED.addr , name = EXCLUDED.name ,
                master_code = EXCLUDED.master_code , phone = EXCLUDED.phone , ctin = EXCLUDED.ctin
        """)

class GstFilingImport :
    imports:list[BaseImport] = [SalesImport,PartyImport,StockImport,MarketReturnImport]

    @classmethod
    def report_update_thread(cls,report,fromd,tod) :
        inserted_count = report.update_db(IkeaDownloader(),fromd,tod)
        print(f"Report {report.__name__} updated with {inserted_count} rows")
        return inserted_count
        
    @classmethod
    def run(cls,fromd,tod) :
        reports_to_update:list[ReportModel] = []
        for import_class in cls.imports :
            reports_to_update.extend(import_class.reports)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(cls.report_update_thread ,r, fromd, tod): r for r in reports_to_update}
            for future in as_completed(futures):
                report = futures[future]
                try:
                    result = future.result()  # This re-raises any exception
                    print(result)
                except Exception as e:
                    print(f"Report {report.__name__} generated an exception: {e}")
                    
        for import_class in cls.imports :
            import_class.run_atomic(fromd,tod)
