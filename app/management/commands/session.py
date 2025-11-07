from io import BytesIO
import pandas as pd
from custom.classes import Einvoice, Gst, IkeaDownloader
from app.company_models import UserSession

# UserSession.objects.filter(key="einvoice").delete()

#Ikea Session
UserSession(
    user="devaki_hul",
    key="ikea",
    username="IIT",
    password="Ven@1234",
    config={
        "dbName": "41A392",
        "home": "https://leveredge18.hulcd.com",
        "bill_prefix" : "A",
        "auto_delivery_process" : True
    },
).save(force_insert=False)
# # i = IkeaDownloader("devaki_hul")
# # print(i.get("/rsunify/app/billing/getUserId").text)


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
g = Einvoice("devaki")
for cookie in g.cookies:
    print(cookie.name, cookie.value)
while not g.is_logged_in():
    with open("captcha.png", "wb+") as f:
        f.write(g.captcha())
    captcha_input = input("Enter Captcha : ")
    status = g.login(captcha_input)
    print("Login status : ", status)
print("Einvoice Logged in successfully")
today_einvs_bytesio = BytesIO(g.get_filed_einvs())
today_einvs_df = pd.read_excel(today_einvs_bytesio)
