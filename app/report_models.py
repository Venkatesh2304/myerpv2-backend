import abc
import datetime
from decimal import Decimal
import enum
import os
import pickle
from typing import Callable
from django.db import models
import pandas as pd
from sqlalchemy import create_engine
from django.db import connection
from custom.classes import IkeaDownloader
from django.core.checks import register, Error
from django.apps import apps
from myerpv2 import settings
from app.sql import engine


def decimal_field(required=False, decimal_places=2, **kwargs) -> models.DecimalField:
    required_fields = (
        {"db_default": Decimal("0.00"), "blank": True, "null": True}
        if not required
        else {}
    )
    return models.DecimalField(
        max_digits=12, decimal_places=decimal_places, **required_fields, **kwargs
    )

# class ReportFetcher :
#     def __init__(self,fetcher_method:Callable[int,int]) -> None:
#         self.fetcher_method = fetcher_method

#     def fetch(self, fromd:datetime.date, tod:datetime.date) -> pd.DataFrame|None :
#         return self.fetcher_method(fromd,tod)

class ReportModel(models.Model):
    
    class Report:    
        fetcher = None  # type: ignore
        # Preprocessing options
        column_map: dict = {}
        ignore_last_nrows = 0
        dropna_columns: list[str] = []
        date_format:str|None = "" #None means detect the format automatically

        #caching
        enable_cache = True
        use_cache = False
        _cache_folders = {}

        @classmethod
        def get_cache_dir(cls):
            """Return (and create if needed) a cache dir specific to this subclass."""
            report_cls = cls.__qualname__.split(".")[0] #Class Qualname is like SalesRegisterReport.Report
            if report_cls not in cls._cache_folders:
                path = os.path.join(".cache", report_cls)
                os.makedirs(path, exist_ok=True)
                cls._cache_folders[report_cls] = os.path.abspath(path)
            return cls._cache_folders[report_cls]
        
        @classmethod
        def basic_preprocessing(cls, df: pd.DataFrame) -> pd.DataFrame:
            if cls.ignore_last_nrows > 0:
                df = df.iloc[: -cls.ignore_last_nrows]
            if cls.column_map:
                df = df.rename(columns=cls.column_map)
            if cls.date_format != "" :
                    df["date"] = pd.to_datetime(df["date"], format=cls.date_format).dt.date
            
            if cls.dropna_columns:
                df = df.dropna(subset=cls.dropna_columns, how="any")
            
            return df

        @classmethod
        def custom_preprocessing(cls, df: pd.DataFrame) -> pd.DataFrame:
            return df

        @classmethod
        def fetch_raw_dataframe(cls, fetcher_cls_instance: object, fromd: datetime.date, tod: datetime.date) -> pd.DataFrame:
            if cls.fetcher is None:
                raise NotImplementedError("Fetcher method not implemented.")
            return cls.fetcher(fetcher_cls_instance, fromd, tod)
        
        @classmethod
        def get_dataframe(
            cls, fetcher_cls_instance: object, fromd: datetime.date, tod: datetime.date
        ) -> pd.DataFrame:
            df = cls.fetch_raw_dataframe(fetcher_cls_instance, fromd, tod)
            df = cls.basic_preprocessing(df)
            df = cls.custom_preprocessing(df)
            return df

    class Meta:
        abstract = True
    
    @classmethod
    def save_to_db(cls, df: pd.DataFrame) -> int | None:
        # Collect concrete, non-auto fields (exclude auto PK and m2m)
        fields = []
        for f in cls._meta.get_fields():
            if (
                getattr(f, "concrete", False)
                and not f.many_to_many
                and not f.auto_created
            ):
                if isinstance(
                    f, (models.AutoField, models.BigAutoField, models.SmallAutoField)
                ):
                    continue
                fields.append(f)

        cols = [f.name for f in fields]
        #check if all columns are present in dataframe , if not raise error for all non present columns
        missing_cols = [col for col in cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing columns in dataframe: {', '.join(missing_cols)}")
        inserted_row_count: int | None = df[cols].to_sql(
            cls._meta.db_table, engine, if_exists="append", index=False 
        )
        return inserted_row_count

    @classmethod
    def update_db(
        cls, fetcher_obj: object, fromd: datetime.date, tod: datetime.date , **kwargs
    ) -> int | None:
        raise NotImplementedError("Use subclass with Report.fetcher implemented.")

class DateReportModel(ReportModel):
    #Note: All Models Should have a date field

    class Report(ReportModel.Report):
        @classmethod
        def fetch_raw_dataframe(
            cls, fetcher_cls_instance: object, fromd: datetime.date, tod: datetime.date
        ) -> pd.DataFrame:
            #Load from cache if enabaled & exists
            is_loaded_from_cache = False
            df = None
            if cls.use_cache and cls.enable_cache:
                cache_dir = cls.get_cache_dir()
                cache_path = os.path.join(cache_dir,f"{fromd}_{tod}.pkl")
                if os.path.exists(cache_path) :
                        with open(cache_path,"rb") as f :
                            df = pickle.load(f)
                            is_loaded_from_cache = True
                   
            if not is_loaded_from_cache :
                df: pd.DataFrame = cls.fetcher(fetcher_cls_instance, fromd, tod)  # type: ignore

            if cls.enable_cache and (not is_loaded_from_cache) : 
                cache_dir = cls.get_cache_dir()
                cache_path = os.path.join(cache_dir,f"{fromd}_{tod}.pkl")
                with open(cache_path,"wb+") as f :
                    pickle.dump(df,f)
            
            return df 
    
    class Meta:
        abstract = True
    
    @classmethod
    def update_db(
        cls, fetcher_obj: object, fromd: datetime.date, tod: datetime.date, **kwargs
    ) -> int | None:
        df = cls.Report.get_dataframe(fetcher_obj, fromd, tod)
        cls.objects.filter(date__gte=fromd, date__lte=tod).delete()
        return cls.save_to_db(df)

    @classmethod
    def last_update_date(cls) -> datetime.date | None:
        last_rec = cls.objects.order_by("-date").first()
        if last_rec:
            return last_rec.date
        return None

class SimpleReportModel(ReportModel):
    #No caching
    class Report(ReportModel.Report):
        @classmethod
        def fetch_raw_dataframe(
            cls, fetcher_cls_instance: object, fromd: datetime.date, tod: datetime.date
        ) -> pd.DataFrame:  # type: ignore
            df: pd.DataFrame = cls.fetcher(fetcher_cls_instance)  # type: ignore
            return df
    
    class Meta:
        abstract = True

    @classmethod
    def update_db(cls, fetcher_obj: object, fromd: datetime.date, tod: datetime.date) -> int | None:
        df = cls.Report.get_dataframe(fetcher_obj, fromd, tod)
        cls.objects.all().delete()
        return cls.save_to_db(df) 
    
class SalesRegisterReport(DateReportModel):
    inum = models.CharField(max_length=100, verbose_name="BillRefNo")
    date = models.DateField(verbose_name="Date")
    party_id = models.CharField(max_length=100, verbose_name="Party Code")
    party_name = models.CharField(max_length=255, verbose_name="Party Name", null=True)
    type = models.CharField(max_length=50, verbose_name="Type")
    amt = decimal_field(required=True, verbose_name="Bill Amount + Credit Adjustment")
    ctin = models.CharField(max_length=20, verbose_name="Party GSTIN", null=True)
    tcs = decimal_field(verbose_name="TCS Amt")
    tds = decimal_field(verbose_name="TDS-194R Amt")
    tax = decimal_field(required=True, verbose_name="Net Tax")

    # Discount & Roundoff
    schdisc = decimal_field(verbose_name="SchDisc")
    cashdisc = decimal_field(verbose_name="CashDisc")
    btpr = decimal_field(verbose_name="BTPR SchDisc")
    outpyt = decimal_field(verbose_name="OutPyt Adj")
    ushop = decimal_field(verbose_name="Ushop Redemption")
    pecom = decimal_field(verbose_name="Adjustments")
    roundoff = decimal_field(verbose_name="RoundOff")
    other_discount = decimal_field(
        verbose_name="Other Discount (DisFinAdj + ReversedPayout)"
    )

    class Meta:  # type: ignore
        db_table = "salesregister_report"

    class Report(DateReportModel.Report):
        fetcher = IkeaDownloader.sales_reg
        column_map = {
            "BillRefNo": "inum",
            "Party Name": "party_name",
            "BillDate/Sales Return Date": "date",
            "Party Code": "party_id",
            "SchDisc": "schdisc",
            "CashDisc": "cashdisc",
            "BTPR SchDisc": "btpr",
            "OutPyt Adj": "outpyt",
            "Ushop Redemption": "ushop",
            "Adjustments": "pecom",
            "GSTIN Number": "ctin",
            "RoundOff": "roundoff",
            "TCS Amt": "tcs",
            "TDS-194R Per": "tds",
        }
        ignore_last_nrows = 1

        @classmethod
        def custom_preprocessing(cls, df: pd.DataFrame) -> pd.DataFrame:
            df["tax"] = df["Tax Amt"] - df["SRT Tax"]
            df["amt"] = df["BillValue"] + df["CR Adj"]
            df["other_discount"] = df["DisFin Adj"] + df["Reversed Payouts"]
            df["type"] = df["amt"].apply(lambda x: "salesreturn" if x < 0 else "sales")
            return df

class IkeaGSTR1Report(DateReportModel):
    inum = models.CharField(max_length=30, verbose_name="Invoice No")
    date = models.DateField(verbose_name="Date")
    txval = decimal_field(required=True, decimal_places=3, verbose_name="Taxable Value")
    stock_id = models.CharField(max_length=50, verbose_name="UQC")
    qty = models.IntegerField(verbose_name="Quantity")
    rt = decimal_field(required=True, verbose_name="Tax - Central Tax")
    type = models.CharField(max_length=50, verbose_name="Type")
    hsn = models.CharField(max_length=50, verbose_name="HSN")
    desc = models.CharField(max_length=255, null=True, verbose_name="HSN Description")
    credit_note_no = models.CharField(max_length=100, verbose_name="Debit/Credit No", null=True)
    original_invoice_no = models.CharField(max_length=100, verbose_name="Original Invoice No", null=True)
    party_id = models.CharField(max_length=100, verbose_name="Outlet Code")
    party_name = models.CharField(max_length=255, verbose_name="Outlet Name", null=True)
    ctin = models.CharField(max_length=20, verbose_name="GSTIN of Recipient", null=True)
    cgst = decimal_field(required=False, decimal_places=3,verbose_name="Amount - Central Tax")
    sgst = decimal_field(required=False, decimal_places=3,verbose_name="Amount - State/UT Tax")
    inv_amt = decimal_field(required=True, decimal_places=3,verbose_name="Total Invoice Amount")

    class Meta:  # type: ignore
        db_table = "ikea_gstr1_report"

    class Report(DateReportModel.Report):
        fetcher = IkeaDownloader.gstr_report
        date_format = "%d/%m/%Y"
        column_map = {
            "Invoice No": "inum",
            "Invoice Date": "date",
            "Invoice Value" : "inv_amt",
            "Outlet Code": "party_id",
            "Outlet Name": "party_name",
            "GSTIN of Recipient": "ctin",
            "Amount - Central Tax": "cgst",
            "Amount - State/UT Tax": "sgst",
            "Taxable": "txval",
            "UQC": "stock_id",
            "Total Quantity": "qty",
            "Tax - Central Tax": "rt",
            "HSN": "hsn",
            "HSN Description": "desc",
            "Debit/Credit No": "credit_note_no" ,
            "Original Invoice No": "original_invoice_no"
        }

        @classmethod
        def custom_preprocessing(cls, df: pd.DataFrame) -> pd.DataFrame:
            df["type"] = df["Transactions"].replace({ "SECONDARY BILLING" : "sales" , 
                                                      "SALES RETURN" : "salesreturn", 
                                                      "CLAIMS SERVICE" : "claimservice" },inplace=False)
            df["party_id"] = df["party_id"].fillna("HUL") #For claimservice entries
            df["hsn"] = df["hsn"].astype(str).str.replace(".","")
            return df

class DmgShtReport(DateReportModel):
    inum = models.CharField(max_length=100, verbose_name="Damage Invoice No")
    type = models.CharField(max_length=50, verbose_name="Type (Damage or Shortage)", choices=[("damage","damage"),("shortage","shortage")])
    return_from = models.CharField(max_length=100, verbose_name="Return From (Market/RS)", choices=[("market","market"),("rs","rs")])
    date = models.DateField(verbose_name="Damage Date")
    party_id = models.CharField(max_length=100, verbose_name="Retailer Code")
    party_name = models.CharField(max_length=255, verbose_name="Retailer Name", null=True)
    stock_id = models.CharField(max_length=50, verbose_name="Product Code")
    desc = models.CharField(max_length=255, verbose_name="Product Name", null=True)
    qty = models.IntegerField(verbose_name="Quantity")
    amt = decimal_field(required=True, decimal_places=2, verbose_name="Total TUR Value")

    plg = models.CharField(max_length=100, verbose_name="PLG (DETS,FNB,..)", null=True)
    credit_note_no = models.CharField(max_length=100, verbose_name="Credit Note No", null=True)
    original_invoice_no = models.CharField(max_length=100, verbose_name="Original Invoice No", null=True)

    class Meta:
        db_table = "dmgsht_report"

    class Report(DateReportModel.Report):
        fetcher = lambda ikea,fromd,tod : IkeaDownloader.damage_proposals(ikea,fromd,tod,"sales")
        column_map = { "TRANS REF NO":"inum" , "TRANS DATE":"date" ,  "RETAILER CODE" : "party_id" , "RETAILER NAME" : "party_name",
                       "PRODUCT CODE":"stock_id","PRODUCT NAME" : "desc" ,"QTY/FREE QTY":"qty" ,"TOTAL TUR VALUE":"amt",
                        "TSO PLG": "plg" , "CREDIT NOTE NO" : "credit_note_no" , "Original Bill No" : "original_invoice_no"  }
        @classmethod
        def custom_preprocessing(cls, df: pd.DataFrame) -> pd.DataFrame:
            df["return_from"] = df["TRANSACTION TYPE"].apply(lambda x : "rs" if x.startswith("RS") else "market")
            df["type"] = df["TRANSACTION TYPE"].apply(lambda x : "damage" if x.endswith("DMG") else "shortage")
            df["party_id"] = df["party_id"].fillna("HUL") #For RS entries
            return df

class StockHsnRateReport(SimpleReportModel):
    stock_id = models.CharField(max_length=8, verbose_name="Product Code")
    hsn = models.CharField(max_length=8, verbose_name="HSN")
    rt = decimal_field(required=True, decimal_places=1, verbose_name="Tax Rate")
    class Report(SimpleReportModel.Report):
        fetcher = IkeaDownloader.product_hsn_master
        column_map = { "prod_code":"stock_id","HSN_NUMBER":"hsn","CGST_RATE":"rt" }
        dropna_columns = ["hsn"]
        @classmethod
        def custom_preprocessing(cls, df: pd.DataFrame) -> pd.DataFrame:
            df = df.sort_values("rt")
            df = df.drop_duplicates(subset="stock_id",keep="last")[["stock_id","hsn","rt"]]
            df["hsn"] = df["hsn"].str.replace(".","")
            return df
        
    class Meta: # type: ignore
        db_table = "stockhsnrate_report"

class PartyReport(SimpleReportModel):
    code = models.CharField(max_length=10, primary_key=True, verbose_name="Party Code")
    master_code = models.CharField(max_length=10, verbose_name="Party Master Code", null=True)
    name = models.CharField(max_length=100, verbose_name="Party Name", null=True)
    addr = models.CharField(max_length=150, verbose_name="Address", null=True)
    # pincode = models.CharField(max_length=10, verbose_name="Pincode", null=True)
    beat = models.CharField(max_length=80, verbose_name="Beat", null=True)
    ctin = models.CharField(max_length=20, verbose_name="GSTIN Number", null=True)
    phone = models.CharField(max_length=20, verbose_name="Phone", null=True)
    
    class Report(SimpleReportModel.Report):
        fetcher = IkeaDownloader.party_master
        column_map = {
            "Party Name": "name",
            "Address": "addr",
            "Party Code": "code",
            "Beat": "beat",
            "GSTIN Number": "ctin",
            "Party Master Code": "master_code",
            "Phone": "phone",
        }
        dropna_columns = ["code"]
        @classmethod
        def custom_preprocessing(cls, df: pd.DataFrame) -> pd.DataFrame:
            df = df.drop_duplicates(subset="code")
            strips = lambda df,val : df.str.split(val).str[0].str.strip(" \t,")
            df["phone"] = df["addr"].str.split("PH :").str[1].str.strip()
            df["addr"] = strips( strips( strips( df["addr"] , "TRICHY" )  , "PH :" ) , "N.A" )
            return df

    class Meta:
        db_table = "party_report"

# System check for models
@register()
def reportmodel_date_field_check(app_configs, **kwargs):
    errors: list[Error] = []
    for model in apps.get_models():
        if not issubclass(model, DateReportModel):
            continue
        if model._meta.abstract:
            continue
        try:
            f = model._meta.get_field("date")
            if not isinstance(f, (models.DateField, models.DateTimeField)):
                errors.append(
                    Error(
                        f"`{model.__name__}.date` must be a DateField or DateTimeField.",
                        obj=model,
                        id="reportmodel.E002",
                    )
                )
        except Exception:
            errors.append(
                Error(
                    f"`{model.__name__}` must define a `date` field.",
                    obj=model,
                    id="reportmodel.E001",
                )
            )
    return errors
