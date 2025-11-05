import calendar
from collections import defaultdict
import datetime
import json
import os
import re
import time
from typing import Callable, Protocol, ParamSpec, TypeVar, Type, Any
from functools import wraps
from django import template
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from app import gst
from app.einvoice import create_einv_json
from custom import Session
from custom.classes import Gst, Einvoice  # type: ignore
from django.http import FileResponse, HttpResponse, JsonResponse
import app.models as models
from django.db import connection
from io import BytesIO
from django.db.models import Sum, F
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.functions import Abs, Round
import pandas as pd
from custom.pdf.split import (LastPageFindMethods,
                                        split_using_last_page)

T = TypeVar("T", bound=Session.Session)
P = ParamSpec("P")
R = TypeVar("R")

def check_login(
    Client: Type[T],
) -> Callable[[Callable[P, R]], Callable[P, R | Response]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R | Response]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs):
            client = Client("devaki")
            if not client.is_logged_in():  # type: ignore
                return Response({"key": client.key}, status=501)
            return func(*args, **kwargs)

        return wrapper

    return decorator

CLIENTS: dict[str, type] = {
    "gst": Gst,
    "einvoice": Einvoice,
}

@api_view(["POST"])
def get_captcha(request):
    key = request.data.get("key")
    Client = CLIENTS.get(str(key).lower())
    if not Client:
        return Response({"error": "invalid key"}, status=400)

    user = request.user.get_username()
    client = Client(user)
    # Expect client.captcha() to return a BytesIO or bytes
    img_io = client.captcha()  # type: ignore
    data = img_io.getvalue() if hasattr(img_io, "getvalue") else bytes(img_io)  # type: ignore
    resp = HttpResponse(data, content_type="image/png")
    resp["Content-Disposition"] = 'inline; filename="captcha.png"'
    return resp

@api_view(["POST"])
def captcha_login(request):
    key = request.data.get("key")
    captcha_text = request.data.get("captcha")
    Client = CLIENTS.get(str(key).lower())
    if not Client or not captcha_text:
        return Response({"error": "invalid payload"}, status=400)
    user = request.user.get_username()
    client = Client(user)
    try:
        client.login(captcha_text)  # type: ignore
        ok = client.is_logged_in()
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=400)
    return Response({"ok": bool(ok)}, status=200)

def excel_response(sheets:list[tuple],filename:str) : 
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, df in sheets:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

#Einvoice Damage APIs
@api_view(["POST"])
@check_login(Einvoice)
def einvoice_damage_stats(request):

    period = request.data.get("period")
    invs = list(
        models.Sales.user_objects.for_user(request.user).filter(
            gst_period=period, ctin__isnull=False, type="damage"
        )
    )
    company_stats = defaultdict(lambda: {"amt": 0, "filed": 0, "not_filed": 0})
    for inv in invs:
        if inv.irn:
            company_stats[inv.company_id]["filed"] += 1
        else:
            company_stats[inv.company_id]["not_filed"] += 1
            company_stats[inv.company_id]["amt"] += abs(inv.amt)

    # Make a Total entry , if more than one company present
    if len(company_stats) > 1:
        total_filed = sum(stats["filed"] for stats in company_stats.values())
        total_not_filed = sum(stats["not_filed"] for stats in company_stats.values())
        total_amt = sum(stats["amt"] for stats in company_stats.values())
        company_stats["total"] = {
            "filed": total_filed,
            "not_filed": total_not_filed,
            "amt": total_amt,
        }

    return JsonResponse({"stats": company_stats})

@api_view(["POST"])
@check_login(Einvoice)
def einvoice_damage_file(request):
    period = request.data.get("period")
    qs = models.Sales.user_objects.for_user(request.user).filter(
        gst_period=period, ctin__isnull=False, type="damage"
    )
    e = Einvoice(request.user.get_username())
    seller_json = e.config["seller_json"]
    month, year = int(period[:2]), int(period[-4:])
    last_day_of_period = datetime.date(year, month, calendar.monthrange(year, month)[1])
    today = datetime.date.today()
    date_fn = lambda date: (last_day_of_period if (today - date).days >= 28 else date)
    json_data = create_einv_json(qs, seller_json=seller_json, date_fn=date_fn)
    with open("damage_einv.json","w+") as f :
        f.write(json_data)
    success, failed = e.upload(json_data)
    duplicate_irns = failed[failed["Error Code"] == 2150]
    for _, row in duplicate_irns.iterrows():
        error = row["Error Date"]
        irn = re.findall(r'([a-f0-9]{64})', error)
        if not irn: continue
        models.Sales.user_objects.for_user(request.user).filter(
            inum=row["Invoice No"]
        ).update(irn=irn[0])

    for _, row in success.iterrows():
        models.Sales.user_objects.for_user(request.user).filter(
            inum=row["Doc No"]
        ).update(irn=row["IRN"])
    sheets = [("failed", failed), ("success", success)]
    return excel_response(sheets, f"damage_einvoice_{datetime.date.today()}.xlsx")

@api_view(["POST"])
@check_login(Einvoice)
def einvoice_damage_excel(request):
    period = request.data.get("period")
    damage_qs = models.Sales.user_objects.for_user(request.user).filter(
        gst_period=period, type="damage"
    )
    # Registered and unregisterted (ctin not null and null)
    damage_qs = damage_qs.annotate(
        txval=Round(Abs(Sum("inventory__txval")), 2),
        cgst=Round(
            Abs(Sum(models.F("inventory__txval") * models.F("inventory__rt") / 100)), 2
        ),
        party_name=F("party__name"),
    ).order_by("company_id", "inum")

    if not damage_qs.exists():
        return Response(
            {"error": "No damage invoices found for the given period"}, status=404
        )

    registerd = damage_qs.filter(ctin__isnull=False)
    unregistered = damage_qs.filter(ctin__isnull=True)
    sheets: list[tuple] = []
    for sheet_name, qs in [("registered", registerd), ("unregistered", unregistered)]:
        data = []
        for inv in qs:
            data.append(
                {
                    "Company": inv.company.name,
                    "Invoice Number": inv.inum,
                    "Invoice Date": inv.date.strftime("%d-%m-%Y"),
                    "Party Name": inv.party_name or "-",
                    "GSTIN": inv.ctin or "",
                    "Amount": abs(inv.amt),
                    "Taxable Value": round(inv.txval, 2),
                    "CGST": round(inv.cgst, 2),
                    "IRN": inv.irn or "",
                }
            )
        df = pd.DataFrame(data).astype(dtype = {"Taxable Value": float , "CGST" : float , "Amount" : float} )
        sheets.append((sheet_name, df))

    return excel_response(sheets, f"damage_{period}.xlsx")

@api_view(["POST"])
@check_login(Gst)
def einvoice_damage_pdf(request):
    period = request.data.get("period")
    qs = models.Sales.user_objects.for_user(request.user).filter(
        gst_period=period, type="damage", ctin__isnull=False
    )
    tform = template.Template(open("app/templates/einvoice_print_form.html").read())
    username = request.user.get_username()
    gst = Gst(username)
    gstin = gst.config["gstin"]
    path = "static/print_includes"
    os.system(f"rm -rf static/{username}/bill_pdf")
    os.makedirs(f"static/{username}/bill_pdf",exist_ok=True)
    os.system(f"rm static/{username}/bills.zip")
    
    def fetch_inv(row) :     
        doctype = "INV" if row.type in ("sales","claimservice") else "CRN"
        data = gst.get_einv_data( gstin , row.date.strftime("%m%Y") ,  doctype , row.inum )
        if data is None : 
           print(f"Einv data not found for {row.inum}")
           return
        c = template.Context(data | {"path" : path })
        forms.append(tform.render(c))

    from multiprocessing.pool import ThreadPool
    invs = list(qs)
    BATCH_SIZE = 20 
    for i in range(0,len(invs),BATCH_SIZE) : 
        forms = []
        fetch_inv_pool = ThreadPool() # Fetch the invoice or retrive if availabe in DB . 
        fetch_inv_pool.map(fetch_inv,invs[ i : min(i+BATCH_SIZE,len(invs)) ]) 
        fetch_inv_pool.close()
        fetch_inv_pool.join()
        thtml = template.Template(open("app/templates/einvoice_print.html").read())
        c = template.Context({"forms" : forms , "path" : path })
        with open(f"bill.html","w+") as f : f.write( thtml.render(c) )
        os.system(f"google-chrome --headless --disable-gpu --print-to-pdf=bill.pdf bill.html")    
        find_last_page = LastPageFindMethods.create_pattern_method("Digitally Signed by NIC-IRP")
        get_pdf_name = lambda text : f"static/{username}/bill_pdf/" + (re.findall(r"Document No  : ([A-Z0-9a-z ]*)",text)[0].replace(" ",""))
        split_using_last_page(f"bill.pdf",find_last_page,get_pdf_name)
    
    os.system("rm -rf bill.html bill.pdf")
    os.system(f"zip -r -j static/{username}/bills.zip static/{username}/bill_pdf/*")
    return FileResponse(open(f"static/{username}/bills.zip","rb"),as_attachment=True,filename=f"bills_{period}.zip")


#Gst Monthly Return APIs
@api_view(["POST"])
@check_login(Gst)
def generate_gst_return(request):
    period = request.data.get("period")
    gst_client = Gst(request.user.get_username())
    models.GSTR1Portal.update_db(gst_client, request.user, period)
    gstin = gst_client.config["gstin"]
    #It creates the workings excel and json 
    summary = gst.generate(request.user, period, gstin)
    summary = summary.reset_index().rename(columns={"company_id" : "Company",
                                                    "gst_type" : "GST Type",
                                                    "type" : "Invoice Type",
                                                    "txval" : "Taxable Value",
                                                    "cgst" : "CGST"})
    data = { 
        "summary": summary.to_dict(orient="records"),
    }
    return JsonResponse(data)

@api_view(["POST"])
def gst_summary(request):
    period = request.data.get("period")
    return FileResponse(open(f"static/{request.user.get_username()}/workings_{period}.xlsx","rb"),as_attachment=True,filename=f"gst_{period}_summary.xlsx")

@api_view(["POST"])
def gst_json(request):
    period = request.data.get("period")
    return FileResponse(open(f"static/{request.user.get_username()}/{period}.json","rb"),as_attachment=True,filename=f"gst_{period}.json")