from app.models import User
from io import BytesIO
import pandas as pd
from custom.classes import Einvoice, Gst, IkeaDownloader
from app.company_models import Company, UserSession


# User.objects.filter(username='devaki').delete()
# UserSession.objects.filter(user='devaki').delete()
# UserSession.objects.filter(user='devaki_hul').delete()

# user = User.objects.create_user(username='devaki', password='1')
# company = Company.objects.create(name="devaki_hul",user = user,gst_types = ["sales","salesreturn","claimservice","damage"])
company = Company.objects.create(name="devaki_rural",user_id = 'devaki',gst_types = ["sales","salesreturn","claimservice","damage"])


#Ikea Session
UserSession(
    user="devaki_rural",
    key="ikea",
    username="IIT",
    password="Abc@123456",
    config={
        "dbName": "41B862",
        "home": "https://leveredge57.hulcd.com",
        "bill_prefix" : "CB",
        "auto_delivery_process" : True
    },
).save(force_insert=False)
i = IkeaDownloader("devaki_rural")

print(i.get("/rsunify/app/billing/getUserId").text)
exit(0)


# #Gst Session
UserSession(
    user="devaki",
    key="gst",
    username="DEVAKI9999",
    password="Ven@2026",
    config={
        "gstin" : "33AAPFD1365C1ZR"
    }
).save()
# g = Gst("devaki")
# for cookie in g.cookies :
#     print(cookie.name,cookie.value)
# while not g.is_logged_in() :
#     with open("captcha.png","wb+") as f :
#         f.write(g.captcha())
#     captcha_input = input("Enter Captcha : ")
#     status = g.login(captcha_input)
#     print("Login status : ",status)
# print("Gst Logged in successfully")

UserSession(
    user="devaki",
    key="einvoice",
    username="DEVAKI9999",
    password="Ven@2345",
    config={
        "seller_json": {
            "SellerDtls": {
                "Gstin": "33AAPFD1365C1ZR",
                "LglNm": "DEVAKI ENTERPRISES",
                "Addr1": "F/4 , INDUSTRISAL ESTATE , ARIYAMANGALAM",
                "Loc": "TRICHY",
                "Pin": 620010,
                "Stcd": "33",
            }
        }
    },
).save()
exit(0)