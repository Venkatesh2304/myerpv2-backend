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
from app.einvoice import change_einv_dates, create_einv_json, einv_json_to_str
from custom import Session
from custom.classes import Gst, Einvoice, IkeaDownloader, WrongCredentials  # type: ignore
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
from multiprocessing.pool import ThreadPool
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO

T = TypeVar("T", bound=Session.Session)
P = ParamSpec("P")
R = TypeVar("R")

def check_login(
    Client: Type[T],
) -> Callable[[Callable[P, R]], Callable[P, R | Response]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R | Response]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs):
            request = args[0]
            client = Client(request.user.get_username()) # type: ignore
            if not client.is_logged_in():  # type: ignore
                print("Client not logged in")
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
    except WrongCredentials as e:
        return Response({"ok": False, "error": "invalid_credentials", "message" : str(e)}, status = 200)
    except Exception as e:
        return Response({"ok": False, "error": str(e)}, status=400)
    return Response({"ok": bool(ok) , "error" : "" if ok else "invalid_captcha"}, status=200)

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

#Einvoice APIs
def load_irns(request,gst = True,einvoice = True):
    period = request.data.get("period")
    username = request.user.get_username()
    irn_mapping = {}
    if gst : 
        #Update using Gst data for the period
        gst_client = Gst(username)
        models.GSTR1Portal.update_db(gst_client, request.user, period)
        irn_mapping |= {
            inv.inum: inv.irn
            for inv in models.GSTR1Portal.objects.filter(user=request.user, period=period)
        }
    if einvoice : 
        # Update using einvoice (last 3 days)
        einvoice_client = Einvoice(username)
        for days_ago in range(3) : 
            date = datetime.date.today() - datetime.timedelta(days=days_ago)
            einv_data = einvoice_client.get_filed_einvs(date = date)
            for _,row in einv_data.iterrows() : 
                irn_mapping[row["Doc No"]] = row["IRN"]

    invs = list(models.Sales.user_objects.for_user(request.user).filter(inum__in=irn_mapping.keys(), gst_period=period))
    for inv in invs : 
        inv.irn = irn_mapping.get(inv.inum)
    models.Sales.objects.bulk_update(invs,["irn"])

@api_view(["POST"])
@check_login(Einvoice)
@check_login(Gst)
def einvoice_reload(request):
    load_irns(request)
    return Response({"ok": True})

@api_view(["POST"])
@check_login(Einvoice)
def einvoice_stats(request):
    period = request.data.get("period")
    type = request.data.get("type")
    
    invs = models.Sales.user_objects.for_user(request.user).filter(
            gst_period=period, ctin__isnull=False, inventory__rt__gt = 0)
    if type != "all" : invs = invs.filter(type=type)
    invs = invs.distinct()
    
    company_type_wise_stats = defaultdict(lambda: {"amt": 0, "filed": 0, "not_filed": 0})
    for inv in invs.iterator():
        if inv.irn:
            company_type_wise_stats[(inv.company_id,inv.type)]["filed"] += 1
        else:
            company_type_wise_stats[(inv.company_id,inv.type)]["not_filed"] += 1
            company_type_wise_stats[(inv.company_id,inv.type)]["amt"] += abs(inv.amt)

    # Make a Total entry , if more than one company present
    if len(company_type_wise_stats) > 1:
        total_filed = sum(stats["filed"] for stats in company_type_wise_stats.values())
        total_not_filed = sum(stats["not_filed"] for stats in company_type_wise_stats.values())
        total_amt = sum(stats["amt"] for stats in company_type_wise_stats.values())
        company_type_wise_stats[("total","")] = {
            "filed": total_filed,
            "not_filed": total_not_filed,
            "amt": total_amt,
        }
    stats = [{"company" : company, "type" : type , **stat} for (company,type) , stat in company_type_wise_stats.items()]
    stats.sort(key=lambda x: (x["company"] != "total", x["not_filed"]),reverse=True)
    return JsonResponse({"stats": stats})

@api_view(["POST"])
@check_login(Einvoice)
def file_einvoice(request):
    period = request.data.get("period")
    type = request.data.get("type")
    qs = models.Sales.user_objects.for_user(request.user).filter(
        gst_period=period, ctin__isnull=False, type=type, irn__isnull=True
    )
    e = Einvoice(request.user.get_username())
    seller_json = e.config["seller_json"]
    month, year = int(period[:2]), int(period[-4:])
    first_day_of_period = datetime.date(year, month, 1)
    last_day_of_period = datetime.date(year, month, calendar.monthrange(year, month)[1])

    sales_qs = qs.filter(type__in=["sales","salesreturn"])
    json_data = []
    if sales_qs.exists():
        company_to_inums = defaultdict(list)
        for inv in sales_qs:
            company_to_inums[inv.company_id].append(inv.inum)
        for company,inums in company_to_inums.items() : 
            ikea_downloader = IkeaDownloader(company)
            ikea_einv_json:BytesIO = ikea_downloader.einvoice_json(first_day_of_period,last_day_of_period,inums)
            if ikea_einv_json is None : 
                continue
            data = json.loads(ikea_einv_json.getvalue())
            json_data += [ entry for entry in data if entry["DocDtls"]["No"] in inums ]

    inums_from_ikea_einv_json = [ entry["DocDtls"]["No"] for entry in json_data ]
    qs = qs.exclude(inum__in=inums_from_ikea_einv_json)
    json_data += create_einv_json(qs, seller_json=seller_json)
    print(json_data)
    
    json_data = change_einv_dates(json_data, fallback_date=last_day_of_period)
    json_data = einv_json_to_str(json_data)
    with open("einv.json","w+") as f :
        f.write(json_data)

    success, failed = e.upload(json_data)
    print(failed)
    error_column = "Error Date" #Note : this might be different in future
    #Error handling
    # Handle duplicate IRNs and update the irns in Sales
    duplicate_irns = failed[failed["Error Code"] == 2150]
    for _, row in duplicate_irns.iterrows():
        error = row[error_column]
        irn = re.findall(r'([a-f0-9]{64})', error)
        if not irn: continue
        models.Sales.user_objects.for_user(request.user).filter(
            inum=row["Invoice No"]
        ).update(irn=irn[0])

    # Handle wrong gstin or cancelled gstin and move the sales invoices to ctin null
    wrong_gstin = failed[(failed["Error Code"] >= 3074) & (failed["Error Code"] <= 3079)]
    for _, row in wrong_gstin.iterrows():
        inv:models.Sales = models.Sales.user_objects.for_user(request.user).get(
            inum=row["Invoice No"]
        )
        inv.update_and_log("ctin", None, row[error_column])


    for _, row in success.iterrows():
        models.Sales.user_objects.for_user(request.user).filter(
            inum=row["Doc No"]
        ).update(irn=row["IRN"])
    sheets = [("failed", failed), ("success", success)]
    return excel_response(sheets, f"einvoice_{datetime.date.today()}.xlsx")

@api_view(["POST"])
def einvoice_excel(request):
    period = request.data.get("period")
    type = request.data.get("type")
    qs = models.Sales.user_objects.for_user(request.user).filter(
        gst_period=period, type=type
    )
    # Registered and unregisterted (ctin not null and null)
    qs = qs.annotate(
        txval=Round(Abs(Sum("inventory__txval")), 2),
        cgst=Round(
            Abs(Sum(models.F("inventory__txval") * models.F("inventory__rt") / 100)), 2
        ),
        party_name=F("party__name"),
    ).order_by("company_id", "inum")

    if not qs.exists():
        return Response(
            {"error": f"No invoices found for the given period for type : {type}"}, status=404
        )

    registerd = qs.filter(ctin__isnull=False)
    unregistered = qs.filter(ctin__isnull=True)
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

    return excel_response(sheets, f"{type}_{period}.xlsx")

@api_view(["POST"])
@check_login(Gst)
def einvoice_pdf(request):
    period = request.data.get("period")
    type = request.data.get("type")
    load_irns(request,gst = True,einvoice=False)
    qs = models.Sales.user_objects.for_user(request.user).filter(
        gst_period=period, type=type, ctin__isnull=False, irn__isnull=False
    ).prefetch_related("party")
    if qs.count() > 200 : 
        return Response(
            {"error": "Cannot generate more than 200 invoices at a time."}, status=400
        )
    tform = template.Template(open("app/templates/einvoice_print_form.html").read())
    username = request.user.get_username()
    gst = Gst(username)
    gstin = gst.config["gstin"]
    path = "static/print_includes"

    if os.path.exists(f"static/{username}/bills.zip") : 
        os.remove(f"static/{username}/bills.zip")
    
    def fetch_inv(row) :     
        doctype = "INV" if row.type in ("sales","claimservice") else "CRN"
        data = gst.get_einv_data( gstin , row.date.strftime("%m%Y") ,  doctype , row.inum )
        if data is None : 
           print(f"Einv data not found for {row.inum}")
           return
        c = template.Context(data | {"path" : path })
        forms.append(tform.render(c))

    invs = list(qs)
    BATCH_SIZE = 20
    files = {}
    inums_to_party = { inv.inum : (inv.party.name if inv.party else "unknown")  for inv in invs }
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
        get_pdf_name = lambda text : re.findall(r"Document No  : ([A-Z0-9a-z ]*)",text)[0].replace(" ","")
        files |= split_using_last_page(f"bill.pdf",find_last_page,get_pdf_name,temp_buffer = True)
    
    #Group files by parties 
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zip_file:        
        for inum,bytesio in files.items() : 
            party = inums_to_party.get(inum,"unknown")
            zip_file.writestr(f"{party}/{inum}.pdf", bytesio.getvalue())

    with open(f"static/{username}/bills.zip", "wb") as f:
        f.write(zip_buffer.getvalue())

    return FileResponse(open(f"static/{username}/bills.zip","rb"),as_attachment=True,filename=f"bills_{period}.zip")


#Gst Monthly Return APIs
@api_view(["POST"])
@check_login(Gst)
@check_login(Einvoice)
def generate_gst_return(request):
    period = request.data.get("period")
    load_irns(request)
    gst_instance = Gst(request.user.get_username())
    #It creates the workings excel and json 
    summary = gst.generate(request.user, period, gst_instance)
    gst_company_type_stats = summary["gst_company_type_stats"].reset_index().rename(columns={"company_id" : "Company",
                                                    "gst_type" : "GST Type",
                                                    "txval" : "Taxable Value",
                                                    "cgst" : "CGST"})
    data = { 
        "summary": gst_company_type_stats.to_dict(orient="records"),
        "missing": len(summary["missing"].index)  , 
        "mismatch" : len(summary["mismatch"].index) ,
        "yet_to_be_pushed" : len(summary["yet_to_be_pushed"].index) ,
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


@api_view(["GET","POST"])
def usersession_update(request):

    if request.method == "GET":
        sessions = models.UserSession.objects.all().values("key", "user", "username", "password")
        grouped = {}
        for s in sessions:
            k = s["key"]
            grouped.setdefault(k, []).append(
                {
                    "user": s["user"],
                    "username": s["username"],
                    "password": s["password"],
                }
            )
        return JsonResponse(grouped)

    # POST
    key = request.data.get("key")
    user = request.data.get("user")
    new_username = request.data.get("username")
    new_password = request.data.get("password")

    session = models.UserSession.objects.get(key=key, user=user)
    session.username = new_username
    session.password = new_password
    session.save(update_fields=["username", "password"])

    return JsonResponse({"status": "updated", "key": session.key, "user": session.user})
