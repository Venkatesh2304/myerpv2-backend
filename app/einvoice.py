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


def create_einv_json(
    queryset: QuerySet[models.Sales], seller_json, date_fn=None
) -> str:
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
    for sale in sales_qs[:1]:
        doc_dtls = {
            "Typ": sale.einv_type,  # type: ignore
            "No": sale.inum,
            "Dt": (sale.date if date_fn is None else date_fn(sale)).strftime(
                "%d/%m/%Y"
            ),
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
            "TotInvVal": round(sale.amt, 2),
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
            desc = stock.desc or ""
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
                    "Unit": "PCS",
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
    return json.dumps(einvs, indent=4, cls=DecimalEncoder)
