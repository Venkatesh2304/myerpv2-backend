import datetime
import json
import pandas as pd
import app.models as models
from django.db.models import Case, When, Value, CharField, Sum, F, FloatField
from django.db.models.query import QuerySet
from django.db.models.functions import Abs, Round
from app.fields import decimal_field
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)  # or str(obj)
        return super().default(obj)

def einv_json_to_str(einv_json: list) -> str:
    return json.dumps(einv_json, cls=DecimalEncoder, indent=4)

def change_einv_dates(einv_json: list, fallback_date: datetime.date) -> list:
    today = datetime.date.today()
    for einv in einv_json:
        date = datetime.datetime.strptime(
                einv["DocDtls"]["Dt"], "%d/%m/%Y"
            ).date()        
        einv["DocDtls"]["Dt"] = (fallback_date if (today - date).days >= 28 else date).strftime("%d/%m/%Y")
    return einv_json

def create_einv_json(
    queryset: QuerySet[models.Sales], seller_json
) -> list:
    """Note: This is vulnerable to Discounts like Outlet Payout"""
    sales_qs = (
        queryset.filter(ctin__isnull=False, irn__isnull=True)
        .annotate(
            gst_type=Case(
                When(ctin__isnull=True, then=Value("b2c")),
                When(type__in=["sales", "claimservice"], then=Value("b2b")),
                default=Value("cdnr"),
                output_field=CharField(),
            ),
            einv_type=Case(
                When(type__in=["sales", "claimservice"], then=Value("INV")),
                default=Value("CRN"),
                output_field=CharField(),
            ),
            txval=Round(Abs(Sum("inventory__txval")), 2),
            cgst=Round(
                Abs(Sum(F("inventory__txval") * F("inventory__rt") / 100)),
                2,
            ),
        )
        .order_by("amt")
        .prefetch_related("inventory", "party")
    )
    einvs = []
    for sale in sales_qs:
        doc_dtls = {
            "Typ": sale.einv_type,  # type: ignore
            "No": sale.inum,
            "Dt": sale.date.strftime("%d/%m/%Y"),
        }

        buyer = sale.party
        if buyer is None:
            raise Exception(f"Party not found for sale {sale.inum}")
        buyer_dtls = {
            "Gstin": sale.ctin,
            "LglNm": buyer.name,
            "Pos": "33",
            "Addr1": buyer.addr[:100],
            "Pin": 620008,
            "Loc": "TRICHY",
            "Stcd": "33",
        }

        val_dtls = {
            "AssVal": round(sale.txval, 2),  # type: ignore
            "CgstVal": round(sale.cgst, 2),  # type: ignore
            "SgstVal": round(sale.cgst, 2),  # type: ignore
            "TotInvVal": round(sale.txval + 2*sale.cgst,2),
            "RndOffAmt": round(sale.roundoff, 2),
            "Discount": round(sale.discount, 2),
        }

        items = []
        for i, inv in enumerate(sale.inventory.all(), start=1):  # type: ignore
            try:
                stock = inv.stock
            except models.Stock.DoesNotExist:
                raise Exception(
                    f"Stock Details not found for inventory id {inv.id} in sale {sale.inum}"
                )

            hsn = stock.hsn
            desc = stock.desc or None
            qty = abs(inv.qty)
            unitprice = abs(round(inv.txval / qty, 2)) if qty else 0
            cgst = abs(round(inv.rt * inv.txval / 100, 2))
            total = abs(round(inv.txval * (1 + 2 * inv.rt / 100), 2))
            rt = round(inv.rt * 2, 1)
            txval = abs(round(inv.txval, 2))
            items.append(
                {
                    "Qty": qty,
                    "IsServc": "N",
                    "HsnCd": hsn,
                    "PrdDesc": desc,
                    "Unit": "NOS",
                    "UnitPrice": unitprice,
                    "TotAmt": txval,
                    "AssAmt": txval,
                    "GstRt": rt,
                    "TotItemVal": total,
                    "CgstAmt": cgst,
                    "SgstAmt": cgst,
                    "SlNo": str(i),
                }
            )

        einv = {
            "Version": "1.1",
            "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B"},
            "DocDtls": doc_dtls,
            "BuyerDtls": buyer_dtls,
            "ValDtls": val_dtls,
            "ItemList": items,
            **seller_json,
        }
        einvs.append(einv)
    return einvs 
