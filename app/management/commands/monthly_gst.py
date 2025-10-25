import json
import re
from typing import Callable
from django.db import connection, transaction
import pandas as pd
from app.company_models import Group
from app.report_models import MonthArgs
import app.models as models
from django.db.models import Case, When, Value, CharField, Sum, F, ExpressionWrapper , IntegerField , FloatField , DecimalField , Func
from app.fields import decimal_field
from django.db.models.functions import Coalesce, Round 


def addtable(writer, sheet, name, data, style="default"):
    def style(name, df):
        workbook = writer.book
        worksheet = writer.sheets[sheet]
        merge_format = workbook.add_format(
            {
                "bold": 1,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "fg_color": "yellow",
            }
        )
        worksheet.merge_range(
            row - 1, col, row - 1, col + len(df.columns) - 1, name, merge_format
        )

    if type(data) != list:
        data = [data]
        name = [name]
    row = 2
    col = 1
    for i in range(0, len(data)):
        # data[i] = data[i].dropna(axis='columns')
        data[i].to_excel(
            writer,
            sheet_name=sheet,
            startrow=row,
            startcol=col,
            index=(True if type(data[i]) == pd.pivot_table else False),
        )
        style(name[i], data[i])
        row += 3 + len(data[i].index)


def diff_dataframes(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    names: tuple,
    keys: list,
    one_version_columns: list,
    both_version_columns: list,
    diff_series: Callable[[pd.DataFrame], pd.Series],
):

    cols = (
        keys
        + one_version_columns
        + both_version_columns
        + [col + names[0] for col in both_version_columns]
        + [col + names[1] for col in both_version_columns]
    )
    filter_cols = lambda df: df[[col for col in cols if col in df.columns]]
    df = df1.merge(df2, on=keys, how="outer", suffixes=names, indicator="source")
    only_left = df1.merge(df[df["source"] == "left_only"][keys], on=keys, how="inner")
    only_right = df2.merge(df[df["source"] == "right_only"][keys], on=keys, how="inner")
    both_df = df[df["source"] == "both"]
    diff_df = both_df[diff_series(both_df)]
    for col in one_version_columns:
        col1, col2 = col + names[0], col + names[1]
        diff_df[col] = diff_df[col1].fillna(col2)
    return filter_cols(only_left), filter_cols(only_right), filter_cols(diff_df)


@transaction.atomic
def main():
    cur = connection.cursor()
    conn = connection.connection
    month_arg = MonthArgs(month=9, year=2025)
    period = str(month_arg)
    # models.Sales.objects.filter(date__let).update(gst_period=None)
    group = Group.objects.get(name="devaki")
    coalesce_zero = lambda expr: Coalesce(
        expr, 0, output_field=decimal_field(decimal_places=3)
    )

    qs = models.Sales.objects.filter(gst_period=period, company__group=group).annotate(
        gst_type=Case(
            When(ctin__isnull=True, then=Value("b2c")),
            default=Case(
                When(type__in=["sales", "claimservice"], then=Value("b2b")),
                default=Value("cdnr"),
                output_field=CharField(),
            ),
            output_field=CharField(),
        ),
        txval=coalesce_zero(Sum("inventory__txval")),
        zero_rate_txval=coalesce_zero(
            Sum(
                Case(
                    When(inventory__rt=0, then=F("inventory__txval")),
                    default=Value(0),
                    output_field=decimal_field(decimal_places=3),
                )
            )
        ),
        cgst=coalesce_zero(
            Sum(
                Round(
                    ExpressionWrapper(
                        F("inventory__txval") * F("inventory__rt") / 100,
                        output_field=decimal_field(decimal_places=3),
                    ),
                    precision=3,
                )
            )
        ),
        name=F("party__name"),
    )
    qs = qs.values(
        "company_id",
        "date",
        "inum",
        "party_id",
        "ctin",
        "type",
        "amt",
        "gst_type",
        "txval",
        "zero_rate_txval",
        "cgst",
        "name",
    )
    invs = pd.DataFrame(qs.iterator())

    qs = models.Inventory.objects.filter(company__group=group, sales__gst_period=period).exclude(txval = 0).values("company_id","bill_id").annotate(
        qty=F('qty') * Func(F('txval'), function='SIGN', output_field=IntegerField()),
        # hsn=F("stock__hsn"),
        # rt=F('rt') * 2,
        # cgst=Round(F('rt') * F('txval') / 100,precision=3),
        # sgst=Round(F('rt') * F('txval') / 100,precision=3),
    ).values("company_id","bill_id","qty") #,"hsn","rt","cgst","sgst","txval"
    print(invs)
    items = pd.DataFrame(qs.iterator())
    print(items)
    exit(0)
    
    gst_portal = pd.read_sql(
        f"select * from gstr1_portal where period = '{period}'", con=conn
    )

    registered_invs = invs[invs["gst_type"].isin(["b2b", "cdnr"]) & (invs["cgst"] != 0)]
    missing, extra, mismatch = diff_dataframes(
        registered_invs[
            ["inum", "name", "date", "ctin", "txval", "zero_rate_txval", "cgst"]
        ],
        gst_portal[["inum", "date", "ctin", "txval", "cgst"]],
        names=("_ikea", "_einv"),
        keys=["inum"],
        one_version_columns=["date", "ctin"],
        both_version_columns=["txval", "cgst"],
        diff_series=lambda df: (
            ((df["txval_ikea"] - df["txval_einv"]).abs() > 1)
            & ((df["txval_ikea"] - df["zero_rate_txval"] - df["txval_einv"]).abs() > 1)
        )
        | ((df["cgst_ikea"] - df["cgst_einv"]).abs() > 0.5),
    )

    # Changes

    registered_zero_rate = registered_invs.merge(
        gst_portal[["inum", "txval", "cgst"]],
        on="inum",
        how="left",
        suffixes=("_ikea", "_einv"),
    ).fillna(0)
    registered_zero_rate = registered_zero_rate[
        registered_zero_rate["zero_rate_txval"] != 0
    ]
    is_txval_match = (
        registered_zero_rate["txval_ikea"]
        - registered_zero_rate["zero_rate_txval"]
        - registered_zero_rate["txval_einv"]
    ).abs() < 1
    is_cgst_match = (
        registered_zero_rate["cgst_ikea"] - registered_zero_rate["cgst_einv"] < 0.5
    )
    registered_zero_rate["is_zero_rate"] = is_txval_match & is_cgst_match
    total_registered_zero_rate = registered_zero_rate[
        registered_zero_rate.is_zero_rate
    ]["zero_rate_txval"].sum()

    summary = items.merge(invs[["inum", "gst_type", "type"]], on="inum", how="left")
    gst_type_stats = (
        summary.groupby("gst_type").agg({"txval": "sum", "cgst": "sum"}).round(2)
    )
    for gst_type in ["b2b", "cdnr"]:
        zero_txval = registered_zero_rate[registered_zero_rate["gst_type"] == gst_type][
            "zero_rate_txval"
        ].sum()
        gst_type_stats.loc[gst_type, "txval"] -= zero_txval
    gst_type_stats.loc["registered_zero_rate"] = {"txval": total_registered_zero_rate, "cgst": 0}  # type: ignore
    gst_type_stats = gst_type_stats.reset_index()

    gst_company_type_invoice_type_total_stats = summary.groupby(
        ["company_id", "gst_type", "type"], as_index=False
    ).agg({"txval": "sum", "cgst": "sum"})

    b2b_rt_stats = (
        summary[summary["gst_type"].isin(["b2b", "cdnr"])]
        .groupby("rt")
        .agg({"txval": "sum", "cgst": "sum"})
        .reset_index()
    )
    b2c_rt_stats = (
        summary[summary["gst_type"].isin(["b2c"])]
        .groupby("rt")
        .agg({"txval": "sum", "cgst": "sum"})
        .reset_index()
    )
    rt_stats = pd.merge(
        b2b_rt_stats, b2c_rt_stats, on="rt", how="outer", suffixes=("_b2b", "_b2c")
    ).fillna(0)

    count_stats = (
        summary.groupby("gst_type", as_index=False)
        .agg({"inum": "nunique"})
        .rename(columns={"inum": "count"})
    )
    detailed = invs[
        ["company_id", "inum", "date", "name", "ctin", "amt", "txval", "cgst"]
    ]

    writer = pd.ExcelWriter(f"workings_{period}.xlsx", engine="xlsxwriter")
    addtable(
        writer=writer,
        sheet="Summary",
        name=["SUMMARY (GST TYPE)", "SUMMARY (INVOICE TYPE)", "RATE", "DOCS"],
        data=[
            gst_type_stats,
            gst_company_type_invoice_type_total_stats,
            rt_stats,
            count_stats,
        ],
    )
    # addtable(writer = writer , sheet = "Changes" , name = ["CHANGES"] ,  data = [changes] )
    addtable(
        writer=writer,
        sheet="Einvoice",
        name=["MISSING", "EXTRA", "MISMATCH"],
        data=[missing, extra, mismatch],
    )
    addtable(
        writer=writer,
        sheet="Zero Rate",
        name=["Registered Zero Percent"],
        data=[registered_zero_rate],
    )
    addtable(writer=writer, sheet="Detailed", name=["Detailed"], data=[detailed])
    writer.close()

    items_inum_rt_grouped = items.groupby(by=["inum", "rt"], as_index=False).agg(
        {"txval": "sum", "cgst": "sum", "sgst": "sum"}
    )
    items_inum_rt_grouped = items_inum_rt_grouped.set_index("inum")
    to_file_registered_inums = list(mismatch["inum"]) + list(missing["inum"])
    to_file_registered_invs = invs[invs.inum.isin(to_file_registered_inums)]

    def get_items(inum):
        items = []
        item_row_count = 0
        for _, item_row in items_inum_rt_grouped.loc[[inum]].iterrows():
            item_row_count += 1
            items.append(
                {
                    "num": item_row_count,
                    "itm_det": {
                        "txval": round(abs(item_row.txval), 2),
                        "csamt": 0,
                        "iamt": 0,
                        "rt": round(item_row.rt, 1),
                        "camt": round(abs(item_row.cgst), 2),
                        "samt": round(abs(item_row.sgst), 2),
                    },
                }
            )
        return items

    b2b_json = []
    for ctin, invs_df in to_file_registered_invs[
        to_file_registered_invs.gst_type == "b2b"
    ].groupby("ctin"):
        invs_list = []
        for _, row in invs_df.iterrows():
            invs_list.append(
                {
                    "inum": row.inum,
                    "val": round(abs(row.amt), 2),
                    "idt": row.date.strftime("%d-%m-%Y"),
                    "pos": "33",
                    "rchrg": "N",
                    "inv_typ": "R",
                    "itms": get_items(row.inum),
                }
            )
        b2b_json.append({"ctin": ctin, "inv": invs_list})

    cdnr_json = []
    for ctin, invs_df in to_file_registered_invs[
        to_file_registered_invs.gst_type == "cdnr"
    ].groupby("ctin"):
        invs_list = []
        for _, row in invs_df.iterrows():
            invs_list.append(
                {
                    "nt_num": row.inum,
                    "val": round(abs(row.amt), 2),
                    "nt_dt": row.date.strftime("%d-%m-%Y"),
                    "pos": "33",
                    "rchrg": "N",
                    "inv_typ": "R",
                    "ntty": "C",
                    "itms": get_items(row.inum),
                }
            )
        cdnr_json.append({"ctin": ctin, "nt": invs_list})

    b2cs_json = []
    b2c_items = items[items.inum.isin(invs[invs["gst_type"] == "b2c"].inum)]
    b2c_items_rt_grouped = b2c_items.groupby("rt").agg(
        {"txval": "sum", "cgst": "sum", "sgst": "sum"}
    )
    for rt, item_row in b2c_items_rt_grouped.iterrows():
        b2cs_json.append(
            {
                "txval": round(item_row.txval, 2),
                "rt": round(rt, 1),
                "camt": round(item_row.cgst, 2),
                "samt": round(item_row.sgst, 2),
                "iamt": 0,
                "csamt": 0,
                "sply_ty": "INTRA",
                "typ": "OE",
                "pos": "33",
            }
        )

    # TODO: include extra invoice hsn
    print(invs)
    hsn_splits = [("hsn_b2b", ["b2b", "cdnr"]), ("hsn_b2c", ["b2c"])]
    hsn_json = {}
    for hsn_name, gst_types in hsn_splits:
        hsn_json_items = []
        hsn_items = items[items.inum.isin(invs[invs["gst_type"].isin(gst_types)].inum)]
        hsn_items = hsn_items.groupby(by=["hsn", "rt"], as_index=False).agg(
            {"txval": "sum", "qty": "sum", "cgst": "sum", "sgst": "sum"}
        )
        rt_wise_negative = (
            hsn_items[hsn_items.txval < 0]
            .groupby("rt")
            .agg({"txval": "sum", "cgst": "sum", "sgst": "sum"})
        )
        max_hsn_per_rt = (
            hsn_items.sort_values("txval")
            .drop_duplicates(subset=["rt"], keep="last")
            .set_index("rt")["hsn"]
        )
        row_count = 0
        for _, row in hsn_items[hsn_items.txval >= 0].iterrows():
            row_count += 1
            if (row.hsn == max_hsn_per_rt.loc[row.rt]) and (
                row.rt in rt_wise_negative.index
            ):
                row.txval += rt_wise_negative.loc[row.rt].txval
                row.cgst += rt_wise_negative.loc[row.rt].cgst
                row.sgst += rt_wise_negative.loc[row.rt].sgst
            hsn_json_items.append(
                {
                    "num": row_count,
                    "hsn_sc": row.hsn,
                    "txval": round(row.txval, 2),
                    "qty": round(abs(row.qty)),
                    "rt": round(row.rt, 1),
                    "camt": round(row.cgst, 2),
                    "samt": round(row.sgst, 2),
                    "uqc": ("NOS" if not row.hsn.startswith("99") else "NA"),
                    "iamt": 0,
                    "csamt": 0,
                }
            )
        hsn_json[hsn_name] = hsn_json_items

    invs["inum_prefix"] = invs.inum.str[:2]
    docs_df = invs.groupby(by=["type", "inum_prefix"], as_index=False).agg(
        inum_min=("inum", "min"),
        inum_max=("inum", "max"),
        inum_count=("inum", "nunique"),
    )
    BILL_TYPE1 = {"doc_num": 1, "doc_typ": "Invoices for outward supply", "docs": []}
    BILL_TYPE2 = {"doc_num": 5, "doc_typ": "Credit Note", "docs": []}
    BILL_TYPES = {
        "shortage": BILL_TYPE2,
        "damage": BILL_TYPE2,
        "salesreturn": BILL_TYPE2,
        "sales": BILL_TYPE1,
        "claimservice": BILL_TYPE1,
    }
    for _, row in docs_df.iterrows():
        docs = BILL_TYPES[row.type]["docs"]
        if row.inum_count > 5:
            serial_num = lambda inum: int(re.search(r"\d+$", inum).group(0).lstrip("0"))
            tot_num = serial_num(row.inum_max) - serial_num(row.inum_min) + 1
        else:
            tot_num = row.inum_count
        docs.append(
            {
                "num": len(docs) + 1,
                "to": row.inum_max,
                "from": row.inum_min,
                "totnum": tot_num,
                "cancel": tot_num - row.inum_count,
                "net_issue": row.inum_count,
            }
        )
    docs_json = {"doc_det": [BILL_TYPE1, BILL_TYPE2]}
    nil_rated_json = (
        {
            "nil": {
                "inv": [
                    {
                        "sply_ty": "INTRAB2B",
                        "expt_amt": 0,
                        "ngsup_amt": 0,
                        "nil_amt": round(total_registered_zero_rate, 2),
                    }
                ]
            }
        }
        if total_registered_zero_rate > 1
        else {}
    )

    gstin = "29AAACR8573R1ZV"  # get_user()["gstin"]

    gst_json = {
        "b2b": b2b_json,
        "cdnr": cdnr_json,
        "b2cs": b2cs_json,
        "hsn": hsn_json,
        "doc_issue": docs_json,
        "gstin": gstin,
        "fp": period,
        "version": "GST3.0.4",
        "hash": "hash",
    } | nil_rated_json
    with open(f"gstr1_{period}.json", "w+") as f:
        json.dump(gst_json, f, indent=4)


main()
exit(0)
