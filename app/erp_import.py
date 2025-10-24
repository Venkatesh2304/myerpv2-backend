from abc import abstractmethod
import abc
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import itertools
import time
import tracemalloc
from typing import Generic, Type
from django.db import connection, transaction
import pandas as pd
from app.company_models import Company
import app.models as models
from custom.classes import IkeaDownloader
from app.sql import engine
from app.report_models import (
    CompanyReportModel,
    ArgsT,
    ReportArgs,
    DateRangeArgs,
    EmptyArgs,
    SalesRegisterReport,
)
from django.db.models import OuterRef, Subquery, Value, FloatField, QuerySet
from django.db.models.functions import Coalesce


def batch_delete(queryset: QuerySet, batch_size: int):
    pks = list(queryset.values_list("pk", flat=True).iterator())
    for i in range(0, len(pks), batch_size):
        batch_pks = pks[i : i + batch_size]
        queryset.model.objects.filter(pk__in=batch_pks).delete()


# TODO: Strict checks
class BaseImport(Generic[ArgsT]):

    arg_type: Type[ArgsT]
    model: Type[models.models.Model]
    reports: list[Type[CompanyReportModel[ArgsT]]] = []

    @classmethod
    def update_reports(cls, company: Company, args: ArgsT):
        # Update the Reports
        inserted_row_counts = {}
        for report in cls.reports:
            # TODO: Better ways to log and handle errors
            inserted_row_counts[report.__name__] = report.update_db(
                IkeaDownloader(), company, args
            )

    @classmethod
    @abstractmethod
    def basic_run(cls, company: Company, args: ArgsT):
        raise NotImplementedError("Basic Run method not implemented")

    @classmethod
    @abstractmethod
    def run_atomic(cls, company: Company, args: ArgsT):
        raise NotImplementedError("Run Atomic method not implemented")

    @classmethod
    def run(cls, company: Company, args: ArgsT):
        cls.update_reports(company, args)
        cls.run_atomic(company, args)


class DateImport(abc.ABC, BaseImport[DateRangeArgs]):
    arg_type = DateRangeArgs

    @classmethod
    @abstractmethod
    def delete_before_insert(cls, company: Company, args: DateRangeArgs):
        raise NotImplementedError("Delete before insert method not implemented")

    @classmethod
    def basic_run(cls, company: Company, args: DateRangeArgs):
        cls.delete_before_insert(company, args)
        # Delete the existing rows in the date range (cascading delete)
        cur = connection.cursor()
        fromd_str = args.fromd.strftime("%Y-%m-%d")
        tod_str = args.tod.strftime("%Y-%m-%d")

        # Create a temp tables for the report tables (with the filtered date)
        # Temp table name : eg: salesregister_report => salesregister_temp
        # The table exists only for the duration of the transaction
        for report in cls.reports:
            db_table = report._meta.db_table
            cur.execute(
                f"""CREATE TEMP TABLE {db_table.replace("_report","_temp")} ON COMMIT DROP AS 
                                SELECT * FROM {db_table} WHERE company_id = '{company.pk}' AND 
                                                                date >= '{fromd_str}' AND date <= '{tod_str}'"""
            )
        return cur


class SimpleImport(abc.ABC, BaseImport[EmptyArgs]):
    arg_type = EmptyArgs
    delete_all = False

    @classmethod
    def basic_run(cls, company: Company, args: EmptyArgs):
        if cls.delete_all:
            cls.model.objects.filter(company=company).delete()
        cur = connection.cursor()
        return cur


class SalesImport(DateImport):
    reports = [models.SalesRegisterReport, models.IkeaGSTR1Report]
    model = models.Sales
    TDS_PERCENT = 2

    @staticmethod
    def insert_gstr(cur, type):
        cur.execute(
            f"""
            INSERT INTO app_stock (company_id,name, hsn, rt)
            SELECT DISTINCT ON(company_id,stock_id) gstr1.company_id, gstr1.stock_id, gstr1.hsn, gstr1.rt
            FROM {type}_gstr1 as gstr1
            ON CONFLICT (company_id,name) DO UPDATE SET hsn = EXCLUDED.hsn , rt = EXCLUDED.rt
        """
        )
        cur.execute(
            f"""
            INSERT INTO app_inventory (company_id,bill_id, stock_id, qty, txval, rt)
            SELECT gstr1.company_id, gstr1.inum, gstr1.stock_id, gstr1.qty, gstr1.txval, gstr1.rt
            FROM {type}_gstr1 as gstr1
        """
        )

    @staticmethod
    def insert_sr(cur, type):
        # Insert Sales
        cur.execute(
            f"""
            INSERT INTO app_sales (company_id,type,inum,date,party_id,amt,ctin,discount,roundoff,tcs,tds)
            SELECT company_id,'{type}' as type , sr.inum, sr.date, sr.party_id, -sr.amt, sr.ctin, 
                    -COALESCE(sr.btpr + sr.outpyt + sr.ushop + sr.pecom + sr.other_discount,0) as discount,
                    sr.roundoff,sr.tcs,sr.tds
            FROM {type}_sr as sr
        """
        )

        # Insert Discount
        discount_types = ["btpr", "outpyt", "ushop", "pecom", "other_discount"]
        for sub_type in discount_types:
            cur.execute(
                f"""
            INSERT INTO app_discount (company_id,bill_id, sub_type, amt)
            SELECT company_id,sr.inum as bill_id , '{sub_type}', -COALESCE(sr.{sub_type}, 0) as amt
            FROM  {type}_sr as sr
            """
            )

    @staticmethod
    def create_type_tables(cur, type):
        """Create temp tables for type_sr and type_gstr1 for the given type"""
        cur.execute(
            f"""CREATE TEMP TABLE {type}_sr ON COMMIT DROP AS 
                                   SELECT * FROM salesregister_temp WHERE type = '{type}'"""
        )
        cur.execute(
            f"""CREATE TEMP TABLE {type}_gstr1 ON COMMIT DROP AS 
                                    SELECT * FROM ikea_gstr1_temp WHERE type = '{type}'"""
        )

    @classmethod
    def delete_before_insert(cls, company: Company, args: DateRangeArgs):
        types = ["salesreturn", "claimservice"] #"sales",
        inums_qs = cls.model.objects.filter(company=company).filter(
            date__gte=args.fromd, date__lte=args.tod, type__in=types
        )
        batch_delete(inums_qs, 100)

    @classmethod
    @transaction.atomic
    def run_atomic(cls, company: Company, args: DateRangeArgs):
        # cur = cls.basic_run(company,args)
        cls.delete_before_insert(company, args)
        sales_qs = models.SalesRegisterReport.objects.filter(
            company=company, date__gte=args.fromd, date__lte=args.tod
        )
        inventory_qs = models.IkeaGSTR1Report.objects.filter(
            company=company, date__gte=args.fromd, date__lte=args.tod
        )

        sales_objs = [] #sales_qs.filter(type="sales")
        sales_inventory_objs = [] #inventory_qs.filter(type="sales")

        date_original_inum_to_cn: defaultdict[tuple, list[str]] = defaultdict(list)
        salesreturn_inventory_objs = list(
            inventory_qs.filter(type="salesreturn").order_by("inv_amt")
        )
        salesreturn_objs = list(sales_qs.filter(type="salesreturn").order_by("amt"))

        for obj in salesreturn_inventory_objs:
            obj.inum = obj.credit_note_no
            obj.txval = -obj.txval
            inums = date_original_inum_to_cn[(obj.date, obj.original_invoice_no)]
            if obj.inum not in inums:
                inums.append(obj.credit_note_no)

        for obj in salesreturn_objs:
            obj.roundoff = -obj.roundoff
            inums = date_original_inum_to_cn[(obj.date, obj.inum)]
            if len(inums) == 0:
                print(
                    "No matching credit note found for sales register entry ",
                    obj.inum,
                    obj.date,
                    "in ikea gstr1",
                )
            inum = inums.pop(0)
            obj.inum = inum

        claimservice_inventory_objs = inventory_qs.filter(type="claimservice")
        claimservice_objs_maps: dict[str, SalesRegisterReport] = {}
        for inv_obj in claimservice_inventory_objs:
            if inv_obj.inum not in claimservice_objs_maps:
                claimservice_objs_maps[inv_obj.inum] = SalesRegisterReport(
                    company=company,
                    inum=inv_obj.inum,
                    date=inv_obj.date,
                    party_id="HUL",
                    ctin=inv_obj.ctin,
                    amt=0,
                    tds=0
                )
            obj = claimservice_objs_maps[inv_obj.inum]
            obj.amt = inv_obj.txval*(100+2*inv_obj.rt- cls.TDS_PERCENT)/100
            obj.tds = -inv_obj.txval*cls.TDS_PERCENT/100

        for qs in claimservice_objs_maps.values():
            qs.amt = round(qs.amt,3)
        claimservice_objs = [] #list(claimservice_objs_maps.values())
        salesregister_objs = (
            models.Sales(
                company_id=company.pk,
                type="sales",
                inum=qs.inum,
                date=qs.date,
                party_id=qs.party_id,
                amt=-qs.amt,
                ctin=qs.ctin,
                discount=-(
                    qs.btpr + qs.outpyt + qs.ushop + qs.pecom + qs.other_discount
                ),
                roundoff=qs.roundoff,
                tcs=qs.tcs,
                tds=qs.tds,
            )
            for qs in itertools.chain(sales_objs, salesreturn_objs, claimservice_objs)
        )
        models.Sales.objects.bulk_create(salesregister_objs, batch_size=1000)
        ikea_gstr_objs = (
            models.Inventory(
                company_id=company.pk,
                bill_id=qs.inum,
                stock_id=qs.stock_id,
                qty=qs.qty,
                rt=qs.rt,
                txval=qs.txval,
            )
            for qs in itertools.chain(
                sales_inventory_objs,
                salesreturn_inventory_objs,
                claimservice_inventory_objs,
            )
        )
        models.Inventory.objects.bulk_create(ikea_gstr_objs, batch_size=1000)
        # print("Memory used : ",tracemalloc.get_traced_memory())

        # cls.create_type_tables(cur,'sales')
        # cls.insert_sr(cur,'sales')
        # cls.insert_gstr(cur,'sales')

        # cls.create_type_tables(cur,'salesreturn')
        # #Insert salesreturn to app_sales
        # cur.execute(f"""
        #     WITH modified_gstr1 AS (
        #         SELECT
        #             ROW_NUMBER() OVER (PARTITION BY date, original_invoice_no ORDER BY inv_amt) AS row_number,
        #             credit_note_no,
        #             date,
        #             original_invoice_no
        #         FROM salesreturn_gstr1
        #     ),
        #     sr_with_rownum AS (
        #         SELECT *,
        #             ROW_NUMBER() OVER (PARTITION BY date, inum ORDER BY amt) AS row_number
        #         FROM salesreturn_sr
        #     )

        #     UPDATE salesreturn_sr AS sr
        #     SET
        #         roundoff = -sr.roundoff,
        #         inum = mg.credit_note_no
        #     FROM modified_gstr1 AS mg
        #     JOIN sr_with_rownum AS swr
        #     ON swr.date = mg.date
        #     AND swr.inum = mg.original_invoice_no
        #     AND swr.row_number = mg.row_number
        #     WHERE sr.id = swr.id;
        # """)
        # cur.execute(f"UPDATE salesreturn_gstr1 SET inum = credit_note_no , txval = -txval")

        # cls.insert_sr(cur,'salesreturn')
        # cls.insert_gstr(cur,'salesreturn')

        # cls.create_type_tables(cur,'claimservice')
        # cur.execute(f"""
        #     INSERT INTO app_sales (company_id,type,inum,date,party_id,ctin,amt,tds)
        #     SELECT distinct on (company_id,inum) company_id, 'claimservice' , inum , date , 'HUL' , ctin ,
        #             -(select ROUND(sum(txval*(100+2*rt-{cls.TDS_PERCENT})/100),3) from claimservice_gstr1 as cs where cs.inum = claimservice_gstr1.inum) as amt,
        #             -(select ROUND(sum(txval*{cls.TDS_PERCENT}/100),3) from claimservice_gstr1 as cs where cs.inum = claimservice_gstr1.inum) as tds
        #     FROM claimservice_gstr1
        # """)
        # cls.insert_gstr(cur,'claimservice')


class MarketReturnImport(DateImport):
    reports = [models.DmgShtReport]
    model = models.Sales

    @classmethod
    def delete_before_insert(cls, company: Company, args: DateRangeArgs):
        types = ["damage", "shortage"]
        inums_qs = cls.model.objects.filter(company=company).filter(
            date__gte=args.fromd, date__lte=args.tod, type__in=types
        )
        inums_qs.delete()

    @classmethod
    @transaction.atomic
    def run_atomic(cls, company: Company, args: DateRangeArgs):

        stock_rt_subquery = models.Stock.objects.filter(
            company=company, name=OuterRef("stock_id")
        ).values("rt")[:1]

        party_ctin_subquery = (
            models.Sales.objects.filter(company=company, party_id=OuterRef("party_id"))
            .order_by("-date")
            .values("ctin")[:1]
        )

        market_returns = models.DmgShtReport.objects.filter(
            return_from="market", company=company
        ).annotate(
            rt=Subquery(stock_rt_subquery, output_field=FloatField()),
            ctin=Subquery(party_ctin_subquery, output_field=models.CharField()),
        )

        sales_objects = {}
        inventory_objects = []
        for mr in market_returns:
            ctin = mr.ctin  # type: ignore
            rt = mr.rt  # type: ignore
            txval = round((float(mr.amt) * 100 / (100 + 2 * float(rt))), 3) if rt else 0

            if mr.inum not in sales_objects:
                sales_objects[mr.inum] = models.Sales(
                    company=company,
                    type=mr.type,
                    inum=mr.inum,
                    date=mr.date,
                    party_id=mr.party_id,
                    ctin=ctin,
                    amt=0,
                )

            sales_objects[mr.inum].amt += mr.amt
            inventory_objects.append(
                models.Inventory(
                    company=company,
                    bill_id=mr.inum,
                    stock_id=mr.stock_id,
                    qty=mr.qty,
                    rt=rt,
                    txval=txval,
                )
            )

        models.Sales.objects.bulk_create(sales_objects.values())
        models.Inventory.objects.bulk_create(inventory_objects)


class StockImport(SimpleImport):
    reports = [models.StockHsnRateReport]
    model = models.Stock
    delete_all = False

    @classmethod
    @transaction.atomic
    def run_atomic(cls, company: Company, args: EmptyArgs):
        cur = cls.basic_run(company, args)
        cur.execute(
            f"""
            INSERT INTO app_stock (company_id, name, hsn, rt)
            SELECT company_id, stock_id, hsn , rt
            FROM stockhsnrate_report
            ON CONFLICT (company_id,name) DO UPDATE SET hsn = EXCLUDED.hsn , rt = EXCLUDED.rt
        """
        )


class PartyImport(SimpleImport):
    reports = [models.PartyReport]
    model = models.Party
    delete_all = False

    @classmethod
    @transaction.atomic
    def run_atomic(cls, company: Company, args: EmptyArgs):
        cur = cls.basic_run(company, args)
        cur.execute(
            f"""
            INSERT INTO app_party (company_id,name,addr,code,master_code,phone,ctin)
            SELECT company_id,name,addr,code,master_code,phone,ctin
            FROM party_report
            ON CONFLICT (company_id,code) DO UPDATE SET addr = EXCLUDED.addr , name = EXCLUDED.name ,
                master_code = EXCLUDED.master_code , phone = EXCLUDED.phone , ctin = EXCLUDED.ctin
        """
        )


class GstFilingImport:
    imports: list[Type[BaseImport]] = [
        SalesImport
    ]  # SalesImport,PartyImport,StockImport,MarketReturnImport

    @classmethod
    def report_update_thread(
        cls, report: CompanyReportModel, company: Company, args: ReportArgs
    ):
        inserted_count = report.update_db(IkeaDownloader(), company, args)
        print(f"Report {report.__name__} updated with {inserted_count} rows")
        return inserted_count

    @classmethod
    def run(cls, company: Company, args_dict: dict[Type[ReportArgs], ReportArgs]):
        reports_to_update = []
        for import_class in cls.imports:
            reports_to_update.extend(import_class.reports)  # type: ignore
        reports_to_update = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for report_model in reports_to_update:
                arg = args_dict[report_model.arg_type]  # type: ignore
                futures.append(executor.submit(cls.report_update_thread, report_model, company, arg))  # type: ignore

            for future in as_completed(futures):
                try:
                    result = future.result()  # This re-raises any exception
                    print(result)
                except Exception as e:
                    print(e)
        print("Reports Imported. Starting Data Import..")
        for import_class in cls.imports:
            arg = args_dict[import_class.arg_type]  # type: ignore
            s = time.time()
            import_class.run_atomic(company, arg)
            print(import_class, time.time() - s)
