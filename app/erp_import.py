from abc import abstractmethod
import abc
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import decimal
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
from django.db.models import OuterRef, Subquery, Value, DecimalField, QuerySet
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

    @classmethod
    def delete_before_insert(cls, company: Company, args: DateRangeArgs):
        types = ["sales", "salesreturn", "claimservice"]
        inums_qs = cls.model.objects.filter(company=company).filter(
            date__gte=args.fromd, date__lte=args.tod, type__in=types
        )
        batch_delete(inums_qs, 100)

    @classmethod
    @transaction.atomic
    def run_atomic(cls, company: Company, args: DateRangeArgs):
        cls.delete_before_insert(company, args)
        sales_qs = models.SalesRegisterReport.objects.filter(
            company=company, date__gte=args.fromd, date__lte=args.tod
        )
        inventory_qs = models.IkeaGSTR1Report.objects.filter(
            company=company, date__gte=args.fromd, date__lte=args.tod
        )

        # Sales
        sales_objs = sales_qs.filter(type="sales")
        sales_inventory_objs = inventory_qs.filter(type="sales")

        # Sales Return
        date_original_inum_to_cn: defaultdict[tuple, list[str]] = defaultdict(list)
        salesreturn_objs = list(sales_qs.filter(type="salesreturn").order_by("amt"))
        salesreturn_inventory_objs = list(
            inventory_qs.filter(type="salesreturn").order_by("inv_amt")
        )

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

        # ClaimService
        claimservice_inventory_objs = inventory_qs.filter(type="claimservice")
        claimservice_txval: defaultdict[str, decimal.Decimal] = defaultdict(
            lambda: decimal.Decimal("0.000")
        )
        claimservice_tax: defaultdict[str, decimal.Decimal] = defaultdict(
            lambda: decimal.Decimal("0.000")
        )
        for inv_obj in claimservice_inventory_objs:
            claimservice_txval[inv_obj.inum] += inv_obj.txval
            claimservice_tax[inv_obj.inum] += 2 * inv_obj.txval * inv_obj.rt / 100

        claimservice_objs: list[SalesRegisterReport] = []
        for inv_obj in claimservice_inventory_objs.distinct("inum"):
            txval = claimservice_txval[inv_obj.inum]
            tax = claimservice_tax[inv_obj.inum]
            tds = (txval * cls.TDS_PERCENT) / 100

            obj = SalesRegisterReport(
                company=company,
                type="claimservice",
                inum=inv_obj.inum,
                date=inv_obj.date,
                party_id="HUL",
                ctin=inv_obj.ctin,
                amt=txval + tax - tds,
                tds=tds,
            )
            claimservice_objs.append(obj)

        # Insert sales
        salesregister_objs = itertools.chain(
            sales_objs.iterator(chunk_size=1000), salesreturn_objs, claimservice_objs
        )
        model_sales_objs = (
            models.Sales(
                company_id=company.pk,
                type=qs.type,
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
                tds=-qs.tds,
            )
            for qs in salesregister_objs
        )
        models.Sales.objects.bulk_create(model_sales_objs, batch_size=1000)

        # Insert Discount
        # Recreate the iterator with non-zero discounts only
        salesregister_objs = itertools.chain(
            sales_objs.exclude(
                btpr=0,
                outpyt=0,
                ushop=0,
                pecom=0,
                other_discount=0,
            ).iterator(chunk_size=1000),
            salesreturn_objs,
            claimservice_objs,
        )
        model_discount_objs = (
            models.Discount(
                company_id=company.pk,
                bill_id=qs.inum,
                sub_type=discount,
                amt=-value,
            )
            for qs in salesregister_objs
            for discount, value in [
                ("btpr", qs.btpr),
                ("outpyt", qs.outpyt),
                ("ushop", qs.ushop),
                ("pecom", qs.pecom),
                ("other_discount", qs.other_discount),
            ]
            if value != 0
        )
        models.Discount.objects.bulk_create(model_discount_objs, batch_size=1000)

        # Insert inventory
        ikea_gstr_objs = itertools.chain(
            sales_inventory_objs.iterator(chunk_size=1000),
            salesreturn_inventory_objs,
            claimservice_inventory_objs,
        )
        model_inventory_objs = (
            models.Inventory(
                company_id=company.pk,
                bill_id=qs.inum,
                stock_id=qs.stock_id,
                qty=qs.qty,
                rt=qs.rt,
                txval=qs.txval,
            )
            for qs in ikea_gstr_objs
        )
        models.Inventory.objects.bulk_create(model_inventory_objs, batch_size=1000)


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
            rt=Subquery(
                stock_rt_subquery,
                output_field=DecimalField(decimal_places=1, max_digits=3),
            ),
            ctin=Subquery(party_ctin_subquery, output_field=models.CharField()),
        )

        sales_objects = {}
        inventory_objects = []
        for mr in market_returns:
            ctin = mr.ctin or None  # type: ignore
            rt = mr.rt  # type: ignore
            if rt is None:
                print(
                    f"Stock HSN Rate not found for stock {mr.stock_id} , skipping entry"
                )
                continue
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
        objs = (
            models.Stock(
                company=company,
                name=obj.stock_id,
                hsn=obj.hsn,
                rt=obj.rt,
            )
            for obj in models.StockHsnRateReport.objects.filter(
                company=company
            ).iterator()
        )
        models.Stock.objects.bulk_create(
            objs,
            batch_size=2000,
            update_conflicts=True,
            update_fields=["hsn", "rt"],
            unique_fields=["company_id", "name"],
        )


class PartyImport(SimpleImport):
    reports = [models.PartyReport]
    model = models.Party
    delete_all = False

    @classmethod
    @transaction.atomic
    def run_atomic(cls, company: Company, args: EmptyArgs):
        objs = (
            models.Party(
                company=company,
                name=obj.name,
                addr=obj.addr,
                code=obj.code,
                master_code=obj.master_code,
                phone=obj.phone,
                ctin=obj.ctin,
            )
            for obj in models.PartyReport.objects.filter(company=company).iterator()
        )
        models.Party.objects.bulk_create(
            objs,
            batch_size=2000,
            update_conflicts=True,
            update_fields=["addr", "master_code", "name", "phone", "ctin"],
            unique_fields=["company_id", "code"],
        )


class GstFilingImport:
    imports: list[Type[BaseImport]] = [
        SalesImport,
        PartyImport,
        StockImport,
        MarketReturnImport,
    ]

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
        s = time.time()
        for import_class in cls.imports:
            reports_to_update.extend(import_class.reports)  # type: ignore
        # reports_to_update = []
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
        print("Reports Completed in :", time.time() - s)
        print("Reports Imported. Starting Data Import..")
        for import_class in cls.imports:
            arg = args_dict[import_class.arg_type]  # type: ignore
            s = time.time()
            import_class.run_atomic(company, arg)
            print(import_class, time.time() - s)
